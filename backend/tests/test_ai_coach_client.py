"""The Mistral client against a mocked API: request shape, tool calls, retries, errors."""

import json

import httpx
import pytest

from app.coach_ai.client import MistralClient
from app.coach_ai.ports import LlmError


def _client(handler) -> MistralClient:
    return MistralClient(api_key="k", model="mistral-large-latest", transport=httpx.MockTransport(handler))


async def test_sends_tools_and_reads_tool_calls_and_usage():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "mistral-large-2512",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{"id": "abc123XYZ", "function": {"name": "get_plans", "arguments": {"start": "2026-11-12"}}}],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 30},
            },
        )

    tools = [{"type": "function", "function": {"name": "get_plans", "parameters": {"type": "object"}}}]
    reply = await _client(handler).chat([{"role": "user", "content": "hi"}], tools=tools, max_tokens=500)
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "mistral-large-latest" and seen["body"]["tool_choice"] == "auto"
    assert seen["body"]["tools"] == tools and seen["body"]["max_tokens"] == 500
    assert reply.content is None and reply.model == "mistral-large-2512"
    assert reply.tool_calls[0].name == "get_plans" and json.loads(reply.tool_calls[0].arguments) == {"start": "2026-11-12"}
    assert (reply.prompt_tokens, reply.completion_tokens) == (1200, 30)


async def test_retries_a_rate_limit_then_reads_chunked_text(monkeypatch):
    monkeypatch.setattr("app.coach_ai.client.asyncio.sleep", _no_sleep)
    answers = iter(
        [
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": [{"type": "thinking", "thinking": []}, {"type": "text", "text": "Bonjour"}]}}]},
            ),
        ]
    )
    reply = await _client(lambda request: next(answers)).chat([{"role": "user", "content": "salut"}])
    assert reply.content == "Bonjour" and reply.tool_calls == []


async def test_a_refused_key_or_outage_is_an_llm_error(monkeypatch):
    monkeypatch.setattr("app.coach_ai.client.asyncio.sleep", _no_sleep)
    with pytest.raises(LlmError, match="refused"):
        await _client(lambda r: httpx.Response(401)).chat([{"role": "user", "content": "x"}])
    with pytest.raises(LlmError, match="HTTP 503"):
        await _client(lambda r: httpx.Response(503)).chat([{"role": "user", "content": "x"}])
    with pytest.raises(LlmError, match="isn.t configured"):
        await MistralClient(api_key="", model="m").chat([])


async def _no_sleep(_seconds):
    return None
