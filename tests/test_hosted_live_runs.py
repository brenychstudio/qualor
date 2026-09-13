"""Offline hosted acceptance: real runtime/persistence with controlled providers."""

import hashlib
import json
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from qualor.api import create_app
from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.persistence import Database
from qualor.runtime.budget import BudgetLimitExceeded
from qualor.runtime.claims import ExtractedClaim
from qualor.runtime.extraction import BedrockClaimExtractor
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.mode import ProviderBoundaryError
from qualor.runtime.providers import SearchCandidate
from qualor.runtime.run_models import StudioInput
from qualor.runtime.search import AgentCoreSearchProvider
from qualor.runtime.sources import OfficialSourceFetcher
from qualor.settings import Settings
from qualor.workspace import WorkspaceStore

SECRET = "test-only-origin-value-" + "x" * 32
AUTH = {"X-QUALOR-Origin-Auth": SECRET}
URL = "https://example.org/rules"
TEXT = (
    "Organizer: Northstar Foundation. Program: Open Builders Challenge. "
    "Deadline: 2030-06-01T17:00:00Z. Projects must use Widget SDK."
)


def profile_file(tmp_path):
    now = datetime.now(UTC)
    base = dict(
        schema_version="1",
        id="demo-founder",
        version=1,
        created_at=now,
        updated_at=now,
        provenance="USER_ASSERTED",
    )
    founder = FounderProfile.model_validate(
        {
            **base,
            "country_of_residence": {"value": "PRIVATE_RESIDENCE", "provenance": "USER_ASSERTED"},
            "strategic_goals": {"value": ["PRIVATE_NOTES"], "provenance": "USER_ASSERTED"},
            "constraints": ["PRIVATE_CONSTRAINT"],
        }
    )
    project = ProjectProfile.model_validate(
        {
            **base,
            "id": "qualor-demo",
            "name": "QUALOR",
            "technology_stack": {"value": ["Python"], "provenance": "DOCUMENTED"},
        }
    )
    inputs = StudioInput(
        schema_version="1",
        sanitized=True,
        goal="IGNORED_OWNER_GOAL",
        allowed_hosts=("owner-private.example",),
        founder=founder,
        projects=(ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),),
    )
    path = tmp_path / "demo-profile.json"
    path.write_text(inputs.model_dump_json(), encoding="utf-8")
    return path


def config(tmp_path, **updates):
    return Settings(
        database_path=tmp_path / "hosted.db",
        qualor_security_mode="HOSTED_DEMO",
        qualor_origin_auth=SECRET,
        qualor_hosted_live_enabled=True,
        qualor_demo_profile_path=profile_file(tmp_path),
        qualor_gateway_id="controlled-gateway",
        qualor_live_cooldown_seconds=0,
        **updates,
    )


