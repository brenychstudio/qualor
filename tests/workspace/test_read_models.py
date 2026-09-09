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


def priority_workspace(tmp_path):
    from qualor.persistence import Database
    from qualor.workspace.store import WorkspaceStore

    _, fixture, decision = seed(tmp_path / "source")
    database = Database(tmp_path / "priority.db")
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        for project in fixture.projects:
            store.projects.put_project(project.project)
    return database, fixture, decision


def put_priority_item(
    database,
    fixture,
    decision,
    identity,
    *,
    recommendation="APPLY",
    state="COMPLETED",
    deadlines=None,
    score=90,
    discovered=NOW,
    with_decision=True,
    with_run=True,
    evidence_retrieved_at=None,
):
    """Persist explicit synthetic read-boundary inputs, without replacing the service."""
    from datetime import timedelta

    from qualor.decisions import DecisionRecord
    from qualor.domain import EvidenceRecord, OpportunityRecord
    from qualor.strategy.scoring import StrategyFactors, score_strategy
    from qualor.workspace.models import RunRecord
    from qualor.workspace.store import WorkspaceStore
    from qualor.workspace.versioning import opportunity_semantic_digest

    references = {e.id: identity + ":" + e.id for e in fixture.evidence}

    def remap(value):
        if isinstance(value, str):
            return references.get(value, value)
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [remap(item) for item in value]
        return value

    opportunity = OpportunityRecord.model_validate(
        {
            **remap(fixture.opportunity.model_dump()),
            "program_name": identity,
            "created_at": discovered,
            "updated_at": NOW,
            "deadlines": deadlines if deadlines is not None else (NOW + timedelta(days=10),),
        }
    )
    references[fixture.opportunity.id] = opportunity.id
    data = remap(decision.model_dump())
    ratings = {90: (4, 4, 4, 2, 3), 70: (2, 4, 2, 4, 2), None: (None, 4, 4, 2, 3)}[score]
    strategy = score_strategy(
        StrategyFactors(**dict(zip(StrategyFactors.model_fields, ratings, strict=True))), NOW
    )
    assert strategy.score == score
    data.update(
        id=identity + ":decision",
        recommendation=recommendation,
        strategy_score=strategy.score,
        strategy=strategy.model_dump(),
        strategy_breakdown=[item.model_dump() for item in strategy.breakdown],
    )
    selected = DecisionRecord.model_validate(data)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.opportunities.put_opportunity_version(
            opportunity, content_hash=opportunity_semantic_digest(opportunity)
        )
        for evidence in fixture.evidence:
            evidence_data = remap(evidence.model_dump())
            if evidence_retrieved_at is not None:
                evidence_data["retrieved_at"] = evidence_retrieved_at
            store.evidence.put_evidence(
                EvidenceRecord.model_validate(evidence_data), opportunity.id, 1
            )
        if with_decision:
            store.decisions.put_decision(selected, founder_profile_id=fixture.founder.id)
        if with_run:
            store.runs.create_run(
                RunRecord(
                    schema_version="1",
                    id=identity + ":run",
                    version=1,
                    created_at=NOW,
                    updated_at=NOW,
                    provenance="DOCUMENTED",
                    mode="FIXTURE",
                    state=state,
                    opportunity_id=opportunity.id,
                    opportunity_version=1,
                    decision_id=selected.id if with_decision else None,
                    decision_version=1 if with_decision else None,
                    started_at=NOW,
                    completed_at=NOW if state == "COMPLETED" else None,
                )
            )
    return opportunity, selected


def test_priority_attention_order_preserves_recommendations(tmp_path):
    from qualor.persistence import Database
    from qualor.workspace.store import WorkspaceStore

    database, fixture, decision = priority_workspace(tmp_path)
    cases = [
        ("a-skip", "SKIP", "COMPLETED", True, True),
        ("b-discovered", "APPLY", "CREATED", False, False),
        ("c-verifying", "APPLY", "RUNNING", False, True),
        ("d-watch", "WATCH", "COMPLETED", True, True),
        ("e-review", "APPLY", "PARTIAL", True, True),
        ("f-prepare", "PREPARE", "COMPLETED", True, True),
        ("g-apply", "APPLY", "COMPLETED", True, True),
    ]
    for identity, rec, state, selected, run in cases:
        put_priority_item(
            database,
            fixture,
            decision,
            identity,
            recommendation=rec,
            state=state,
            with_decision=selected,
            with_run=run,
        )
    reader = service(database, fixture, decision)
    rows = reader.inbox().items
    assert [row.program_name for row in rows] == [
        "g-apply",
        "f-prepare",
        "e-review",
        "d-watch",
        "c-verifying",
        "b-discovered",
        "a-skip",
    ]
    assert [row.priority_rank for row in rows] == list(range(7))
    assert [row.presentation_state for row in rows] == [
        "EVALUATED", "EVALUATED", "NEEDS_REVIEW", "EVALUATED",
        "VERIFYING", "DISCOVERED", "EVALUATED",
    ]
    assert [row.recommendation for row in rows] == [
        "APPLY", "PREPARE", "APPLY", "WATCH", None, None, "SKIP",
    ]
    # Each transaction closes its connection; reopen the persisted workspace and services.
    reopened = service(Database(database.path), fixture, decision).inbox()
    assert reopened.items == rows
    assert rows[2].recommendation == "APPLY"
    assert rows[4].best_project is None
    assert rows[4].recommendation is None
    with database.transaction() as connection:
        stored = WorkspaceStore(connection).decisions.get_decision("e-review:decision", 1)
        assert stored.recommendation == "APPLY"


