"""Mistral's chat-completions API (https://docs.mistral.ai/api/), with
function calling. Off unless `MISTRAL_API_KEY` is set."""

import asyncio
import json
import logging

import httpx

from app.coach_ai.ports import LlmError, LlmReply, ToolCall
from app.core.config import get_settings

logger = logging.getLogger("coach_ai.client")

# Mistral Large 4 reasons before answering (~37 tokens/s, measured 11/18):
# a plan proposal with its step trees can take minutes, so the read timeout
# is long and a read timeout is never retried — that request was already
# being generated, and billed.
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)
_RETRIES = 2


def ai_coach_available() -> bool:
    return bool(get_settings().mistral_api_key)


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
        json_mode: bool = False,
        temperature: float = 0.4,
        max_tokens: int | None = None,
    ) -> LlmReply:
        if not self._api_key:
            raise LlmError("The AI coach isn't configured (no MISTRAL_API_KEY)")
        body: dict = {"model": self._model, "messages": messages, "temperature": temperature}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if max_tokens:
            body["max_tokens"] = max_tokens
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=_TIMEOUT,
            transport=self._transport,
        ) as client:
            for attempt in range(_RETRIES + 1):
                try:
                    response = await client.post("/chat/completions", json=body)
                except httpx.HTTPError as exc:
                    if attempt < _RETRIES and not isinstance(exc, httpx.ReadTimeout):
                        await asyncio.sleep(2**attempt)
                        continue
                    raise LlmError(f"Mistral unreachable: {exc}") from exc
                if response.status_code in (429, 500, 502, 503, 504) and attempt < _RETRIES:
                    retry = response.headers.get("Retry-After", "")
                    await asyncio.sleep(min(int(retry), 20) if retry.isdigit() else 2 ** (attempt + 1))
                    continue
                break
        if response.status_code in (401, 403):
            raise LlmError("Mistral refused the API key")
        if response.status_code >= 400:
            logger.warning("Mistral answered HTTP %s: %s", response.status_code, response.text[:500])
            raise LlmError(f"Mistral answered HTTP {response.status_code}")
        return parse_reply(response.json(), self._model)


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
