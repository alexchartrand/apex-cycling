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

    sqorz_base_url: str = "https://my.sqorz.com/json/training/transponder"
    sqorz_poll_interval_minutes: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
