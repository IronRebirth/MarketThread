from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "MarketThread"
    app_env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = (
        "postgresql+psycopg://marketthread:change-me@localhost:5433/marketthread"
    )

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = Field(
        default="marketthread-development-secret-key-32",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"

    cors_allowed_origins: str = "http://localhost:3000,http://localhost:3001"

    market_data_api_key: str | None = None
    market_data_base_url: str | None = None

    news_api_key: str | None = None
    news_api_base_url: str = "https://newsapi.org"

    llm_api_key: str | None = None
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-5.6-luna"
    llm_timeout: float = 30.0

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_timeout: float = 10.0
    smtp_use_tls: bool = True

    sentry_dsn: str | None = None
    admin_emails: str = ""

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256.")
        return value

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()
