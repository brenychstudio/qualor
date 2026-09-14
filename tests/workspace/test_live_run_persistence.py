from datetime import UTC, datetime
from pathlib import Path

import pytest

from qualor.decisions import DecisionFixture
from qualor.decisions.engine import decide
from qualor.decisions.fixture import DecisionInput
from qualor.persistence import Database
from qualor.runtime.run_models import AgentRunResult, RuntimeDecisionBundle, StudioInput, TraceEvent
from qualor.workspace import WorkspaceStore
from qualor.workspace.lifecycle import WorkspaceLifecycle
from qualor.workspace.run_capture import WorkspaceRunCapture
from qualor.workspace.versioning import opportunity_semantic_digest

FIXED = datetime(2026, 9, 12, 18, 0, tzinfo=UTC)
FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures/decisions/D09_TWO_PROJECTS_CLEAR_BEST_MATCH.json"
)


def live_authority():
    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    evidence = tuple(
        item.model_copy(
            update={
                "original_url": "https://example.org/rules",
                "final_url": "https://example.org/rules",
                "source_type": "OFFICIAL_RULES",
            }
        )
        for item in fixture.evidence
    )
    opportunity = fixture.opportunity.model_copy(
        update={"canonical_rules_url": "https://example.org/rules"}
    )
    decision_input = DecisionInput.model_validate(
        {
            **fixture.model_dump(mode="json"),
            "mode": "LIVE",
            "opportunity": opportunity,
            "evidence": evidence,
        }
    )
    inputs = StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Assess one controlled official opportunity",
        allowed_hosts=("example.org",),
        founder=fixture.founder,
        projects=fixture.projects,
    )
    return inputs, decision_input


def result(bundle, termination_reason="SUFFICIENT_CRITICAL_EVIDENCE"):
    return AgentRunResult(
        mode="LIVE",
        decision=bundle.decision,
        claims=(),
        trace=(),
        termination_reason=termination_reason,
        agent_steps=8,
        search_calls=2,
        fetched_documents=1,
        official_source_count=1,
        citation_urls=("https://example.org/rules",),
        contradictions=(),
        bundle=bundle,
    )


def resolved_bundle(capture, decision_input):
    opportunity = capture.resolve_opportunity_version(decision_input.opportunity)
    authoritative_input = decision_input.model_copy(update={"opportunity": opportunity})
    return RuntimeDecisionBundle(
        opportunity=opportunity,
        evidence=authoritative_input.evidence,
        decision_input=authoritative_input,
        decision=decide(authoritative_input),
    )


