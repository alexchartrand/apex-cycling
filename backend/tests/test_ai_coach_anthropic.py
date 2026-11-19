"""The Claude client: chat-completion messages → Messages API, and a
streamed reply (thinking, text, tool call) back into an `LlmReply`. No
network: the SDK runs over a mocked transport."""

import json

import anthropic
import httpx2
import pytest

from app.coach_ai.anthropic_client import AnthropicClient, to_anthropic_messages, to_anthropic_tool
from app.coach_ai.ports import LlmError

TOOL = {"type": "function", "function": {"name": "get_plans", "description": "Plans", "parameters": {"type": "object", "properties": {}}}}


def test_converts_a_tool_exchange():
    system, messages = to_anthropic_messages(
        [
            {"role": "system", "content": "You coach."},
            {"role": "assistant", "content": "orphan before the first user message"},
            {"role": "user", "content": "Plan my week"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "a.1", "type": "function", "function": {"name": "get_plans", "arguments": '{"days": 7}'}},
                    {"id": "a2", "type": "function", "function": {"name": "get_plans", "arguments": '{"days": '}},
                ],
            },
            {"role": "tool", "tool_call_id": "a.1", "name": "get_plans", "content": "[]"},
            {"role": "tool", "tool_call_id": "a2", "name": "get_plans", "content": ""},
            {"role": "assistant", "content": ""},  # a proposal card: dropped
            {"role": "user", "content": "Thanks"},
        ]
    )
    assert system == "You coach."
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    calls = messages[1]["content"]
    assert calls[0] == {"type": "tool_use", "id": "a_1", "name": "get_plans", "input": {"days": 7}}
    assert calls[1]["input"] == {}  # cut-off arguments
    results = messages[2]["content"]
    assert [b["type"] for b in results] == ["tool_result", "tool_result", "text"]
    assert results[0]["tool_use_id"] == "a_1" and results[1]["content"] == "(empty)"


def test_provider_content_is_sent_back_as_is():
    blocks = [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "tool_use", "id": "t1", "name": "x", "input": {}}]
    _, messages = to_anthropic_messages(
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "", "tool_calls": [], "provider_content": blocks}]
    )
    assert messages[1]["content"] == blocks


def test_tool_definition():
    assert to_anthropic_tool(TOOL) == {"name": "get_plans", "description": "Plans", "input_schema": {"type": "object", "properties": {}}}


def _sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _stream(stop_reason: str = "tool_use") -> list[dict]:
    return [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [],
                "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 100, "cache_read_input_tokens": 900, "cache_creation_input_tokens": 0, "output_tokens": 1},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "sig"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Let me "}},
        {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "look."}},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "toolu_1", "name": "get_plans", "input": {}}},
        {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '{"days": 7}'}},
        {"type": "content_block_stop", "index": 2},
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 50}},
        {"type": "message_stop"},
    ]


def _client(handler) -> AnthropicClient:
    sdk = anthropic.AsyncAnthropic(
        api_key="k", max_retries=0, http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    )
    return AnthropicClient(api_key="k", model="claude-sonnet-5-5", effort="medium", client=sdk)


async def test_streams_a_tool_call():
    seen: dict = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(_stream()))

    deltas: list[tuple[str, str]] = []

    async def on_delta(kind, text):
        deltas.append((kind, text))

    reply = await _client(handler).chat(
        [{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}],
        tools=[TOOL],
        tool_choice="none",
        max_tokens=500,
        on_delta=on_delta,
    )
    body = seen["body"]
    assert body["system"] == "S" and body["max_tokens"] == 500 and "temperature" not in body
    assert body["tool_choice"] == {"type": "none"} and body["tools"][0]["name"] == "get_plans"
    assert body["output_config"] == {"effort": "medium"} and body["thinking"]["type"] == "adaptive"
    assert body["fallbacks"] == "default" and "server-side-fallback" in seen["beta"]
    assert deltas == [("thinking", ""), ("text", "Let me "), ("text", "look.")]
    assert reply.content == "Let me look."
    assert reply.tool_calls[0].name == "get_plans" and json.loads(reply.tool_calls[0].arguments) == {"days": 7}
    assert reply.prompt_tokens == 1000 and reply.completion_tokens == 50 and not reply.truncated
    assert reply.cache_read_tokens == 900 and reply.cache_write_tokens == 0
    assert [b["type"] for b in reply.provider_content] == ["thinking", "text", "tool_use"]
    assert reply.provider_content[0]["signature"] == "sig"


async def test_cut_off_and_refusal():
    def cut(request):
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(_stream("max_tokens")))

    assert (await _client(cut).chat([{"role": "user", "content": "hi"}])).truncated

    def refused(request):
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(_stream("refusal")))

    with pytest.raises(LlmError):
        await _client(refused).chat([{"role": "user", "content": "hi"}])


async def test_errors_become_llm_errors():
    def refused_key(request):
        return httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}})

    with pytest.raises(LlmError, match="API key"):
        await _client(refused_key).chat([{"role": "user", "content": "hi"}])
    with pytest.raises(LlmError):
        await AnthropicClient(api_key="", model="m").chat([{"role": "user", "content": "hi"}])


def test_cost_prices_cache_tokens_per_model():
    from app.coach_ai.access import cost_usd

    # 1M input of which 0.9M cache reads and 0.05M writes, 0.1M output, at Sonnet 5.5's rates.
    assert cost_usd("claude-sonnet-5-5", 1_000_000, 100_000, 900_000, 50_000) == pytest.approx(
        0.05 * 2.0 + 0.9 * 0.10 + 0.05 * 2.50 + 0.1 * 10.0
    )
    # Mistral rows keep Mistral's prices whatever the current provider.
    assert cost_usd("mistral-large-4", 1_000_000, 1_000_000) == pytest.approx(0.7 + 2.1)