def test_hosted_inbox_advertises_server_owned_live_research_context(tmp_path):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        response = client.get("/api/v1/inbox", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["live_research_available"] is True
    assert response.json()["security_mode"] == "HOSTED_DEMO"


def test_hosted_read_model_preserves_server_owned_approval_authority(tmp_path, monkeypatch):
    settings = config(tmp_path)
    with TestClient(make_app(settings, ControlledRunner())) as client:
        accepted = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        done = terminal(client, accepted.json()["run_id"])
        opportunity_id = done["opportunity_id"]
        service = client.app.state.workspace
        authoritative = service.workspace(opportunity_id)
        actionable = authoritative.model_copy(
            update={
                "decision": authoritative.decision.model_copy(
                    update={
                        "primary_action": authoritative.decision.primary_action.model_copy(
                            update={"available": True, "reason": "VALID"}
                        )
                    }
                ),
                "product_state": authoritative.product_state.model_copy(
                    update={"approval_available": True}
                ),
            }
        )
        monkeypatch.setattr(service, "workspace", lambda *args, **kwargs: actionable)

        workspace = client.get(
            f"/api/v1/opportunities/{opportunity_id}/workspace", headers=AUTH
        ).json()
        inbox = client.get("/api/v1/inbox", headers=AUTH).json()

    assert workspace["decision"]["primary_action"]["available"] is True
    assert workspace["decision"]["primary_action"]["reason"] == "VALID"
    assert workspace["decision"]["primary_action"]["approval_request"] is not None
    assert workspace["product_state"]["approval_available"] is True
    assert all(item["human_action_available"] is False for item in inbox["items"])


class ControlledRunner:
    def __init__(self, *, pause=False, failure=None):
        self.pause, self.failure = pause, failure
        self.entered = threading.Event()
        self.continue_research = threading.Event()
        self.evaluated = threading.Event()
        self.finish = threading.Event()
        self.researching = threading.Event()
        self.continue_evaluation = threading.Event()
        self.calls = 0
        self.inputs = None

    def __call__(self, inputs, gateway_id, *, sink, budget):
        self.calls += 1
        self.inputs = inputs
        assert gateway_id == "controlled-gateway"
        assert budget.policy.cost_cap_usd == Decimal(".20")
        self.entered.set()
        if self.pause:
            assert self.continue_research.wait(10)
        if self.failure:
            raise self.failure

        class Search(AgentCoreSearchProvider):
            def search(self, request):
                return (SearchCandidate(URL, "Official rules", "discovery only"),)

        class Extract(BedrockClaimExtractor):
            def extract(self, source, focus):
                values = (
                    (
                        ("organizer", "Northstar Foundation", "Organizer: Northstar Foundation."),
                        ("program", "Open Builders Challenge", "Program: Open Builders Challenge."),
                    )
                    if focus == "metadata"
                    else (
                        ("deadline", "2030-06-01T17:00:00Z", "Deadline: 2030-06-01T17:00:00Z."),
                        ("required_technology", ("Widget SDK",), "Projects must use Widget SDK."),
                    )
                )
                return tuple(
                    ExtractedClaim(
                        source_id=source.id,
                        source_url=source.final_url,
                        field=field,
                        value=value,
                        excerpt=excerpt,
                        state="CANDIDATE",
                        confidence="HIGH",
                    )
                    for field, value, excerpt in values
                )

        run = OpportunityRun(
            inputs,
            mode="LIVE",
            search=Search(mode="LIVE", transport=object(), budget=budget),
            fetcher=OfficialSourceFetcher(
                mode="LIVE",
                allowed_hosts=inputs.allowed_hosts,
                budget=budget,
                resolver=lambda host: ["93.184.216.34"],
                request=lambda url, address: (200, {"content-type": "text/plain"}, TEXT.encode()),
            ),
            extractor=Extract(SimpleNamespace(budget=budget)),
            budget=budget,
            sink=sink,
            opportunity_version_resolver=sink.resolve_opportunity_version,
        )
        candidates = run.search_web("Open Builders Challenge official rules")
        fetched = run.fetch_official_source(candidates["results"][0]["candidate_id"])
        self.researching.set()
        if self.pause:
            assert self.continue_evaluation.wait(10)
        run.extract_official_claims(fetched["source_id"], "metadata")
        run.extract_official_claims(fetched["source_id"], "requirements")
        run.evaluate_current_state()
        self.evaluated.set()
        if self.pause:
            assert self.finish.wait(10)
        return run.finish(), {}


def make_app(settings, runner):
    return create_app(settings, live_runner=runner, live_resolver=lambda host: ["93.184.216.34"])


def terminal(client, run_id):
    for _ in range(300):
        response = client.get(f"/api/v1/live-runs/{run_id}", headers=AUTH)
        assert response.status_code == 200, response.text
        if response.json()["status"] in {"COMPLETED", "FAILED", "BUDGET_STOPPED"}:
            return response.json()
        time.sleep(0.01)
    pytest.fail("Controlled run did not terminate")


def test_async_live_path_persists_graph_and_survives_reconnect(tmp_path, caplog):
    settings = config(tmp_path)
    runner = ControlledRunner(pause=True)
    app = make_app(settings, runner)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/live-runs",
            headers=AUTH,
            json={"official_url": URL, "goal": "Check eligibility"},
        )
        assert response.status_code == 202, response.text
        accepted = response.json()
        assert accepted["status"] == "STARTING"
        run_id = accepted["run_id"]
        assert runner.entered.wait(5)
        busy = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        assert busy.status_code == 409
        assert busy.json() == {"code": "LIVE_RUN_BUSY"}
        runner.continue_research.set()
        assert runner.researching.wait(5)
        assert client.get(f"/api/v1/live-runs/{run_id}", headers=AUTH).json()["status"] == (
            "RESEARCHING"
        )
        runner.continue_evaluation.set()
        assert runner.evaluated.wait(5)
        status = client.get(f"/api/v1/live-runs/{run_id}", headers=AUTH).json()
        assert status["status"] == "EVALUATING"
        with Database(settings.database_path).transaction() as connection:
            assert WorkspaceStore(connection).runs.current(run_id) is None
        runner.finish.set()
        done = terminal(client, run_id)
        assert done["status"] == "COMPLETED", done
        assert done["mode"] == "LIVE"
        assert done["recommendation"] == "SKIP"
        opportunity_id = done["opportunity_id"]
        payloads = [done]
        for route in (
            "inbox",
            f"opportunities/{opportunity_id}/workspace",
            f"opportunities/{opportunity_id}/evidence",
            "runs",
        ):
            result = client.get("/api/v1/" + route, headers=AUTH)
            assert result.status_code == 200, result.text
            payloads.append(result.json())
        assert payloads[1]["items"][0]["mode"] == "LIVE"
        assert payloads[2]["mode"] == "LIVE"
        assert any(p["excerpt"] == "Deadline: 2030-06-01T17:00:00Z." for p in payloads[3]["proofs"])
        assert payloads[4]["events"]
        assert all(event["mode"] == "LIVE" for event in payloads[4]["events"])
        assert any(
            event["event_type"] == "DECISION_EVALUATED" for event in payloads[4]["events"]
        )
        serialized = json.dumps(payloads) + caplog.text + runner.inputs.model_dump_json()
        for private in (
            SECRET,
            "PRIVATE_RESIDENCE",
            "PRIVATE_NOTES",
            "PRIVATE_CONSTRAINT",
            "IGNORED_OWNER_GOAL",
            "owner-private.example",
        ):
            assert private not in serialized
        assert runner.inputs.allowed_hosts == ("example.org",)
        assert runner.inputs.official_url == URL
        assert runner.calls == 1
        with Database(settings.database_path).transaction() as connection:
            store = WorkspaceStore(connection)
            persisted = store.runs.current(run_id)
            assert persisted.decision_id is not None
            assert persisted.opportunity_id == opportunity_id
            assert store.evidence.list_for_opportunity(opportunity_id, 1)[0].content_hash == (
                hashlib.sha256(TEXT.encode()).hexdigest()
            )
    with TestClient(make_app(settings, ControlledRunner())) as reopened:
        assert terminal(reopened, run_id) == done
        missing = reopened.get("/api/v1/live-runs/unknown", headers=AUTH)
        assert missing.status_code == 404
        assert missing.json() == {"code": "LIVE_RUN_UNAVAILABLE"}


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/rules",
        "https://localhost/rules",
        "https://127.0.0.1/rules",
        "https://169.254.169.254/latest",
        "https://10.0.0.1/rules",
        "https://[::1]/rules",
        "https://user:password@example.org/rules",
        "file:///etc/passwd",
        "https://example.org:8080/rules",
        "https://example.org\\@localhost/rules",
    ],
)
def test_invalid_or_private_urls_rejected(tmp_path, url):
    runner = ControlledRunner()
    with TestClient(make_app(config(tmp_path), runner)) as client:
        result = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": url})
        assert result.status_code == 422, result.text
        assert runner.calls == 0