def test_priority_deadline_buckets_and_exact_boundary(tmp_path):
    from datetime import timedelta

    database, fixture, decision = priority_workspace(tmp_path)
    cases = [
        ("a-past", (NOW - timedelta(days=1),)),
        ("b-boundary", (NOW,)),
        ("c-calendar", (NOW.date(),)),
        ("d-unknown", ()),
        ("e-later", (NOW + timedelta(days=10),)),
        ("f-sooner", (NOW + timedelta(days=2),)),
    ]
    for identity, deadlines in cases:
        put_priority_item(database, fixture, decision, identity, deadlines=deadlines)
    rows = service(database, fixture, decision).inbox().items
    assert [row.program_name for row in rows] == [
        "f-sooner",
        "e-later",
        "c-calendar",
        "d-unknown",
        "b-boundary",
        "a-past",
    ]
    assert rows[2].deadline.timezone_status == "CALENDAR_DATE_ONLY"
    assert rows[3].deadline.timezone_status == "UNKNOWN"
    assert all(row.presentation_state == "EVALUATED" for row in rows)


def test_priority_strategy_null_then_first_discovery_then_id(tmp_path):
    from datetime import timedelta

    database, fixture, decision = priority_workspace(tmp_path)
    for identity, score, discovered in [
        ("a-null", None, NOW),
        ("b-70", 70, NOW),
        ("c-90-old", 90, NOW - timedelta(days=2)),
        ("e-90-new", 90, NOW),
        ("d-90-new", 90, NOW),
    ]:
        put_priority_item(database, fixture, decision, identity, score=score, discovered=discovered)
    reader = service(database, fixture, decision)
    expected = ["e-90-new", "d-90-new", "c-90-old", "b-70", "a-null"]
    assert [row.program_name for row in reader.inbox().items] == expected
    assert reader.inbox() == reader.inbox()


@pytest.mark.parametrize(
    "scores,expected",
    [
        ((90, 70, None), ["item-1", "item-2", "item-3"]),
        ((None, 90, 70), ["item-2", "item-3", "item-1"]),
    ],
)
def test_priority_scores_override_id_order(tmp_path, scores, expected):
    database, fixture, decision = priority_workspace(tmp_path)
    for number, score in enumerate(scores, 1):
        put_priority_item(database, fixture, decision, f"item-{number}", score=score)
    assert [r.program_name for r in service(database, fixture, decision).inbox().items] == expected


def test_priority_versions_do_not_reset_discovery_and_restart_order(tmp_path):
    from datetime import timedelta

    from qualor.persistence import Database
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database, fixture, decision = priority_workspace(tmp_path)
    original, _ = put_priority_item(
        database,
        fixture,
        decision,
        "a-old",
        with_decision=False,
        with_run=False,
        discovered=NOW - timedelta(days=2),
    )
    put_priority_item(database, fixture, decision, "z-new", with_decision=False, with_run=False)
    lifecycle = WorkspaceLifecycle(database)
    changed = original.model_copy(
        update={"deadlines": (NOW,), "created_at": NOW, "updated_at": NOW}
    )
    lifecycle.persist_observation(changed)
    lifecycle.persist_observation(
        original.model_copy(update={"created_at": NOW, "updated_at": NOW})
    )
    before = service(database, fixture, decision).inbox()
    assert [row.program_name for row in before.items] == ["z-new", "a-old"]
    assert before.items[1].version == 3
    assert before.items[1].discovered_at == NOW - timedelta(days=2)
    # Database transactions close their connections; construct all services anew.
    after = service(Database(database.path), fixture, decision).inbox()
    assert before == after


