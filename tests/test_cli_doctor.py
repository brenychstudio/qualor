import socket
from pathlib import Path

import boto3.session
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    """A provider/client or network connection during doctor must fail the test."""

    def deny_network(*args, **kwargs):
        raise AssertionError("Doctor must work offline")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(boto3.session.Session, "client", deny_network)
    monkeypatch.delenv("QUALOR_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("QUALOR_ENV", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)


def test_doctor_reports_verified_bootstrap_offline_from_any_directory(monkeypatch, tmp_path):
    from qualor.cli import app

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        "QUALOR",
        "PHASE=bootstrap",
        "PYTHON=PASS",
        "CANONICAL=PASS",
        "LIVE_MODE=DISABLED",
        "PAID_AWS_CALLS=DISABLED",
    ]


@pytest.mark.parametrize("content", [None, b"changed canonical bytes"])
def test_doctor_blocks_missing_or_changed_canonical(monkeypatch, content):
    from qualor.cli import app

    original_read = Path.read_bytes

    def read_candidate(path):
        if path.name == "00_CANONICAL_BRIEF_UA.md":
            if content is None:
                raise FileNotFoundError
            return content
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_candidate)
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "CANONICAL=BLOCKED" in result.output


def test_doctor_blocks_incompatible_python(monkeypatch):
    import qualor.cli as cli

    monkeypatch.setattr(cli.sys, "version_info", (3, 11, 0))
    result = CliRunner().invoke(cli.app, ["doctor"])
    assert result.exit_code == 1
    assert "PYTHON=BLOCKED" in result.output


def test_doctor_rejects_live_enablement(monkeypatch):
    from qualor.cli import app

    monkeypatch.setenv("QUALOR_LIVE_ENABLED", "true")
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "CONFIGURATION=BLOCKED" in result.output
    assert "LIVE_MODE=DISABLED" in result.output


def test_settings_default_to_safe_bootstrap_configuration():
    from qualor.settings import Settings

    settings = Settings(_env_file=None)
    assert settings.qualor_env == "development"
    assert settings.qualor_live_enabled is False
    assert settings.aws_region == "us-east-1"


def test_settings_read_nonsecret_environment(monkeypatch):
    from qualor.settings import Settings

    monkeypatch.setenv("QUALOR_ENV", "test")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    settings = Settings(_env_file=None)
    assert settings.qualor_env == "test"
    assert settings.aws_region == "eu-west-1"


def test_settings_refuse_live_mode(monkeypatch):
    from qualor.settings import Settings

    monkeypatch.setenv("QUALOR_LIVE_ENABLED", "true")
    with pytest.raises(ValidationError, match="Live mode is disabled during bootstrap"):
        Settings(_env_file=None)
