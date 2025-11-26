from functools import lru_cache
from pydantic import Field, field_validator
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
    admin_emails: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(env_prefix="PLANT_", env_file=".env", extra="ignore")

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _split_admin_emails(cls, value: str | list[str] | None) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
