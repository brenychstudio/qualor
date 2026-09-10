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


WORKSPACE_FIXTURES = Path(__file__).parent / "fixtures/workspace"
W01 = WORKSPACE_FIXTURES / "W01_DECISION_TO_DRAFT_PACK.json"


def seed_command(tmp_path, monkeypatch, argument=None, **environment):
    """Invoke the development-only seed boundary against a temporary database."""
    from qualor.cli import app

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "workspace.db"))
    for name, value in environment.items():
        monkeypatch.setenv(name.upper(), value)
    return CliRunner().invoke(app, ["seed-workspace-fixture", str(argument or W01)])


def test_seed_accepts_an_owned_fixture_and_reports_only_bounded_facts(tmp_path, monkeypatch):
    result = seed_command(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "MODE=FIXTURE" in result.output
    # The opportunity identity is derived by the contract, never taken from the file.
    assert "OPPORTUNITY=opp_" in result.output
    assert "RECOMMENDATION=APPLY" in result.output
    assert (tmp_path / "workspace.db").exists()
    # The command reports what it recorded, never credentials, paths or raw source text.
    for forbidden in ("token", "secret", "password", "arn:", "http://", "https://"):
        assert forbidden not in result.output.lower()


def test_seed_derives_authority_from_the_engines_rather_than_the_file(tmp_path, monkeypatch):
    """The fixture supplies inputs. The deterministic engines supply the decision."""
    import json

    from qualor.persistence import Database
    from qualor.workspace import WorkspaceStore

    payload = json.loads(W01.read_text(encoding="utf-8"))
    assert "recommendation" not in payload
    assert "eligibility" not in payload

    result = seed_command(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    opportunity = next(
        line.split("=", 1)[1]
        for line in result.output.splitlines()
        if line.startswith("OPPORTUNITY=")
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        workspace = WorkspaceStore(connection).load_opportunity_workspace(opportunity, 1)
    assert workspace.decisions and workspace.decisions[0].recommendation.value == "APPLY"


def test_seed_rejects_a_fixture_that_claims_a_non_fixture_mode(tmp_path, monkeypatch):
    import json

    payload = json.loads(W01.read_text(encoding="utf-8"))
    payload["mode"] = "LIVE"
    claimed = tmp_path / "claims-live.json"
    claimed.write_text(json.dumps(payload), encoding="utf-8")
    result = seed_command(tmp_path, monkeypatch, claimed)
    assert result.exit_code == 2
    assert "FIXTURE" in result.output


def test_seed_refuses_outside_a_development_environment(tmp_path, monkeypatch):
    result = seed_command(tmp_path, monkeypatch, qualor_env="production")
    assert result.exit_code == 2
    assert "DEVELOPMENT" in result.output
    assert not (tmp_path / "workspace.db").exists()


@pytest.mark.parametrize("argument", ["missing.json", "https://example.com/fixture.json"])
def test_seed_refuses_an_unreadable_or_remote_input(tmp_path, monkeypatch, argument):
    result = seed_command(tmp_path, monkeypatch, argument)
    assert result.exit_code == 2
    assert "INVALID_FIXTURE" in result.output


def test_seed_never_opens_a_network_or_aws_client(tmp_path, monkeypatch):
    """The autouse offline guard fails this test if any provider boundary is touched."""
    assert seed_command(tmp_path, monkeypatch).exit_code == 0
