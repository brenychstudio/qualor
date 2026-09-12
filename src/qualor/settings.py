"""Explicit local/hosted configuration; secret fields are never serialized."""

import secrets
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

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
    qualor_security_mode: Literal["LOCAL", "HOSTED_DEMO"] = "LOCAL"
    qualor_origin_auth: SecretStr | None = Field(default=None, exclude=True, repr=False)
    qualor_hosted_live_enabled: bool = False
    qualor_demo_profile_path: Path | None = Field(default=None, exclude=True, repr=False)
    qualor_gateway_id: str | None = Field(default=None, exclude=True, repr=False)
    qualor_max_concurrent_live_runs: Literal[1] = 1
    qualor_live_max_runs: int = Field(default=5, ge=1, le=100)
    qualor_live_cooldown_seconds: int = Field(default=60, ge=0, le=86400)

    @model_validator(mode="after")
    def hosted_boundary(self):
        if self.qualor_security_mode == "HOSTED_DEMO":
            if self.qualor_origin_auth is None or not (
                32 <= len(self.qualor_origin_auth.get_secret_value()) <= 1024
            ):
                raise ValueError("HOSTED_DEMO requires an origin secret of 32–1024 characters")
            if self.qualor_demo_profile_path is None:
                raise ValueError("HOSTED_DEMO requires a sanitized server demo profile")
            if self.qualor_hosted_live_enabled and (
                not self.qualor_gateway_id or self.qualor_read_only_demo
            ):
                raise ValueError("Hosted LIVE requires a server gateway and write access")
        elif self.qualor_hosted_live_enabled:
            raise ValueError("Hosted LIVE requires HOSTED_DEMO security")
        return self

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
