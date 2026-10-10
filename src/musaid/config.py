"""Runtime settings, read from environment variables (and `.env` in local dev)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App database (Postgres + pgvector)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "musaid"
    postgres_user: str = "musaid"
    postgres_password: SecretStr = SecretStr("musaid")

    # Langfuse (self-hosted)
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