def test_private_dns_answer_rejected(tmp_path):
    runner = ControlledRunner()
    app = create_app(config(tmp_path), live_runner=runner, live_resolver=lambda host: ["10.0.0.4"])
    with TestClient(app) as client:
        response = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        assert response.status_code == 422
        assert runner.calls == 0


@pytest.mark.parametrize(
    "field",
    [
        "founder",
        "projects",
        "allowed_hosts",
        "budget",
        "aws_region",
        "model_id",
        "gateway_id",
        "credentials",
        "policy",
    ],
)
def test_browser_cannot_supply_server_authority(tmp_path, field):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        response = client.post(
            "/api/v1/live-runs", headers=AUTH, json={"official_url": URL, field: "untrusted"}
        )
        assert response.status_code == 422
        assert "untrusted" not in response.text


@pytest.mark.parametrize("headers", [{}, {"X-QUALOR-Origin-Auth": "wrong"}])
def test_hosted_requires_proxy_auth_for_reads_and_mutations(tmp_path, headers):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        for method, route in (
            ("post", "live-runs"),
            ("get", "live-runs/unknown"),
            ("get", "inbox"),
            ("put", "profile"),
        ):
            response = getattr(client, method)("/api/v1/" + route, headers=headers)
            assert response.status_code == 403
            assert response.json() == {"code": "ACTION_FORBIDDEN"}


