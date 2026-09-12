from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.base import Fact
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.persistence import Database
from qualor.runtime.claims import ExtractedClaim, validate_claim
from qualor.runtime.handoff import compile_decision_bundle
from qualor.runtime.run_models import AgentRunResult, StudioInput, TraceEvent
from qualor.runtime.sources import SourceDocument
from qualor.settings import Settings
from qualor.workspace.run_capture import WorkspaceRunCapture

NOW = datetime(2026, 9, 12, 18, 0, tzinfo=UTC)
URL = "https://example.org/rules"


def controlled_inputs():
    base = {
        "schema_version": "1",
        "id": "founder-live-acceptance",
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "provenance": "USER_ASSERTED",
    }
    founder = FounderProfile.model_validate(base)
    project = ProjectProfile.model_validate(
        {
            **base,
            "id": "project-live-acceptance",
            "name": "Controlled project",
            "technology_stack": Fact(value=("Different SDK",), provenance="USER_ASSERTED"),
        }
    )
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Assess the controlled official opportunity",
        allowed_hosts=("example.org",),
        founder=founder,
        projects=(
            ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),
        ),
    )


def controlled_live_result(capture, inputs):
    text = (
        "Organizer: Northstar Foundation. "
        "Program: Controlled Builders Challenge. "
        "Deadline: 2030-06-01T17:00:00-07:00. "
        "Projects must use Widget SDK."
    )
    source = SourceDocument(
        id="source-live-acceptance",
        original_url=URL,
        final_url=URL,
        retrieved_at=NOW,
        content_hash="c" * 64,
        authority="OFFICIAL_RULES",
        text=text,
    )

    def claim(field, value, excerpt):
        return validate_claim(
            ExtractedClaim.model_validate(
                {
                    "source_id": source.id,
                    "source_url": source.final_url,
                    "field": field,
                    "value": value,
                    "excerpt": excerpt,
                    "state": "CANDIDATE",
                    "confidence": "HIGH",
                }
            ),
            {source.id: source},
        )

    claims = (
        claim("organizer", "Northstar Foundation", "Organizer: Northstar Foundation."),
        claim(
            "program",
            "Controlled Builders Challenge",
            "Program: Controlled Builders Challenge.",
        ),
        claim(
            "deadline",
            "2030-06-01T17:00:00-07:00",
            "Deadline: 2030-06-01T17:00:00-07:00.",
        ),
        claim(
            "required_technology",
            ("Widget SDK",),
            "Projects must use Widget SDK.",
        ),
    )
    run = SimpleNamespace(
        inputs=inputs,
        mode="LIVE",
        sources={source.id: source},
        candidates={},
        claims={item.evidence.id: item for item in claims},
        contradictions=(),
        opportunity_version_resolver=capture.resolve_opportunity_version,
    )
    bundle = compile_decision_bundle(run)
    assert bundle.decision.eligibility == "FAIL"
    assert bundle.decision.selected_decision is not None
    result = AgentRunResult(
        mode="LIVE",
        decision=bundle.decision,
        claims=claims,
        trace=(),
        termination_reason="HARD_FAIL_CONFIRMED",
        agent_steps=7,
        search_calls=1,
        fetched_documents=1,
        official_source_count=1,
        citation_urls=(URL,),
        contradictions=(),
        bundle=bundle,
    )
    return result


def test_live_shaped_result_reopens_through_existing_workspace_api(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs = controlled_inputs()
    capture = WorkspaceRunCapture(
        database,
        run_id="live-acceptance",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: NOW,
    )
    runtime_result = controlled_live_result(capture, inputs)
    capture.trace_event(
        TraceEvent(event="SOURCE_FETCHED", reason_code="SOURCE_TEXT_UNTRUSTED_DATA"),
        mode="LIVE",
    )
    capture.trace_event(
        TraceEvent(event="EVIDENCE_RECORDED", reason_code="CONTROLLED_CLAUSE_VERIFIED"),
        mode="LIVE",
    )
    capture.trace_event(
        TraceEvent(event="DECISION_EVALUATED", reason_code="DETERMINISTIC_ENGINE"),
        mode="LIVE",
    )
    capture.run_finished(runtime_result)
    capture.require_persisted()

    selected = runtime_result.decision.selected_decision
    app = __import__("qualor.api", fromlist=["create_app"]).create_app(
        Settings(database_path=database.path),
        actor_id=inputs.founder.id,
        policy_versions=selected.policy_versions,
        mode="LIVE",
        clock=lambda: NOW,
    )
    with TestClient(app, client=("127.0.0.1", 12345), raise_server_exceptions=False) as client:
        inbox = client.get("/api/v1/inbox")
        assert inbox.status_code == 200
        item = inbox.json()["items"][0]
        assert item["opportunity_id"] == runtime_result.bundle.opportunity.id
        assert item["program_name"] == "Controlled Builders Challenge"
        assert item["mode"] == "LIVE"

        opportunity_id = item["opportunity_id"]
        workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace")
        assert workspace.status_code == 200
        assert workspace.json()["decision"]["recommendation"] == "SKIP"
        assert workspace.json()["mode"] == "LIVE"
        assert workspace.json()["run_state"] == "COMPLETED"

        evidence = client.get(f"/api/v1/opportunities/{opportunity_id}/evidence")
        assert evidence.status_code == 200
        proofs = evidence.json()["proofs"]
        assert any(
            proof["excerpt"] == "Deadline: 2030-06-01T17:00:00-07:00."
            and proof["url"] == URL
            for proof in proofs
        )

        activity = client.get("/api/v1/runs")
        assert activity.status_code == 200
        persisted_run = activity.json()["runs"][0]
        assert persisted_run["mode"] == "LIVE"
        assert persisted_run["state"] == "COMPLETED"
        assert persisted_run["opportunity_id"] == opportunity_id
