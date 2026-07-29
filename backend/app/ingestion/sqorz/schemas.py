"""Schema for the `my.sqorz.com` transponder history response.

Only the fields `normalizer.py` actually reads are made required/typed here;
everything else is left as free-form extra so unrelated upstream additions
don't break ingestion. The point of this model is purely to turn a malformed
or reshaped upstream response into one clear validation error at the fetch
boundary, instead of an obscure `KeyError`/`TypeError` deep inside
`normalize_snapshot`.
"""

from pydantic import BaseModel, ConfigDict


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="allow")


class TrackViewLoopRef(_Lenient):
    loopId: str


class TrackViewPayload(_Lenient):
    trackViewId: str
    trackViewName: str | None = None
    circuit: bool = False
    trackViewLoops: list[TrackViewLoopRef] = []


class TrackLoopPayload(_Lenient):
    loopId: str
    loopName: str | None = None
    distance: float | None = None


class TrackPayload(_Lenient):
    trackId: str
    trackName: str | None = None
    trackType: str | None = None
    validationMethod: str | None = None
    trackEnabled: bool = True
    trackGate: bool = False
    trackStartFrom: str | None = None
    trackLoops: list[TrackLoopPayload] = []
    trackViews: list[TrackViewPayload] = []


class EventClassPayload(_Lenient):
    classCode: str | None = None
    className: str | None = None
    classType: str | None = None


class TrainingLapPayload(_Lenient):
    lapId: str
    trackId: str | None = None
    classCode: str | None = None
    startTime: int
    lapTimes: list[int | None] = []
    fromStart: bool = True
    startNumber: int | None = None


class MemberPayload(_Lenient):
    transponder: str | None = None
    classCode: str | None = None
    trainingLaps: list[TrainingLapPayload] = []


class TrainingDetail(_Lenient):
    eventId: str
    eventName: str | None = None
    eventDate: str
    sportType: str | None = None
    startTimestamp: str | None = None
    endTimestamp: str | None = None
    classes: list[EventClassPayload] = []
    tracks: list[TrackPayload] = []
    members: list[MemberPayload] = []


class EventTrainingDetailEntry(_Lenient):
    accountId: str | None = None
    accountName: str | None = None
    trainingDetail: TrainingDetail


class SqorzHistoryPayload(_Lenient):
    """Top-level shape of a `GET /{transponderCode}` response."""

    transponderCode: str | None = None
    eventTrainingDetails: list[EventTrainingDetailEntry] = []
