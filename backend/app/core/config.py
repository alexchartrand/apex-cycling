from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Every backend route is mounted under this prefix (see app/main.py), so the
# edge proxy only has to forward one path to the backend and the SPA can own
# every other URL.
API_PREFIX = "/api"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://apex_cycling:apex_cycling@localhost:5432/apex_cycling"

    jwt_secret: str = "dev-only-secret-change-me-before-any-real-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    # Session length when the user does NOT opt into "keep me logged in".
    refresh_token_expire_hours_default: int = 12

    cookie_secure: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Public URL of the SPA, for links in emails and admin-generated
    # password-reset links.
    app_base_url: str = "http://localhost:5173"
    password_reset_expire_minutes: int = 60
    # Admin-generated links are handed over by a person, so they live longer.
    password_reset_admin_expire_hours: int = 72

    # Optional outgoing email (app/core/mail.py). Without SMTP_HOST and
    # SMTP_FROM, email is off and password resets go through admin links.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    # "starttls" (port 587), "ssl" (implicit TLS, port 465) or "none".
    smtp_security: str = "starttls"

    # Encrypts third-party credentials at rest (app/core/crypto.py): one Fernet
    # key, or several comma-separated for rotation (the first encrypts, all
    # decrypt). The default is public — production must set its own, and
    # docker-compose.prod.yml refuses to start without one.
    data_encryption_key: str = "H4tZyMCFh158yS6kTE9PcevpCeYVP7PZo57crhYEBSE="

    # Where original activity files (FIT/TCX/GPX) are kept; an uploads volume
    # in docker (app/activities/storage.py).
    uploads_dir: str = "/data/uploads"
    # Largest single FIT/TCX/GPX file accepted (a 10-hour ride is ~2 MB).
    max_activity_file_bytes: int = 15 * 1024 * 1024

    # Intervals.icu sync (app/ingestion/intervals): the worker looks for new
    # activities this often; a first sync reaches back `backfill_days`, and a
    # run downloads at most `max_downloads_per_run` files so a long history
    # arrives over several runs instead of hammering the API.
    intervals_base_url: str = "https://intervals.icu/api/v1"
    intervals_poll_interval_minutes: int = 30
    intervals_backfill_days: int = 90
    intervals_max_downloads_per_run: int = 25

    sqorz_base_url: str = "https://my.sqorz.com/json/training/transponder"
    sqorz_poll_interval_minutes: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
