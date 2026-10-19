"""Import every model module so they register on `Base.metadata` — used by
Alembic autogenerate and by `Base.metadata.create_all` in tests/dev seeding.
"""

from app.athletes.models import Athlete, AthleteMetric, CoachAthlete  # noqa: F401
from app.auth.models import User  # noqa: F401
from app.clubs.models import Club, ClubMembership  # noqa: F401
from app.connections.models import (  # noqa: F401
    DataSourceConnection,
    IngestionRun,
    RawSnapshot,
    TransponderAssignment,
)
from app.training.models import (  # noqa: F401
    EventClass,
    EventTrack,
    LapSegmentTime,
    Track,
    TrackLoop,
    TrackView,
    TrackViewLoop,
    TrainingEvent,
    TrainingLap,
)
