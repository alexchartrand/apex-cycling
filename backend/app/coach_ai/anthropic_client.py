"""Anthropic's Messages API (Claude), behind the same `LlmClientPort` as
Mistral. The service speaks chat-completion messages; this module turns them
into Messages-API requests and the streamed answer back into an `LlmReply`.

- Adaptive thinking (always on for current Claude models) at the configured
  effort. Its blocks come back in `LlmReply.provider_content` and the service
  sends them back for the rest of the same turn. Earlier turns are sent as
  plain text and tool blocks: the brief in the system prompt changes every
  turn, which would fail the API's history check on those blocks anyway.
  `drop_block` covers the case where it still fails (the last round's
  `tool_choice` change), so a request is never refused for it.
- A refusal is retried server-side on another model (`fallbacks: "default"`).
- No `temperature`: current Claude models refuse anything but the default.
"""

import json
import logging
import re
from typing import Literal

import anthropic

from app.coach_ai.ports import DeltaHandler, LlmError, LlmReply, ToolCall
from app.core.config import get_settings

logger = logging.getLogger("coach_ai.anthropic")

_BETAS = ["server-side-fallback-2026-07-01", "thinking-binding-controls-2026-08-01"]
_TIMEOUT = 600.0
_TOOL_ID = re.compile(r"[^a-zA-Z0-9_-]")


class AnthropicClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.anthropic_model
        self._effort = effort if effort is not None else settings.anthropic_effort
        self._client = client

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
        temperature: float = 0.4,  # ignored, see the module docstring
        max_tokens: int | None = None,
        on_delta: DeltaHandler | None = None,
    ) -> LlmReply:
        if not self._api_key and self._client is None:
            raise LlmError("The AI coach isn't configured (no ANTHROPIC_API_KEY)")
        system, converted = to_anthropic_messages(messages)
        if json_mode:
            system += "\n\nAnswer with one JSON object and nothing else."
        params: dict = {
            "model": self._model,
            "max_tokens": max_tokens or 16000,
            "messages": converted,
            "thinking": {"type": "adaptive", "block_binding": {"prefix_mismatch_behavior": "drop_block"}},
            "betas": _BETAS,
            "fallbacks": "default",
            # Caches the system prompt and history across the rounds of a turn.
            "cache_control": {"type": "ephemeral"},
        }
        if system:
            params["system"] = system
        if self._effort:
            params["output_config"] = {"effort": self._effort}
        if tools:
            params["tools"] = [to_anthropic_tool(t) for t in tools]
            params["tool_choice"] = {"type": tool_choice}

        client = self._client or anthropic.AsyncAnthropic(api_key=self._api_key, timeout=_TIMEOUT, max_retries=2)
        try:
            async with client.beta.messages.stream(**params) as stream:
                if on_delta is not None:
                    async for event in stream:
                        if event.type == "content_block_start" and event.content_block.type in (
                            "thinking",
                            "redacted_thinking",
                        ):
                            await on_delta("thinking", "")
                        elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                            await on_delta("text", event.delta.text)
                message = await stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LlmError("Anthropic refused the API key") from exc
        except anthropic.PermissionDeniedError as exc:
            raise LlmError("Anthropic refused the request (permission)") from exc
        except anthropic.RateLimitError as exc:
            raise LlmError("Anthropic rate limit") from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Anthropic answered HTTP %s: %s", exc.status_code, str(exc.message)[:500])
            raise LlmError(f"Anthropic answered HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LlmError(f"Anthropic unreachable: {exc}") from exc
        return to_reply(message, self._model)


def to_reply(message, model: str) -> LlmReply:
    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None) if message.stop_details else None
        logger.warning("Anthropic declined the request (category %s)", category)
        raise LlmError("The model declined to answer")
    text = "".join(block.text for block in message.content if block.type == "text")
    calls = [
        ToolCall(id=block.id, name=block.name, arguments=json.dumps(block.input, ensure_ascii=False))
        for block in message.content
        if block.type == "tool_use"
    ]
    usage = message.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    prompt = (usage.input_tokens or 0) + cache_read + cache_write
    return LlmReply(
        content=text or None,
        tool_calls=calls,
        prompt_tokens=prompt,
        completion_tokens=usage.output_tokens or 0,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        model=str(message.model or model),
        truncated=message.stop_reason == "max_tokens",
        provider_content=[block.model_dump(mode="json", by_alias=True, exclude_none=True) for block in message.content],
    )


def to_anthropic_tool(tool: dict) -> dict:
    """A chat-completion function definition → a Messages-API tool."""
    function = tool.get("function", tool)
    return {
        "name": function["name"],
        "description": function.get("description", ""),
        "input_schema": function.get("parameters") or {"type": "object", "properties": {}},
    }


def _tool_id(raw: str) -> str:
    return _TOOL_ID.sub("_", raw) or "call"


def _tool_input(arguments: str) -> dict:
    try:
        value = json.loads(arguments) if arguments else {}
    except ValueError:  # a cut-off call; its result already says so
        return {}
    return value if isinstance(value, dict) else {}


def to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Chat-completion messages → (system text, Messages-API messages).
    System messages are joined into the system prompt, tool results become
    `tool_result` blocks in a user message (all results of one round in the
    same message), empty assistant messages are dropped and same-role
    neighbours merged."""
    system: list[str] = []
    out: list[dict] = []

    def push(role: str, blocks: list[dict]) -> None:
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            if content:
                system.append(content)
        elif role == "user":
            push("user", [{"type": "text", "text": content}] if content else [])
        elif role == "tool":
            push(
                "user",
                [{"type": "tool_result", "tool_use_id": _tool_id(message.get("tool_call_id") or ""), "content": content or "(empty)"}],
            )
        elif role == "assistant":
            if message.get("provider_content"):
                push("assistant", list(message["provider_content"]))
                continue
            blocks: list[dict] = [{"type": "text", "text": content}] if content else []
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": _tool_id(str(call.get("id", ""))),
                        "name": function.get("name", ""),
                        "input": _tool_input(function.get("arguments", "")),
                    }
                )
            push("assistant", blocks)
    while out and out[0]["role"] != "user":  # the API wants a user message first
        out.pop(0)
    return "\n\n".join(system), out