def test_hosted_capability_is_separate_and_owner_mutations_remain_unavailable(tmp_path):
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        assert client.app.state.action_token is None
        session = client.get("/api/v1/session", headers=AUTH)
        assert session.status_code == 200
        assert session.json()["read_only"] is False
        assert session.json()["action_token"]
        for method, route in (
            ("get", "portfolio"),
            ("put", "profile"),
            ("put", "projects/qualor"),
        ):
            response = getattr(client, method)("/api/v1/" + route, headers=AUTH)
            assert response.status_code == 404
            assert SECRET not in response.text
        for route in (
            "opportunities/opportunity/approvals",
            "approvals/approval/confirm",
        ):
            response = client.post("/api/v1/" + route, headers=AUTH)
            assert response.status_code == 403
            assert response.json() == {"code": "ACTION_FORBIDDEN"}


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (RuntimeError("PRIVATE_PROVIDER_ERROR"), "FAILED", "INTERNAL_LIVE_RUN_FAILURE"),
        (ProviderBoundaryError("PRIVATE_DISCONNECTED"), "FAILED", "LIVE_PROVIDER_FAILED"),
        (BudgetLimitExceeded("PRIVATE_BUDGET_ERROR"), "BUDGET_STOPPED", "BUDGET_STOPPED"),
    ],
)
def test_failures_are_bounded_and_terminal(tmp_path, failure, status, code):
    with TestClient(make_app(config(tmp_path), ControlledRunner(failure=failure))) as client:
        accepted = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        done = terminal(client, accepted.json()["run_id"])
        assert done["status"] == status
        assert done["error_code"] == code
        assert done["opportunity_id"] is None
        assert "PRIVATE" not in json.dumps(done)


def test_persistence_failure_cannot_report_completed(tmp_path, monkeypatch):
    from qualor.workspace.run_capture import WorkspaceRunCapture

    def fail(self, store, graph):
        raise RuntimeError("PRIVATE_DATABASE_FAILURE")

    monkeypatch.setattr(WorkspaceRunCapture, "_persist_graph", fail)
    with TestClient(make_app(config(tmp_path), ControlledRunner())) as client:
        accepted = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        done = terminal(client, accepted.json()["run_id"])
        assert done["status"] == "FAILED"
        assert done["error_code"] == "LIVE_PERSISTENCE_FAILED"
        assert done["opportunity_id"] is None


def test_process_run_count_is_bounded(tmp_path):
    runner = ControlledRunner(failure=RuntimeError("controlled"))
    with TestClient(make_app(config(tmp_path, qualor_live_max_runs=1), runner)) as client:
        first = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        terminal(client, first.json()["run_id"])
        second = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        assert second.status_code == 429
        assert second.json() == {"code": "LIVE_RUN_LIMIT_REACHED"}
        assert runner.calls == 1


