from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "Plant Automation Backend"
    environment: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./plant.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 60 * 24 * 14
    session_secret_key: str = "change-me-session"
    device_offline_seconds: int = 120

    model_config = SettingsConfigDict(env_prefix="PLANT_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
