"""Mistral's chat-completions API (https://docs.mistral.ai/api/), with
function calling. Off unless `MISTRAL_API_KEY` is set."""

import asyncio
import json
import logging

import httpx

from app.coach_ai.ports import LlmError, LlmReply, ToolCall
from app.core.config import get_settings

logger = logging.getLogger("coach_ai.client")

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
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
                    if attempt < _RETRIES:
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
        message = body["choices"][0]["message"]
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
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")
    usage = body.get("usage") or {}
    return LlmReply(
        content=content or None,
        tool_calls=calls,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        model=str(body.get("model") or model),
    )
