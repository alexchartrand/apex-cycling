"""Rate limits must key on the real client behind the edge proxy, and a client
must not be able to pick its own bucket by sending X-Forwarded-For."""

import pytest
from httpx import ASGITransport, AsyncClient
from slowapi.util import get_remote_address
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

EDGE_NETWORK = "172.28.0.0/24"


async def whoami(request: Request) -> PlainTextResponse:
    return PlainTextResponse(get_remote_address(request))


def client_for(peer: str) -> AsyncClient:
    app = ProxyHeadersMiddleware(Starlette(routes=[Route("/", whoami)]), trusted_hosts=EDGE_NETWORK)
    return AsyncClient(transport=ASGITransport(app=app, client=(peer, 5000)), base_url="http://test")


@pytest.mark.parametrize(
    ("peer", "forwarded", "expected"),
    [
        # Caddy (the trusted edge) reports the browser's address.
        ("172.28.0.10", "203.0.113.7", "203.0.113.7"),
        # The browser prepended a fake hop; the one Caddy appended wins.
        ("172.28.0.10", "198.51.100.1, 203.0.113.7", "203.0.113.7"),
        # Not the edge: X-Forwarded-For is ignored entirely.
        ("10.0.0.5", "198.51.100.1", "10.0.0.5"),
        # Edge reached without the header: its own address.
        ("172.28.0.10", None, "172.28.0.10"),
    ],
)
async def test_client_address(peer, forwarded, expected):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    async with client_for(peer) as client:
        assert (await client.get("/", headers=headers)).text == expected