def test_priority_global_order_before_bounded_pages_and_single_clock(tmp_path):
    database, fixture, decision = priority_workspace(tmp_path)
    for identity, rec in [
        ("a-low", "SKIP"),
        ("b-low", "SKIP"),
        ("y-high", "APPLY"),
        ("z-high", "APPLY"),
    ]:
        put_priority_item(database, fixture, decision, identity, recommendation=rec)
    reader = service(database, fixture, decision)
    calls = []

    def clock():
        calls.append(NOW)
        return NOW

    reader.clock = clock
    first = reader.inbox(limit=2)
    assert len(calls) == 1
    second = reader.inbox(limit=2, offset=2)
    assert [r.program_name for r in first.items + second.items] == [
        "y-high",
        "z-high",
        "a-low",
        "b-low",
    ]
    assert [r.priority_rank for r in first.items + second.items] == [0, 1, 2, 3]
    assert first.page.total == 4 and first.page.has_more
    assert not second.page.has_more


def test_priority_failed_refresh_uses_safety_but_does_not_blanket_demote_stale(tmp_path):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database, fixture, decision = priority_workspace(tmp_path)
    ids = {}
    for identity, rec in [("a-stale", "APPLY"), ("b-watch", "WATCH"), ("z-safe", "PREPARE")]:
        record, _ = put_priority_item(database, fixture, decision, identity, recommendation=rec)
        ids[identity] = record.id
    lifecycle = WorkspaceLifecycle(database)
    lifecycle.mark_refresh_failed(ids["a-stale"], NOW)
    lifecycle.mark_refresh_failed(ids["b-watch"], NOW)
    rows = service(database, fixture, decision).inbox().items
    assert [row.program_name for row in rows] == ["z-safe", "a-stale", "b-watch"]
    assert rows[1].recommendation == "APPLY" and not rows[1].human_action_available
    assert rows[1].freshness == rows[2].freshness == "STALE"


def test_priority_completed_without_selection_requires_review(tmp_path):
    database, fixture, decision = priority_workspace(tmp_path)
    put_priority_item(database, fixture, decision, "a-watch", recommendation="WATCH")
    put_priority_item(database, fixture, decision, "z-unresolved", with_decision=False)
    rows = service(database, fixture, decision).inbox().items
    assert [row.program_name for row in rows] == ["z-unresolved", "a-watch"]
    assert rows[0].best_project is None and rows[0].recommendation is None
    assert rows[0].presentation_state == "NEEDS_REVIEW"


@pytest.mark.parametrize(
    "state", ["CREATED", "RUNNING", "PARTIAL", "FAILED", "CANCELLED", "BUDGET_STOPPED"]
)
def test_priority_current_run_state_precedes_retained_recommendation(tmp_path, state):
    database, fixture, decision = priority_workspace(tmp_path)
    put_priority_item(database, fixture, decision, "watch", recommendation="WATCH")
    put_priority_item(database, fixture, decision, "retained", state=state)
    rows = service(database, fixture, decision).inbox().items
    expected = ["watch", "retained"] if state in {"CREATED", "RUNNING"} else ["retained", "watch"]
    assert [r.program_name for r in rows] == expected
    retained = next(r for r in rows if r.program_name == "retained")
    assert retained.recommendation == "APPLY" and retained.run_state == state
    assert retained.presentation_state == (
        "VERIFYING" if state in {"CREATED", "RUNNING"} else "NEEDS_REVIEW"
    )
    assert not retained.human_action_available


def test_priority_newest_uses_exact_fractional_instants_not_id_order(tmp_path):
    from datetime import timedelta

    database, fixture, decision = priority_workspace(tmp_path)
    put_priority_item(database, fixture, decision, "item-1", discovered=NOW)
    put_priority_item(
        database, fixture, decision, "item-2", discovered=NOW - timedelta(microseconds=1)
    )
    rows = service(database, fixture, decision).inbox().items
    assert rows[1].opportunity_id < rows[0].opportunity_id
    assert [r.program_name for r in rows] == ["item-1", "item-2"]


@pytest.mark.parametrize("deadlines", [(), (NOW,), (NOW.date(),)])
def test_priority_deadline_does_not_cross_attention_tier(tmp_path, deadlines):
    from datetime import timedelta

    database, fixture, decision = priority_workspace(tmp_path)
    put_priority_item(database, fixture, decision, "apply", deadlines=deadlines)
    put_priority_item(
        database,
        fixture,
        decision,
        "prepare",
        recommendation="PREPARE",
        deadlines=(NOW + timedelta(days=1),),
    )
    rows = service(database, fixture, decision).inbox().items
    assert [r.program_name for r in rows] == ["apply", "prepare"]


