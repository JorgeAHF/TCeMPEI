import os
from functools import lru_cache

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://cempei:cempei@localhost:5432/cempei")
    data_root: str = os.getenv("DATA_ROOT", "/data")
    app_env: str = os.getenv("APP_ENV", "development")
    algorithm_version: str = "v1.0"
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    refresh_token_expire_minutes: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))
    allow_sqlite_for_tests: bool = os.getenv("ALLOW_SQLITE_FOR_TESTS", "false").lower() == "true"

    class Config:
        env_file = ".env"

    @validator("database_url")
    def validate_database_url(cls, value: str, values: dict) -> str:
        # Runtime policy: app flows must use PostgreSQL; SQLite only allowed in explicit test mode.
        # `database_url` may be validated before sibling fields; fallback to env vars.
        app_env = values.get("app_env") or os.getenv("APP_ENV", "development")
        allow_sqlite = values.get("allow_sqlite_for_tests")
        if allow_sqlite is None:
            allow_sqlite = os.getenv("ALLOW_SQLITE_FOR_TESTS", "false").lower() == "true"
        if value.startswith("sqlite"):
            if app_env == "test" and allow_sqlite:
                return value
            raise ValueError("DATABASE_URL must point to PostgreSQL in non-test environments.")
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL must use postgresql:// or postgresql+driver://")
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()
