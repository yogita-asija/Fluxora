from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and .env for local runs)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OrderFlow API"
    app_version: str = "0.2.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # Required: there are deliberately no defaults so credentials are never hardcoded.
    database_url: str
    jwt_secret_key: str

    # Authentication
    jwt_issuer: str = "orderflow"
    access_token_expire_minutes: int = 30
    login_max_attempts: int = 5  # failed logins per account before a temporary lockout
    login_window_seconds: int = 900

    # Backing store for the login throttle. Without it an in-process store is used
    # (fine for one process; with several API replicas use Redis).
    redis_url: str | None = None
    # Wired up in later phases; optional so the foundation runs without them.
    rabbitmq_url: str | None = None
    kafka_bootstrap_servers: str | None = None

    # Comma-separated in the environment, e.g. "http://localhost:5173,http://localhost:8080".
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def jwt_secret_must_be_strong(cls, value: str) -> str:
        if len(value) < MIN_JWT_SECRET_LENGTH or value.lower().startswith("change-me"):
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters and not a "
                "placeholder. Generate one with: python scripts/init_env.py"
            )
        return value

    @field_validator("access_token_expire_minutes", "login_max_attempts", "login_window_seconds")
    @classmethod
    def must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least 1")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