def test_local_security_remains_loopback_and_action_token_bound(tmp_path):
    with TestClient(
        create_app(Settings(database_path=tmp_path / "local.db")), client=("127.0.0.1", 3456)
    ) as client:
        origin = {"Origin": "http://127.0.0.1:5173"}
        session = client.get("/api/v1/session", headers=origin)
        assert session.status_code == 200
        assert session.json()["action_token"]
        assert (
            client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL}).status_code
            == 403
        )
        allowed = {**origin, "X-QUALOR-Action-Token": session.json()["action_token"]}
        assert (
            client.post(
                "/api/v1/live-runs", headers=allowed, json={"official_url": URL}
            ).status_code
            == 404
        )


def test_cooldown_refuses_repeated_execution(tmp_path):
    settings = config(tmp_path).model_copy(update={"qualor_live_cooldown_seconds": 60})
    runner = ControlledRunner(failure=RuntimeError("controlled"))
    with TestClient(make_app(settings, runner)) as client:
        first = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        terminal(client, first.json()["run_id"])
        response = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        assert response.status_code == 429
        assert response.json() == {"code": "LIVE_RUN_COOLDOWN"}
        assert runner.calls == 1


def test_successful_transient_return_without_capture_cannot_complete(tmp_path):
    def no_capture(*args, **kwargs):
        return {"status": "COMPLETED", "opportunity_id": "invented"}, {}

    with TestClient(make_app(config(tmp_path), no_capture)) as client:
        first = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        done = terminal(client, first.json()["run_id"])
        assert done["status"] == "FAILED"
        assert done["error_code"] == "LIVE_PERSISTENCE_FAILED"
        assert done["opportunity_id"] is None


def test_completed_status_revalidates_database_authority(tmp_path, monkeypatch):
    from qualor.persistence.repositories import RunRepository

    settings = config(tmp_path)
    with TestClient(make_app(settings, ControlledRunner())) as client:
        first = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        run_id = first.json()["run_id"]
        assert terminal(client, run_id)["status"] == "COMPLETED"
        # Controlled loss of the terminal authority must not fall back to a memory success.
        monkeypatch.setattr(RunRepository, "current", lambda self, key: None)
        response = client.get(f"/api/v1/live-runs/{run_id}", headers=AUTH)
        assert response.status_code == 404
        assert response.json() == {"code": "LIVE_RUN_UNAVAILABLE"}


def test_url_canonicalization_preserves_unverified_target(tmp_path):
    runner = ControlledRunner(failure=RuntimeError("controlled"))
    with TestClient(make_app(config(tmp_path), runner)) as client:
        first = client.post(
            "/api/v1/live-runs",
            headers=AUTH,
            json={"official_url": "https://EXAMPLE.org:443/rules?utm_source=x#top"},
        )
        terminal(client, first.json()["run_id"])
        assert runner.inputs.official_url == URL
        assert runner.inputs.allowed_hosts == ("example.org",)


def test_missing_or_weak_hosted_configuration_fails_closed(tmp_path):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(qualor_security_mode="HOSTED_DEMO")
    with pytest.raises(ValidationError):
        Settings(
            qualor_security_mode="HOSTED_DEMO",
            qualor_origin_auth="short",
            qualor_demo_profile_path=profile_file(tmp_path),
        )
    with pytest.raises(ValidationError):
        Settings(qualor_hosted_live_enabled=True)
    with pytest.raises(ValidationError):
        Settings(qualor_max_concurrent_live_runs=2)


def test_hosted_disabled_by_default_and_secret_not_serialized(tmp_path):
    settings = config(tmp_path).model_copy(update={"qualor_hosted_live_enabled": False})
    assert SECRET not in repr(settings)
    assert SECRET not in settings.model_dump_json()
    runner = ControlledRunner()
    with TestClient(make_app(settings, runner)) as client:
        response = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
        assert response.status_code == 503
        assert runner.calls == 0


