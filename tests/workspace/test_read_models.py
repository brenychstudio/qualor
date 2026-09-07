"""Projection must preserve persisted decision and operational uncertainty."""

from datetime import UTC, datetime

import pytest

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def seed(*args, **kwargs):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "workspace_api_tests", Path(__file__).parents[1] / "test_workspace_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.seed(*args, **kwargs)


def service(database, fixture, decision):
    import importlib.util

    import qualor.workspace as workspace

    assert importlib.util.find_spec(workspace.__name__ + ".service"), "Missing read service"
    from qualor.workspace.approval import ApprovalService
    from qualor.workspace.service import WorkspaceService

    approvals = ApprovalService(
        database,
        actor_id=fixture.founder.id,
        policy_versions=decision.policy_versions,
        mode="FIXTURE",
    )
    return WorkspaceService(database, approvals=approvals, clock=lambda: NOW)


@pytest.mark.parametrize("state", ["COMPLETED", "PARTIAL", "FAILED", "BUDGET_STOPPED", "RUNNING"])
@pytest.mark.parametrize("mode", ["FIXTURE", "REPLAY", "LIVE"])
def test_run_states_and_modes_preserved(tmp_path, state, mode):
    database, fixture, decision = seed(tmp_path, state=state, mode=mode)
    row = service(database, fixture, decision).inbox().items[0]
    assert row.run_state == state
    assert row.mode == mode
    assert row.recommendation == decision.recommendation


def test_stale_retains_exact_proof_and_prior_decision(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database, fixture, decision = seed(tmp_path)
    WorkspaceLifecycle(database).mark_refresh_failed(fixture.opportunity.id, NOW)
    reader = service(database, fixture, decision)
    result = reader.workspace(fixture.opportunity.id)
    assert result.freshness == "STALE"
    assert result.decision.recommendation == decision.recommendation
    assert not result.decision.primary_action.available
    assert all(p.freshness == "STALE" for p in reader.evidence(fixture.opportunity.id).proofs)


def test_no_decision_has_no_invented_project_score_or_recommendation(tmp_path):
    database, fixture, decision = seed(tmp_path, decision_present=False)
    canvas = service(database, fixture, decision).workspace(fixture.opportunity.id).decision
    assert canvas.best_project is None
    assert canvas.recommendation is None
    assert canvas.eligibility is None
    assert canvas.strategy.state == "NOT_ENOUGH_EVIDENCE"
    assert canvas.strategy.score is None
    assert not canvas.primary_action.available


def test_approval_capability_inspection_uses_existing_authority_without_writes(tmp_path):
    from test_approval import request, setup

    approvals, bindings, _, _ = setup(tmp_path)
    assert hasattr(approvals, "inspect_request"), "Missing read-only approval capability"
    result = approvals.inspect_request(bindings, NOW)
    assert result.actionable
    with approvals.database.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM approvals").fetchone()[0] == 0
    assert request(approvals, bindings).state == "PENDING_APPROVAL"


def test_canonical_evidence_failure_marker_cannot_become_fresh_workspace(tmp_path):
    from test_approval import setup

    approvals, _, fixture, decision = setup(
        tmp_path, evidence_change={"last_refresh_failed_at": NOW}
    )
    reader = service(approvals.database, fixture, decision)
    assert reader.workspace(fixture.opportunity.id).freshness == "STALE"
    assert reader.inbox().items[0].freshness == "STALE"
