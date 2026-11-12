"""What can be notified, and through which channels by default."""

from enum import Enum


class NotificationKind(str, Enum):
    NEW_PR = "new_pr"
    SYNC_FAILED = "sync_failed"
    COMMENT = "comment"
    COACH_REQUEST = "coach_request"
    PLAN_ADDED = "plan_added"
    AI_REPORT = "ai_report"
    AI_PROPOSAL = "ai_proposal"


CHANNELS = ("in_app", "push", "email")

# Everything is on, except email for records: after each session it would be
# the noisiest message the app sends, and the bell and push already say it.
# Same for the AI coach's proposals (its weekly report does go by email).
DEFAULT_PREFERENCES: dict[str, dict[str, bool]] = {
    kind.value: {"in_app": True, "push": True, "email": kind not in (NotificationKind.NEW_PR, NotificationKind.AI_PROPOSAL)}
    for kind in NotificationKind
}


def effective_preferences(overrides: dict | None) -> dict[str, dict[str, bool]]:
    """Defaults with the user's stored overrides applied; unknown kinds and
    channels in the stored value are ignored.
    """
    merged = {kind: dict(channels) for kind, channels in DEFAULT_PREFERENCES.items()}
    for kind, channels in (overrides or {}).items():
        if kind in merged and isinstance(channels, dict):
            for channel, enabled in channels.items():
                if channel in CHANNELS and isinstance(enabled, bool):
                    merged[kind][channel] = enabled
    return merged
