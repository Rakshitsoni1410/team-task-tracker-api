from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "development-only-change-me"
PLACEHOLDER_SECRETS = {DEFAULT_JWT_SECRET, "replace-this-with-a-long-random-secret"}
RELAXED_ENVIRONMENTS = {"development", "test"}


class Settings(BaseSettings):
    app_name: str = "Team Task Tracker API"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://tasktracker:tasktracker@localhost:5432/tasktracker"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _require_real_secret_outside_development(self) -> "Settings":
        """Fail fast instead of silently signing tokens with a well-known secret."""
        if self.app_env.lower() not in RELAXED_ENVIRONMENTS:
            if self.jwt_secret in PLACEHOLDER_SECRETS or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be a random value of at least 32 characters "
                    f"when APP_ENV is '{self.app_env}'"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
