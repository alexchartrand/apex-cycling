"""Mistral's chat-completions API (https://docs.mistral.ai/api/), with
function calling. Off unless `MISTRAL_API_KEY` is set."""

import asyncio
import json
import logging
from typing import Literal

import httpx

from app.coach_ai.ports import DeltaHandler, LlmError, LlmReply, ToolCall
from app.core.config import get_settings

logger = logging.getLogger("coach_ai.client")

# Mistral Large 4 reasons before answering (~37 tokens/s, measured 11/18):
# a plan proposal with its step trees can take minutes, so the read timeout
# is long and a read timeout is never retried — that request was already
# being generated, and billed.
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)
_RETRIES = 2


class MistralClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.mistral_api_key
        self._model = model or settings.mistral_model
        self._base_url = (base_url or settings.mistral_base_url).rstrip("/")
        self._reasoning_effort = settings.mistral_reasoning_effort
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        tool_choice: Literal["auto", "none"] = "auto",
        json_mode: bool = False,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        on_delta: DeltaHandler | None = None,
    ) -> LlmReply:
        if not self._api_key:
            raise LlmError("The AI coach isn't configured (no MISTRAL_API_KEY)")
        messages = [{k: v for k, v in m.items() if k != "provider_content"} for m in messages]
        body: dict = {"model": self._model, "messages": messages, "temperature": temperature}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if max_tokens:
            body["max_tokens"] = max_tokens
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort

        if on_delta is not None:
            body["stream"] = True

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=_TIMEOUT,
            transport=self._transport,
        ) as client:
            for attempt in range(_RETRIES + 1):
                request = client.build_request("POST", "/chat/completions", json=body)
                try:
                    response = await client.send(request, stream=True)
                except httpx.HTTPError as exc:
                    if attempt < _RETRIES and not isinstance(exc, httpx.ReadTimeout):
                        await asyncio.sleep(2**attempt)
                        continue
                    raise LlmError(f"Mistral unreachable: {exc}") from exc
                try:
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < _RETRIES:
                        retry = response.headers.get("Retry-After", "")
                        await asyncio.sleep(min(int(retry), 20) if retry.isdigit() else 2 ** (attempt + 1))
                        continue
                    if response.status_code in (401, 403):
                        raise LlmError("Mistral refused the API key")
                    if response.status_code >= 400:
                        text = (await response.aread()).decode(errors="replace")
                        logger.warning("Mistral answered HTTP %s: %s", response.status_code, text[:500])
                        raise LlmError(f"Mistral answered HTTP {response.status_code}")
                    # Past this point the reply is being generated (and billed): never retried.
                    try:
                        if on_delta is None:
                            return parse_reply(json.loads(await response.aread()), self._model)
                        return await _read_stream(response, self._model, on_delta)
                    except httpx.HTTPError as exc:
                        raise LlmError(f"Mistral connection lost: {exc}") from exc
                    except ValueError as exc:
                        raise LlmError("Unexpected answer from Mistral") from exc
                finally:
                    await response.aclose()
        raise LlmError("Mistral kept failing")  # pragma: no cover - the loop always returns or raises


async def _read_stream(response: httpx.Response, model: str, on_delta: DeltaHandler) -> LlmReply:
    """Server-sent events, one `chat.completion.chunk` per `data:` line, then `[DONE]`."""
    stream = StreamedReply(model)
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        for kind, text in stream.feed(json.loads(data)):
            await on_delta(kind, text)
    return stream.reply()


class StreamedReply:
    """Puts a streamed reply back together: content pieces, tool calls (whose
    arguments may come in fragments, keyed by `index`), usage on the last chunk."""

    def __init__(self, model: str) -> None:
        self.model = model
        self._text: list[str] = []
        self._calls: dict[int, dict] = {}
        self._usage: dict = {}
        self._finish: str | None = None
        self._thinking_chars = 0

    def feed(self, chunk: dict) -> list[tuple[str, str]]:
        """Takes one chunk; returns what to pass on: ("text", piece) / ("thinking", "")."""
        if not isinstance(chunk, dict):
            raise ValueError("chunk is not an object")
        if chunk.get("model"):
            self.model = str(chunk["model"])
        if chunk.get("usage"):
            self._usage = chunk["usage"]
        out: list[tuple[str, str]] = []
        for choice in chunk.get("choices") or []:
            if choice.get("finish_reason"):
                self._finish = choice["finish_reason"]
            delta = choice.get("delta") or {}
            content = delta.get("content")
            parts = content if isinstance(content, list) else [{"type": "text", "text": content}] if content else []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text" and part.get("text"):
                    self._text.append(part["text"])
                    out.append(("text", part["text"]))
                elif part.get("type") == "thinking":
                    self._thinking_chars += len(_text_of(part.get("thinking")))
                    out.append(("thinking", ""))
            for position, call in enumerate(delta.get("tool_calls") or []):
                index = call.get("index")
                index = index if isinstance(index, int) else len(self._calls) if call.get("id") else position
                slot = self._calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                if call.get("id"):
                    slot["id"] = str(call["id"])
                function = call.get("function") or {}
                if function.get("name"):
                    slot["name"] = str(function["name"])
                arguments = function.get("arguments")
                if arguments:
                    slot["arguments"] += arguments if isinstance(arguments, str) else json.dumps(arguments)
        return out

    def reply(self) -> LlmReply:
        content = "".join(self._text)
        calls = [ToolCall(id=c["id"], name=c["name"], arguments=c["arguments"]) for _, c in sorted(self._calls.items())]
        if self._thinking_chars:
            logger.info("Mistral reasoning: %d chars, answer: %d chars, %d tool calls", self._thinking_chars, len(content), len(calls))
        return LlmReply(
            content=content or None,
            tool_calls=calls,
            prompt_tokens=int(self._usage.get("prompt_tokens") or 0),
            completion_tokens=int(self._usage.get("completion_tokens") or 0),
            model=self.model,
            truncated=self._finish == "length",
        )


def parse_reply(body: dict, model: str) -> LlmReply:
    try:
        choice = body["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("Unexpected answer from Mistral") from exc
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments", "")
        if not isinstance(arguments, str):  # some versions send an object
            arguments = json.dumps(arguments)
        calls.append(ToolCall(id=str(call.get("id", "")), name=str(function.get("name", "")), arguments=arguments))
    content = message.get("content")
    if isinstance(content, list):  # chunked content (text parts, maybe "thinking" parts)
        parts = [part for part in content if isinstance(part, dict)]
        content = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        thinking = sum(len(_text_of(part.get("thinking"))) for part in parts if part.get("type") == "thinking")
        if thinking:
            logger.info("Mistral reasoning: %d chars, answer: %d chars, %d tool calls", thinking, len(content), len(calls))
    usage = body.get("usage") or {}
    return LlmReply(
        content=content or None,
        tool_calls=calls,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        model=str(body.get("model") or model),
        truncated=choice.get("finish_reason") == "length",
    )


def _text_of(value: object) -> str:
    """Thinking parts are text, or a list of {type: text, text} chunks."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_text_of(v.get("text") if isinstance(v, dict) else v) for v in value)
    return ""
