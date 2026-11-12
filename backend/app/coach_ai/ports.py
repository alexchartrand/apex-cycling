"""What the AI coach needs from a language model, so the service never
depends on one provider's HTTP API (and tests script the replies)."""

from dataclasses import dataclass, field
from typing import Protocol


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
    ) -> LlmReply:
        """`messages` are chat-completion messages ({role, content,
        tool_calls?, tool_call_id?, name?}); `tools` JSON-schema function
        definitions."""
        ...