def test_hosted_rejects_owner_database(tmp_path):
    settings = config(tmp_path)
    inputs = StudioInput.model_validate_json(settings.qualor_demo_profile_path.read_bytes())
    with Database(settings.database_path).transaction() as connection:
        WorkspaceStore(connection).profiles.put_founder(inputs.founder)
    with pytest.raises(RuntimeError, match="HOSTED_DEMO_DATABASE_REQUIRES_SANITIZED_PROFILE"):
        with TestClient(make_app(settings, ControlledRunner())):
            pass


@pytest.mark.parametrize("kind", ["founder", "project"])
def test_hosted_rejects_private_historical_profile(tmp_path, kind):
    from qualor.hosted.inputs import load_demo_profile

    settings = config(tmp_path)
    raw = json.loads(settings.qualor_demo_profile_path.read_text(encoding="utf-8"))
    target = raw["founder"] if kind == "founder" else raw["projects"][0]["project"]
    target["version"] = 2
    settings.qualor_demo_profile_path.write_text(json.dumps(raw), encoding="utf-8")
    profile = load_demo_profile(settings.qualor_demo_profile_path)
    current = profile.founder if kind == "founder" else profile.projects[0].project
    historical = current.model_copy(update={"version": 1})
    if kind == "founder":
        historical = historical.model_copy(update={"constraints": ("PRIVATE_HISTORY",)})
    with Database(settings.database_path).transaction() as connection:
        store = WorkspaceStore(connection)
        put = store.profiles.put_founder if kind == "founder" else store.projects.put_project
        put(historical)
        put(current)
    with pytest.raises(RuntimeError, match="HOSTED_DEMO_DATABASE_REQUIRES_SANITIZED_PROFILE"):
        with TestClient(make_app(settings, ControlledRunner())):
            pass


def test_settings_validation_traceback_does_not_echo_secret():
    import traceback

    from pydantic import ValidationError

    secret = "SENSITIVE_ORIGIN_SENTINEL" * 2
    with pytest.raises(ValidationError) as error:
        Settings(qualor_security_mode="HOSTED_DEMO", qualor_origin_auth=secret)
    assert "SENSITIVE" not in "".join(traceback.format_exception(error.value))
    assert "input_value" not in str(error.value)


def test_worker_bootstrap_failure_is_terminal_and_releases_slot(tmp_path, monkeypatch):
    def broken_budget():
        raise RuntimeError("PRIVATE_BOOTSTRAP_ERROR")

    monkeypatch.setattr("qualor.hosted.coordinator.live_budget", broken_budget)
    runner = ControlledRunner()
    with TestClient(make_app(config(tmp_path), runner)) as client:
        for _ in range(2):
            response = client.post("/api/v1/live-runs", headers=AUTH, json={"official_url": URL})
            assert response.status_code == 202
            done = terminal(client, response.json()["run_id"])
            assert done["status"] == "FAILED"
            assert done["error_code"] == "INTERNAL_LIVE_RUN_FAILURE"
            assert "PRIVATE_BOOTSTRAP_ERROR" not in json.dumps(done)
        assert runner.calls == 0


def test_only_one_racing_request_can_launch(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from qualor.hosted.contracts import LiveRunRequest
    from qualor.hosted.coordinator import LiveRunDenied

    runner = ControlledRunner(pause=True, failure=RuntimeError("controlled"))
    with TestClient(make_app(config(tmp_path), runner)) as client:
        coordinator = client.app.state.live_runs
        barrier = threading.Barrier(8)

        def start():
            barrier.wait(timeout=5)
            try:
                return coordinator.start(LiveRunRequest(official_url=URL)).run_id
            except LiveRunDenied as error:
                return error.code

        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(lambda _: start(), range(8)))
            assert outcomes.count("LIVE_RUN_BUSY") == 7
            assert runner.entered.wait(5)
            assert runner.calls == 1
        finally:
            runner.continue_research.set()
