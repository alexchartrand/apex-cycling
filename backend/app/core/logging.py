"""Logging setup shared by the API and the worker.

`LOG_FORMAT=json` (set in the prod compose) emits one JSON object per line,
which `docker logs` / CloudWatch / jq can filter; anything else is the plain
dev format. Every record made while handling a request carries its
`request_id`, the same value returned in the `X-Request-ID` response header,
so a user's error report can be matched to the log lines.
"""

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "x-request-id"
_MAX_INBOUND_ID_LENGTH = 64
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "taskName", "color_message"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            entry["request_id"] = request_id
        # Fields passed with `extra=` (method, path, status, …).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key != "request_id" and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if os.environ.get("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s [%(request_id)s]")
        )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    # uvicorn installs its own handlers; route them through ours. Access lines
    # come from RequestLogMiddleware instead (they know the request id).
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True


class RequestLogMiddleware:
    """Pure-ASGI middleware: assigns a request id (or keeps a sane inbound
    one), echoes it in `X-Request-ID` and logs one line per request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("app.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = inbound if _is_safe_id(inbound) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            # Health probes run every few seconds; keep them out of the log
            # unless they fail.
            if not (scope["path"].endswith("/health") and status_code < 400):
                client = scope.get("client")
                self.logger.info(
                    "%s %s %s",
                    scope["method"],
                    scope["path"],
                    status_code,
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "client_ip": client[0] if client else None,
                    },
                )
            request_id_var.reset(token)


def _is_safe_id(value: str) -> bool:
    return 0 < len(value) <= _MAX_INBOUND_ID_LENGTH and all(c.isalnum() or c in "-_." for c in value)
