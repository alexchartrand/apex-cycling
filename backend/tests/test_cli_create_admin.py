from sqlalchemy import select

from app.athletes.models import Athlete
from app.auth.cli import create_admin
from app.auth.models import User
from app.core.security import verify_password


async def test_create_admin_makes_admin_with_athlete_profile(db_session):
    async with db_session() as db:
        user, created = await create_admin(db, "root@example.com", "Correct-Horse-9", "Root")
        assert created
        assert user.is_platform_admin
        assert verify_password("Correct-Horse-9", user.hashed_password)
        athlete = await db.scalar(select(Athlete).where(Athlete.user_id == user.id))
        assert athlete is not None and athlete.display_name == "Root"


async def test_create_admin_promotes_existing_account_without_touching_password(db_session):
    async with db_session() as db:
        user, _ = await create_admin(db, "a@example.com", "Correct-Horse-9", "A")
        user.is_platform_admin = False
        await db.commit()

        again, created = await create_admin(db, "a@example.com", "Other-Passw0rd!", "A")
        assert not created
        assert again.is_platform_admin
        assert verify_password("Correct-Horse-9", again.hashed_password)
        assert len((await db.scalars(select(User))).all()) == 1