def test_completed_live_result_persists_one_linked_authoritative_graph(tmp_path, monkeypatch):
    database = Database(tmp_path / "workspace.db")
    inputs, decision_input = live_authority()
    # Existing exact profile/project snapshots are legitimate immutable authorities and
    # must be reused rather than causing a duplicate-record failure.
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(inputs.founder)
        for project in inputs.projects:
            store.projects.put_project(project.project)

    capture = WorkspaceRunCapture(
        database,
        run_id="live-run-1",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    bundle = resolved_bundle(capture, decision_input)
    monkeypatch.setattr(
        "qualor.runtime.handoff.decide",
        lambda decision_input: (_ for _ in ()).throw(
            AssertionError("persistence must not recompute the decision")
        ),
    )
    capture.trace_event(
        TraceEvent(event="EVIDENCE_RECORDED", reason_code="CONTROLLED_CLAUSE_VERIFIED"),
        mode="LIVE",
    )

    capture.run_finished(result(bundle))
    capture.require_persisted()

    selected = bundle.decision.selected_decision
    assert selected is not None
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        assert (
            store.profiles.get_founder(inputs.founder.id, inputs.founder.version)
            == inputs.founder
        )
        assert tuple(
            store.projects.get_project(item.project.id, item.project.version)
            for item in inputs.projects
        ) == tuple(item.project for item in inputs.projects)
        assert (
            store.opportunities.get_opportunity_version(
                bundle.opportunity.id, bundle.opportunity.version
            )
            == bundle.opportunity
        )
        assert {
            item.id: item
            for item in store.evidence.list_for_opportunity(
                bundle.opportunity.id, bundle.opportunity.version
            )
        } == {item.id: item for item in bundle.evidence}
        assert {
            item.id: item
            for item in store.decisions.list_for_opportunity(
                bundle.opportunity.id, bundle.opportunity.version
            )
        } == {item.id: item for item in bundle.decision.candidates}
        persisted_run = store.runs.current("live-run-1")
        assert persisted_run.opportunity_id == bundle.opportunity.id
        assert persisted_run.opportunity_version == bundle.opportunity.version
        assert persisted_run.decision_id == selected.id
        assert persisted_run.decision_version == selected.version
        assert persisted_run.mode.value == "LIVE"
        assert [event.mode.value for event in store.runs.list_run_events("live-run-1")] == [
            "LIVE"
        ]

    reopened = WorkspaceLifecycle(Database(database.path)).reconstruct_workspace(
        bundle.opportunity.id, FIXED
    )
    assert reopened.current.opportunity == bundle.opportunity
    assert {item.id: item for item in reopened.current.evidence} == {
        item.id: item for item in bundle.evidence
    }
    assert {item.id: item for item in reopened.current.decisions} == {
        item.id: item for item in bundle.decision.candidates
    }
    assert reopened.current.runs[0].decision_id == selected.id


@pytest.mark.parametrize(
    ("termination_reason", "state"),
    (
        ("NO_PROGRESS", "PARTIAL"),
        ("BUDGET_EXHAUSTED", "BUDGET_STOPPED"),
        ("MAX_STEPS", "PARTIAL"),
        ("TOOL_FAILURE_BOUND_REACHED", "PARTIAL"),
    ),
)
def test_incomplete_live_run_persists_telemetry_without_success_graph(
    tmp_path, termination_reason, state
):
    database = Database(tmp_path / "workspace.db")
    inputs, decision_input = live_authority()
    capture = WorkspaceRunCapture(
        database,
        run_id="live-run-incomplete",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    bundle = resolved_bundle(capture, decision_input)

    capture.run_finished(result(bundle, termination_reason))
    capture.require_persisted()

    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("live-run-incomplete")
        assert run.state.value == state
        assert run.opportunity_id is None
        assert run.decision_id is None
        assert store.opportunities.list_current() == ()
        assert store.decisions.list_for_opportunity(
            bundle.opportunity.id, bundle.opportunity.version
        ) == ()
        assert store.evidence.list_for_opportunity(
            bundle.opportunity.id, bundle.opportunity.version
        ) == ()
        assert store.profiles.list_current() == ()
        assert store.projects.list_current() == ()


def test_observer_retains_persistence_failure_until_operator_verifies(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs, _ = live_authority()
    first = WorkspaceRunCapture(
        database,
        run_id="duplicate-run",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    first.run_failed(termination_reason="PROVIDER_DISCONNECTED")
    first.require_persisted()

    second = WorkspaceRunCapture(
        database,
        run_id="duplicate-run",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )

    # Observer callbacks stay isolated and do not raise into the runtime.
    second.run_failed(termination_reason="PROVIDER_DISCONNECTED")

    with pytest.raises(RuntimeError, match="workspace persistence failed"):
        second.require_persisted()


def test_provider_failure_persists_only_failed_live_telemetry(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs, _ = live_authority()
    capture = WorkspaceRunCapture(
        database,
        run_id="provider-failure",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )

    capture.run_failed(
        termination_reason="PROVIDER_DISCONNECTED",
        provider_state="DISCONNECTED_LIVE_PROVIDER",
    )
    capture.require_persisted()

    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        run = store.runs.current("provider-failure")
        assert run.state.value == "FAILED"
        assert run.provider_state == "DISCONNECTED_LIVE_PROVIDER"
        assert run.opportunity_id is None
        assert run.decision_id is None
        assert store.opportunities.list_current() == ()


def test_version_resolver_reuses_identity_and_advances_semantic_version(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs, decision_input = live_authority()
    first = WorkspaceLifecycle(database).persist_observation(decision_input.opportunity)
    capture = WorkspaceRunCapture(
        database,
        run_id="semantic-change",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    changed = decision_input.opportunity.model_copy(
        update={"deadlines": (datetime(2026, 9, 13, 12, 0, tzinfo=UTC),)}
    )

    resolved = capture.resolve_opportunity_version(changed)

    assert resolved.id == first.opportunity_id
    assert resolved.version == 2
    # Resolution is read-only; the graph transaction owns the eventual write.
    with database.transaction() as connection:
        versions = WorkspaceStore(connection).opportunities.list_versions(resolved.id)
    assert [item.version for item in versions] == [1]


def test_provisional_resolution_can_refine_before_final_graph_persistence(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs, decision_input = live_authority()
    capture = WorkspaceRunCapture(
        database,
        run_id="semantic-refinement",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    provisional = decision_input.opportunity.model_copy(
        update={"organizer": "UNKNOWN", "program_name": "UNKNOWN", "edition": "UNKNOWN"}
    )

    first = capture.resolve_opportunity_version(provisional)
    final_bundle = resolved_bundle(capture, decision_input)
    capture.run_finished(result(final_bundle))
    capture.require_persisted()

    assert first.id != final_bundle.opportunity.id
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        assert store.opportunities.list_versions(first.id) == ()
        persisted = store.runs.current("semantic-refinement")
        assert persisted.opportunity_id == final_bundle.opportunity.id


def test_completed_graph_requires_admitted_official_rules_evidence(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs, decision_input = live_authority()
    capture = WorkspaceRunCapture(
        database,
        run_id="missing-official-rules",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    opportunity = capture.resolve_opportunity_version(decision_input.opportunity)
    evidence = tuple(
        item.model_copy(update={"source_type": "OTHER_OFFICIAL"})
        for item in decision_input.evidence
    )
    downgraded_input = decision_input.model_copy(
        update={"opportunity": opportunity, "evidence": evidence}
    )
    bundle = RuntimeDecisionBundle(
        opportunity=opportunity,
        evidence=evidence,
        decision_input=downgraded_input,
        decision=decide(downgraded_input),
    )

    capture.run_finished(result(bundle))

    with pytest.raises(RuntimeError, match="workspace persistence failed"):
        capture.require_persisted()
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        assert store.opportunities.list_current() == ()
        assert store.runs.page_current(50, 0)[0] == ()


def test_existing_evidence_cannot_be_silently_reused_under_another_opportunity(tmp_path):
    database = Database(tmp_path / "workspace.db")
    inputs, decision_input = live_authority()
    first_opportunity = decision_input.opportunity
    evidence = decision_input.evidence[0]
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.opportunities.put_opportunity_version(
            first_opportunity,
            content_hash=opportunity_semantic_digest(first_opportunity),
        )
        store.evidence.put_evidence(
            evidence, first_opportunity.id, first_opportunity.version
        )

    second_opportunity = type(first_opportunity).model_validate(
        {**first_opportunity.model_dump(mode="json"), "program_name": "Other Program"}
    )
    second_input = decision_input.model_copy(update={"opportunity": second_opportunity})
    capture = WorkspaceRunCapture(
        database,
        run_id="evidence-scope-conflict",
        mode="LIVE",
        inputs=inputs,
        clock=lambda: FIXED,
    )
    bundle = resolved_bundle(capture, second_input)

    capture.run_finished(result(bundle))

    with pytest.raises(RuntimeError, match="workspace persistence failed"):
        capture.require_persisted()
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        assert store.opportunities.get_opportunity_version(bundle.opportunity.id, 1) is None
