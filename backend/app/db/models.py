"""Import every model module so they register on `Base.metadata` — used by
Alembic autogenerate and by `Base.metadata.create_all` in tests/dev seeding.
"""

from app.activities.models import Activity, ActivityPowerCurve, ActivityStream  # noqa: F401
from app.aero.models import AeroTest  # noqa: F401
from app.athletes.models import Athlete, AthleteClub, AthleteMetric, CoachAthlete  # noqa: F401
from app.auth.models import PasswordResetToken, User  # noqa: F401
from app.clubs.models import Club, ClubInvite, ClubMembership, ClubSqorzAccount  # noqa: F401
from app.connections.models import (  # noqa: F401
    DataSourceConnection,
    IngestionRun,
    RawSnapshot,
    TransponderAssignment,
)
from app.equipment.models import Bike, GearSetup  # noqa: F401
from app.goals.models import Goal  # noqa: F401
from app.notifications.models import Notification, NotificationPreference, PushSubscription  # noqa: F401
from app.ops.models import WorkerHeartbeat  # noqa: F401
from app.planning.models import PlannedSession  # noqa: F401
from app.seasons.models import CalendarFeed, Competition, Season  # noqa: F401
from app.training.models import (  # noqa: F401
    EventClass,
    EventTrack,
    LapSegmentTime,
    ManualResult,
    PersonalRecord,
    SessionComment,
    SessionCommentRead,
    Track,
    TrackLoop,
    TrackView,
    TrackViewLoop,
    TrainingEvent,
    TrainingLap,
)
