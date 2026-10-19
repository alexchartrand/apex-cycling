import httpx
import pytest

from app.ingestion.sqorz.client import SqorzClientError, SqorzHttpClient


def _patch_transport(monkeypatch, handler):
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr("app.ingestion.sqorz.client.httpx.AsyncClient", fake_async_client)


def _valid_payload() -> dict:
    return {
        "transponderCode": "TP-1",
        "eventTrainingDetails": [
            {
                "accountId": "acc-1",
                "accountName": "TestClub",
                "trainingDetail": {
                    "eventId": "evt1",
                    "eventDate": "2026-06-05",
                    "classes": [],
                    "tracks": [],
                    "members": [],
                },
            }
        ],
    }


async def test_fetch_transponder_history_accepts_valid_payload(monkeypatch):
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=_valid_payload()))

    payload = await SqorzHttpClient().fetch_transponder_history("TP-1")

    assert payload == _valid_payload()


async def test_fetch_transponder_history_rejects_malformed_payload(monkeypatch):
    malformed = {"eventTrainingDetails": [{"trainingDetail": {"eventId": "evt1"}}]}  # missing eventDate
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json=malformed))

    with pytest.raises(SqorzClientError, match="schema validation"):
        await SqorzHttpClient().fetch_transponder_history("TP-1")


async def test_fetch_transponder_history_rejects_wrong_top_level_shape(monkeypatch):
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json={"eventTrainingDetails": "oops"}))

    with pytest.raises(SqorzClientError, match="schema validation"):
        await SqorzHttpClient().fetch_transponder_history("TP-1")
