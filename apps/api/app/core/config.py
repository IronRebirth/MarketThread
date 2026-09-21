from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "MarketThread"
    app_env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_request_body_bytes: int = Field(default=1_048_576, gt=0, le=10_485_760)

    database_url: str = (
        "postgresql+psycopg://marketthread:change-me@localhost:5433/marketthread"
    )

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = Field(
        default="marketthread-development-secret-key-32",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "marketthread-api"
    access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)

    auth_cookie_name: str = "marketthread.access"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"

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

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.app_env.lower() not in {"production", "prod"}:
            return self

        if self.jwt_secret_key == "marketthread-development-secret-key-32":
            raise ValueError(
                "JWT_SECRET_KEY must be explicitly configured in production.",
            )

        if "change-me" in self.database_url:
            raise ValueError(
                "DATABASE_URL must not contain the development password in production.",
            )

        if "localhost" in self.cors_allowed_origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must not use localhost in production.",
            )

        if not self.auth_cookie_secure:
            raise ValueError(
                "AUTH_COOKIE_SECURE must be enabled in production.",
            )

        if self.auth_cookie_samesite.lower() == "none" and not self.auth_cookie_secure:
            raise ValueError(
                "AUTH_COOKIE_SECURE must be enabled when AUTH_COOKIE_SAMESITE is none.",
            )

        return self

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256.")
        return value

    @field_validator("auth_cookie_samesite")
    @classmethod
    def validate_auth_cookie_samesite(cls, value: str) -> str:
        normalized = value.lower()

        if normalized not in {"lax", "strict", "none"}:
            raise ValueError(
                "AUTH_COOKIE_SAMESITE must be lax, strict, or none.",
            )

        return normalized

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
