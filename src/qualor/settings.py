"""Non-secret bootstrap configuration; live execution is unavailable."""

import secrets
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qualor_env: str = "development"
    qualor_live_enabled: bool = False
    aws_region: str = "us-east-1"
    database_path: Path = Path(".qualor/local/qualor.db")
    qualor_allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
    )
    qualor_read_only_demo: bool = False

    @field_validator("qualor_allowed_origins")
    @classmethod
    def local_browser_origins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for origin in value:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parts.username
                or parts.password
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError("Allowed origins must be explicit local browser origins")
        return value

    @staticmethod
    def new_action_token() -> str:
        """Not a settings field: cannot be supplied by environment or serialized."""
        return secrets.token_urlsafe(32)

    @field_validator("qualor_live_enabled")
    @classmethod
    def reject_live_mode(cls, value: bool) -> bool:
        if value:
            raise ValueError("Live mode is disabled during bootstrap")
        return value