@pytest.mark.parametrize("deadlines", [(), (NOW,), (NOW.date(),)])
def test_priority_deadline_denial_cannot_hide_failed_refresh(tmp_path, deadlines):
    from qualor.workspace.lifecycle import WorkspaceLifecycle

    database, fixture, decision = priority_workspace(tmp_path)
    failed, _ = put_priority_item(database, fixture, decision, "failed", deadlines=deadlines)
    put_priority_item(
        database, fixture, decision, "safe", recommendation="PREPARE", deadlines=deadlines
    )
    WorkspaceLifecycle(database).mark_refresh_failed(failed.id, NOW)
    rows = service(database, fixture, decision).inbox().items
    assert [r.program_name for r in rows] == ["safe", "failed"]
    assert rows[1].freshness == "STALE" and rows[1].recommendation == "APPLY"
    assert rows[1].presentation_state == "NEEDS_REVIEW"
    assert rows[0].presentation_state == "EVALUATED"
    assert not rows[1].human_action_available


@pytest.mark.parametrize("age_hours,freshness", [(7, "STALE"), (-1, "UNKNOWN")])
def test_priority_unknown_deadline_cannot_mask_nonfresh_proof(tmp_path, age_hours, freshness):
    from datetime import timedelta

    database, fixture, decision = priority_workspace(tmp_path)
    put_priority_item(
        database,
        fixture,
        decision,
        "unsafe",
        deadlines=(),
        evidence_retrieved_at=NOW - timedelta(hours=age_hours),
    )
    put_priority_item(database, fixture, decision, "safe", recommendation="PREPARE", deadlines=())
    rows = service(database, fixture, decision).inbox().items
    assert [r.program_name for r in rows] == ["safe", "unsafe"]
    assert rows[1].freshness == freshness
    assert rows[1].recommendation == "APPLY"
    assert rows[1].presentation_state == "NEEDS_REVIEW"


@pytest.mark.parametrize("deadlines", [(), (NOW,)])
def test_priority_deadline_cannot_hide_ambiguous_required_proof(tmp_path, deadlines):
    from qualor.workspace.models import ApprovalBindings
    from qualor.workspace.store import WorkspaceStore

    database, fixture, decision = priority_workspace(tmp_path)
    opportunity, _ = put_priority_item(
        database, fixture, decision, "ambiguous", deadlines=deadlines
    )
    put_priority_item(
        database, fixture, decision, "safe", recommendation="PREPARE", deadlines=deadlines
    )
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        proof = store.evidence.list_for_opportunity(opportunity.id, 1)[0]
        store.evidence.put_evidence(proof.model_copy(update={"version": 2}), opportunity.id, 1)
    reader = service(database, fixture, decision)
    before = reader.workspace(opportunity.id).decision.primary_action
    assert before.reason == ("DEADLINE_UNKNOWN" if not deadlines else "DEADLINE_PASSED")
    binding = ApprovalBindings(
        actor_id=fixture.founder.id,
        opportunity_id=opportunity.id,
        **before.approval_request.model_dump(),
    )
    authority = reader.approvals.for_workspace_request(binding, NOW)
    assert authority.inspect_consequential_safety(binding, NOW) == "EVIDENCE_CHANGED"
    assert authority.inspect_request(binding, NOW).reason == before.reason
    assert [row.program_name for row in reader.inbox().items] == ["safe", "ambiguous"]
    assert reader.inbox().items[1].presentation_state == "NEEDS_REVIEW"
    assert reader.inbox().items[1].recommendation == "APPLY"
    assert reader.workspace(opportunity.id).decision.primary_action == before
    with database.transaction() as connection:
        assert WorkspaceStore(connection).approvals.list_for_opportunity(opportunity.id) == ()


def test_priority_stale_supplementary_proof_does_not_override_valid_authority(tmp_path):
    from datetime import timedelta

    from qualor.workspace.store import WorkspaceStore

    database, fixture, decision = priority_workspace(tmp_path)
    opportunity, _ = put_priority_item(database, fixture, decision, "apply")
    put_priority_item(database, fixture, decision, "prepare", recommendation="PREPARE")
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        proof = store.evidence.list_for_opportunity(opportunity.id, 1)[0]
        store.evidence.put_evidence(
            proof.model_copy(
                update={
                    "id": "unreferenced-supplement",
                    "retrieved_at": NOW - timedelta(days=2),
                }
            ),
            opportunity.id,
            1,
        )
    reader = service(database, fixture, decision)
    canvas = reader.workspace(opportunity.id).decision
    assert canvas.freshness == "STALE" and canvas.primary_action.available
    assert canvas.primary_action.reason == "VALID"
    assert [row.program_name for row in reader.inbox().items] == ["apply", "prepare"]
    assert reader.inbox().items[0].presentation_state == "EVALUATED"
