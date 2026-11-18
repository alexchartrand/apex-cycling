"""What the AI coach needs from a language model, so the service never
depends on one provider's HTTP API (and tests script the replies)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    # The raw JSON text the model wrote; parsed (and refused) by the caller.
    arguments: str


@dataclass(frozen=True)
class LlmReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    # The reply hit max_tokens: tool-call arguments are then cut-off JSON.
    truncated: bool = False


# Called while a reply is being generated: ("text", the next piece of the
# answer) or ("thinking", "") when the model is reasoning before it answers.
DeltaHandler = Callable[[Literal["text", "thinking"], str], Awaitable[None]]


class LlmError(Exception):
    """The model provider failed (outage, refused key, rate limit)."""


class LlmClientPort(Protocol):
    @property
    def model(self) -> str: ...

    async def chat(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        json_mode: bool = False,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        on_delta: DeltaHandler | None = None,
    ) -> LlmReply:
        """`messages` are chat-completion messages ({role, content,
        tool_calls?, tool_call_id?, name?}); `tools` JSON-schema function
        definitions. With `on_delta` the reply is streamed through it as it
        is written; the returned reply is the same either way."""
        ...
