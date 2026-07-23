from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://track_trainer:track_trainer@localhost:5432/track_trainer"

    jwt_secret: str = "dev-only-secret-change-me-before-any-real-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    sqorz_base_url: str = "https://my.sqorz.com/json/training/transponder"
    sqorz_poll_interval_minutes: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
