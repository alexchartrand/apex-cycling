"""Operator commands for the Strava webhook, run once on the server:

    python -m app.ingestion.strava.cli subscribe     # ask Strava to push events here
    python -m app.ingestion.strava.cli status        # show the current subscription
    python -m app.ingestion.strava.cli unsubscribe   # remove it

Needs STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET and STRAVA_WEBHOOK_VERIFY_TOKEN
set and the app reachable at APP_BASE_URL (Strava calls the callback to check
it before accepting). Afterwards put the printed id in
STRAVA_WEBHOOK_SUBSCRIPTION_ID so the endpoint only accepts that subscription.
There is one subscription per Strava application.
"""

import argparse
import sys

import httpx

from app.core.config import API_PREFIX, get_settings


def _credentials() -> dict[str, str]:
    settings = get_settings()
    if not (settings.strava_client_id and settings.strava_client_secret):
        raise SystemExit("Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET first.")
    return {"client_id": settings.strava_client_id, "client_secret": settings.strava_client_secret}


def _url() -> str:
    return f"{get_settings().strava_base_url.rstrip('/')}/api/v3/push_subscriptions"


def _subscribe() -> int:
    settings = get_settings()
    if not settings.strava_webhook_verify_token:
        raise SystemExit("Set STRAVA_WEBHOOK_VERIFY_TOKEN (any long random string) first.")
    callback = f"{settings.app_base_url.rstrip('/')}{API_PREFIX}/strava/webhook"
    response = httpx.post(
        _url(),
        data={**_credentials(), "callback_url": callback, "verify_token": settings.strava_webhook_verify_token},
        timeout=30,
    )
    if response.status_code >= 400:
        print(f"Strava refused the subscription ({response.status_code}): {response.text}", file=sys.stderr)
        return 1
    print(f"Subscribed {callback}. Set STRAVA_WEBHOOK_SUBSCRIPTION_ID={response.json()['id']} and restart the backend.")
    return 0


def _status() -> int:
    response = httpx.get(_url(), params=_credentials(), timeout=30)
    response.raise_for_status()
    print(response.json() or "No subscription.")
    return 0


def _unsubscribe() -> int:
    subscriptions = httpx.get(_url(), params=_credentials(), timeout=30)
    subscriptions.raise_for_status()
    for subscription in subscriptions.json():
        httpx.delete(f"{_url()}/{subscription['id']}", params=_credentials(), timeout=30).raise_for_status()
        print(f"Removed subscription {subscription['id']}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ingestion.strava.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("subscribe", "status", "unsubscribe"):
        commands.add_parser(name)
    command = parser.parse_args().command
    return {"subscribe": _subscribe, "status": _status, "unsubscribe": _unsubscribe}[command]()


if __name__ == "__main__":
    raise SystemExit(main())
