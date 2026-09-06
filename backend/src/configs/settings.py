"""Process settings from environment variables.

Source of truth is the process environment (`RAGLAB_*`), as set by Docker Compose
or the shell. An optional local `.env` is loaded only when the file exists
(developer convenience); it never overrides real env vars.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _optional_env_file() -> Path | None:
    """Return a `.env` path if present. Docker images do not ship one."""
    candidates = (
        Path.cwd() / ".env",
        # Editable / local layout: .../backend/src/configs/settings.py → backend/.env
        Path(__file__).resolve().parents[2] / ".env",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


_ENV_FILE = _optional_env_file()


class Settings(BaseSettings):
    """Runtime configuration for the API process."""

    model_config = SettingsConfigDict(
        env_prefix="RAGLAB_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/raglab"
    database_enabled: bool = True
    upload_dir: str = "./data/uploads"
    custom_plugin_dir: str = "./data/plugins"
    cors_origins: str = "http://localhost:6650"
    api_prefix: str = "/api/v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
