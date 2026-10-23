"""The text of push notifications and emails, which leave the app and so
can't be translated by the SPA. The bell renders from the payload instead.
The user's saved language is used, French when they never chose one (the
app's own default).
"""

from dataclasses import dataclass

from app.notifications.kinds import NotificationKind

DEFAULT_LOCALE = "fr"

_EVENTS = {
    "en": {
        "f200": "flying 200",
        "lap": "flying lap",
        "500m": "500 m",
        "750m": "750 m",
        "1km": "1 km",
        "2km": "2 km pursuit",
        "3km": "3 km pursuit",
        "4km": "4 km pursuit",
    },
    "fr": {
        "f200": "200 m lancé",
        "lap": "tour lancé",
        "500m": "500 m",
        "750m": "750 m",
        "1km": "1 km",
        "2km": "poursuite 2 km",
        "3km": "poursuite 3 km",
        "4km": "poursuite 4 km",
    },
}

_TEXT = {
    "en": {
        "pr_one": "New record: {event}",
        "pr_many": "{count} new records",
        "pr_body": "{session}: {event} in {time}",
        "pr_body_many": "{session}",
        "sync_failed": "Sync failed",
        "sync_failed_body": "Transponder {code} couldn't be synced: {error}",
        "comment": "New comment from {author}",
        "comment_body": "{session}: {excerpt}",
        "coach_request": "Coaching request",
        "coach_request_coach": "{name} would like you to coach them.",
        "coach_request_athlete": "{name} would like to coach you.",
        "plan_added": "New planned session",
        "plan_added_body": "{author} planned “{title}” for {date}.",
    },
    "fr": {
        "pr_one": "Nouveau record : {event}",
        "pr_many": "{count} nouveaux records",
        "pr_body": "{session} : {event} en {time}",
        "pr_body_many": "{session}",
        "sync_failed": "Échec de la synchronisation",
        "sync_failed_body": "Le transpondeur {code} n'a pas pu être synchronisé : {error}",
        "comment": "Nouveau commentaire de {author}",
        "comment_body": "{session} : {excerpt}",
        "coach_request": "Demande d'entraînement",
        "coach_request_coach": "{name} aimerait que vous l'entraîniez.",
        "coach_request_athlete": "{name} aimerait vous entraîner.",
        "plan_added": "Nouvelle séance planifiée",
        "plan_added_body": "{author} a planifié « {title} » le {date}.",
    },
}


@dataclass(frozen=True)
class Message:
    title: str
    body: str
    url: str  # path inside the app


def format_time(ms: int) -> str:
    if ms < 60_000:
        return f"{ms / 1000:.3f} s"
    minutes, rest = divmod(ms, 60_000)
    return f"{minutes}:{rest / 1000:06.3f}"


def render(kind: str, payload: dict, locale: str | None) -> Message:
    language = locale if locale in _TEXT else DEFAULT_LOCALE
    text = _TEXT[language]

    if kind == NotificationKind.NEW_PR.value:
        items = payload.get("items") or []
        count = payload.get("count", len(items))
        first = items[0] if items else {}
        event = _EVENTS[language].get(first.get("event_key", ""), first.get("event_key", ""))
        if count > 1:
            title = text["pr_many"].format(count=count)
            body = text["pr_body_many"].format(session=payload.get("session_name", ""))
        else:
            title = text["pr_one"].format(event=event)
            body = text["pr_body"].format(
                session=payload.get("session_name", ""), event=event, time=format_time(first.get("time_ms", 0))
            )
        return Message(title, body, f"/sessions/{payload.get('external_event_id', '')}")
    if kind == NotificationKind.SYNC_FAILED.value:
        body = text["sync_failed_body"].format(code=payload.get("transponder_code", ""), error=payload.get("error", ""))
        return Message(text["sync_failed"], body, "/import")
    if kind == NotificationKind.COMMENT.value:
        title = text["comment"].format(author=payload.get("author_name", ""))
        body = text["comment_body"].format(session=payload.get("session_name", ""), excerpt=payload.get("excerpt", ""))
        return Message(title, body, f"/sessions/{payload.get('external_event_id', '')}?tab=comments")
    if kind == NotificationKind.COACH_REQUEST.value:
        key = "coach_request_coach" if payload.get("asked_role") == "athlete" else "coach_request_athlete"
        return Message(text["coach_request"], text[key].format(name=payload.get("from_name", "")), "/coach")
    if kind == NotificationKind.PLAN_ADDED.value:
        body = text["plan_added_body"].format(
            author=payload.get("author_name", ""), title=payload.get("title", ""), date=payload.get("planned_date", "")
        )
        return Message(text["plan_added"], body, "/")
    return Message(kind, "", "/")
