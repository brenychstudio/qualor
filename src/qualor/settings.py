"""Non-secret bootstrap configuration; live execution is unavailable."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qualor_env: str = "development"
    qualor_live_enabled: bool = False
    aws_region: str = "us-east-1"
    database_path: Path = Path(".qualor/local/qualor.db")

    @field_validator("qualor_live_enabled")
    @classmethod
    def reject_live_mode(cls, value: bool) -> bool:
        if value:
            raise ValueError("Live mode is disabled during bootstrap")
        return value
