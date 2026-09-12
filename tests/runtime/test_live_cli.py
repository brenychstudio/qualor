from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from qualor.cli import app


def test_live_opportunity_command_requires_explicit_activation():
    result = CliRunner().invoke(app, ["run-live-opportunity", "--profile", "missing.json"])
    assert result.exit_code != 0
    assert "LIVE_REQUIRES_EXPLICIT_MODE" in result.output


def test_replay_uses_recorded_observations_without_network():
    from test_claims import source

    from qualor.runtime.providers import FetchRequest, SearchRequest
    from qualor.runtime.replay import RecordedProviders

    providers = RecordedProviders(
        searches={
            "owned": [
                {"url": "https://example.org/rules", "title": "Owned", "snippet": "discovery"}
            ]
        },
        sources=[source()],
    )
    assert providers.search(SearchRequest("owned"))[0].url == "https://example.org/rules"
    assert providers.fetch(FetchRequest("https://example.org/rules")).id == "source_owned"


def studio_profile(tmp_path: Path) -> Path:
    from qualor.decisions import DecisionFixture
    from qualor.runtime.run_models import StudioInput

    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"
    )
    fixture = DecisionFixture.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    profile = StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Controlled CLI proof",
        allowed_hosts=("example.org",),
        founder=fixture.founder,
        projects=fixture.projects,
    )
    path = tmp_path / "profile.json"
    path.write_text(profile.model_dump_json(), encoding="utf-8")
    return path


def inert_result():
    return SimpleNamespace(
        citation_urls=(),
        decision=SimpleNamespace(candidates=()),
        model_dump=lambda **kwargs: {"mode": "LIVE"},
    )


def test_live_cli_forwards_explicit_workspace_database(monkeypatch, tmp_path):
    import qualor.runtime.live_cli as live_cli

    captured = {}

    def fake_run(profile, gateway_id, *, diagnostic=False, workspace_database=None):
        captured.update(
            profile=profile,
            gateway_id=gateway_id,
            diagnostic=diagnostic,
            workspace_database=workspace_database,
        )
        return inert_result(), {}

    monkeypatch.setattr(live_cli, "run_command", fake_run)
    monkeypatch.setattr(live_cli, "summary", lambda result, metrics: {})
    database = tmp_path / "workspace.db"

    outcome = CliRunner().invoke(
        app,
        [
            "run-live-opportunity",
            "--profile",
            str(studio_profile(tmp_path)),
            "--mode",
            "LIVE",
            "--gateway-id",
            "gateway-controlled",
            "--workspace-database",
            str(database),
        ],
    )

    assert outcome.exit_code == 0
    assert captured["workspace_database"] == database


def test_run_command_verifies_requested_workspace_capture_after_runtime_returns(
    monkeypatch, tmp_path
):
    import qualor.runtime.live_cli as live_cli

    verified = []

    class Capture:
        def require_persisted(self):
            verified.append(True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_cli, "workspace_run_capture", lambda *args, **kwargs: Capture())
    monkeypatch.setattr(
        live_cli,
        "execute_live",
        lambda *args, **kwargs: (inert_result(), {"budget": {}}),
    )

    live_cli.run_command(
        studio_profile(tmp_path),
        "gateway-controlled",
        workspace_database=tmp_path / "workspace.db",
    )

    assert verified == [True]


def test_run_command_fails_closed_when_requested_workspace_capture_failed(
    monkeypatch, tmp_path
):
    import qualor.runtime.live_cli as live_cli

    class Capture:
        def require_persisted(self):
            raise RuntimeError("workspace persistence failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_cli, "workspace_run_capture", lambda *args, **kwargs: Capture())
    monkeypatch.setattr(
        live_cli,
        "execute_live",
        lambda *args, **kwargs: (inert_result(), {"budget": {}}),
    )

    with pytest.raises(RuntimeError, match="workspace persistence failed"):
        live_cli.run_command(
            studio_profile(tmp_path),
            "gateway-controlled",
            workspace_database=tmp_path / "workspace.db",
        )


def test_execute_live_records_bounded_setup_failure(monkeypatch, tmp_path):
    import qualor.runtime.live_cli as live_cli
    import qualor.runtime.search_transport as search_transport
    from qualor.runtime.run_models import StudioInput

    inputs = StudioInput.model_validate_json(studio_profile(tmp_path).read_bytes())
    failures = []

    class Capture:
        def run_failed(self, **kwargs):
            failures.append(kwargs)

    @contextmanager
    def broken_transport(**kwargs):
        del kwargs
        raise RuntimeError("controlled gateway setup failure")
        yield

    monkeypatch.setattr(search_transport, "open_gateway_transport", broken_transport)

    with pytest.raises(RuntimeError, match="controlled gateway setup failure"):
        live_cli.execute_live(inputs, "gateway-controlled", sink=Capture())

    assert failures == [
        {
            "termination_reason": "PROVIDER_DISCONNECTED",
            "provider_state": "DISCONNECTED_LIVE_PROVIDER",
        }
    ]


def test_run_command_verifies_failed_capture_before_reraising_runtime_error(
    monkeypatch, tmp_path
):
    import qualor.runtime.live_cli as live_cli

    verified = []

    class Capture:
        def require_persisted(self):
            verified.append(True)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_cli, "workspace_run_capture", lambda *args, **kwargs: Capture())
    monkeypatch.setattr(
        live_cli,
        "execute_live",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("controlled setup failure")),
    )

    with pytest.raises(RuntimeError, match="controlled setup failure"):
        live_cli.run_command(
            studio_profile(tmp_path),
            "gateway-controlled",
            workspace_database=tmp_path / "workspace.db",
        )

    assert verified == [True]


def test_run_command_surfaces_failed_failure_telemetry_persistence(monkeypatch, tmp_path):
    import qualor.runtime.live_cli as live_cli

    class Capture:
        def require_persisted(self):
            raise RuntimeError("workspace persistence failed")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(live_cli, "workspace_run_capture", lambda *args, **kwargs: Capture())
    monkeypatch.setattr(
        live_cli,
        "execute_live",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("controlled setup failure")),
    )

    with pytest.raises(RuntimeError, match="workspace persistence failed"):
        live_cli.run_command(
            studio_profile(tmp_path),
            "gateway-controlled",
            workspace_database=tmp_path / "workspace.db",
        )
