"""File-backed approval safety cases; fixtures never represent LIVE authorization."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.persistence import Database
from qualor.workspace.lifecycle import WorkspaceLifecycle
from qualor.workspace.store import WorkspaceStore
from qualor.workspace.versioning import opportunity_semantic_digest

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)
FIXTURE = Path(__file__).parents[1] / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def setup(
    tmp_path, *, deadline=None, recommendation=None, evidence_change=None, decision_change=None
):
    from qualor.workspace.approval import ApprovalService
    from qualor.workspace.models import ApprovalBindings

    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    if deadline is not None:
        fixture = fixture.model_copy(
            update={"opportunity": fixture.opportunity.model_copy(update={"deadlines": deadline})}
        )
    decision = decide_fixture(fixture).selected_decision
    assert decision is not None
    if recommendation:
        decision = decision.model_copy(update={"recommendation": recommendation})
    if decision_change:
        decision = decision_change(decision)
    database = Database(tmp_path / "approval.db")
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        store.projects.put_project(fixture.projects[0].project)
        store.opportunities.put_opportunity_version(
            fixture.opportunity, content_hash=opportunity_semantic_digest(fixture.opportunity)
        )
        store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        for evidence in fixture.evidence:
            if evidence_change and evidence.id == "e_DEADLINE":
                evidence = evidence.model_copy(update=evidence_change)
            store.evidence.put_evidence(evidence, fixture.opportunity.id, 1)
    bindings = ApprovalBindings(
        actor_id=fixture.founder.id,
        opportunity_id=fixture.opportunity.id,
        opportunity_hash=opportunity_semantic_digest(fixture.opportunity),
        opportunity_version=1,
        founder_profile_id=fixture.founder.id,
        founder_profile_version=1,
        project_id=decision.project_id,
        project_version=1,
        decision_id=decision.id,
        decision_version=1,
        policy_versions=decision.policy_versions,
        action="GENERATE_DRAFT_PACK",
    )
    service = ApprovalService(
        database,
        actor_id=fixture.founder.id,
        policy_versions=decision.policy_versions,
        mode="FIXTURE",
    )
    return service, bindings, fixture, decision


def request(service, bindings, now=NOW, deadline=None):
    data = bindings.model_dump(warnings=False)
    data["profile_version"] = data.pop("founder_profile_version")
    return service.request_approval(**data, deadline=deadline, now=now)


def confirm(service, bindings, approval=None, key="confirm", now=NOW):
    approval = approval or request(service, bindings)
    return service.confirm_approval(approval.id, key, now, expected_versions=bindings)


def consume(service, bindings, approval, key="consume", now=NOW):
    return service.consume_approval(approval.id, key, now, expected_versions=bindings)


def reopened(service):
    from qualor.workspace.approval import ApprovalService

    return ApprovalService(
        Database(service.database.path),
        actor_id=service.actor_id,
        policy_versions=service.policy_versions,
        mode="FIXTURE",
    )


def denied(call, reason):
    from qualor.workspace.approval import ApprovalDenied

    with pytest.raises(ApprovalDenied) as error:
        call()
    assert error.value.reason == reason


def test_a_pending_requires_confirmation_and_exact_snapshot_becomes_actionable(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    pending = request(service, bindings)
    assert pending.state == "PENDING_APPROVAL"
    assert not service.validate_approval(pending.id, bindings, NOW).actionable
    approved = confirm(service, bindings, pending)
    assert approved.state == "APPROVED_FOR_PREPARATION"
    assert approved.consumed_at is None
    assert service.validate_approval(approved.id, bindings, NOW).actionable
    assert reopened(service).validate_approval(approved.id, bindings, NOW).actionable


def test_b_wrong_action_is_denied(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    wrong = bindings.model_copy(update={"action": "SUBMIT"})
    denied(lambda: request(service, wrong), "ACTION_MISMATCH")
    approved = confirm(service, bindings)
    denied(lambda: consume(service, wrong, approved), "ACTION_MISMATCH")


def test_c_default_expiry_and_equality_after_restart(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    assert approved.expires_at == datetime(2026, 9, 6, 12, tzinfo=UTC)
    denied(
        lambda: consume(reopened(service), bindings, approved, now=NOW + timedelta(hours=24)),
        "EXPIRED",
    )


def test_d_verified_sooner_deadline_bounds_expiry(tmp_path):
    deadline = NOW + timedelta(hours=2)
    service, bindings, _, _ = setup(tmp_path, deadline=(deadline,), recommendation="PREPARE")
    pending = request(service, bindings, deadline=deadline)
    assert pending.expires_at == datetime(2026, 9, 5, 14, tzinfo=UTC)
    denied(lambda: confirm(service, bindings, pending, now=deadline), "EXPIRED")


def test_e_past_deadline_denies_request(tmp_path):
    service, bindings, _, _ = setup(tmp_path, deadline=(NOW - timedelta(seconds=1),))
    denied(lambda: request(service, bindings), "DEADLINE_PASSED")


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("opportunity_version", 2, "VERSION_MISMATCH"),
        ("opportunity_hash", "0" * 64, "VERSION_MISMATCH"),
        ("opportunity_id", "other", "IDENTITY_MISMATCH"),
        ("actor_id", "other", "ACTOR_MISMATCH"),
        ("founder_profile_id", "other", "IDENTITY_MISMATCH"),
        ("founder_profile_version", 2, "VERSION_MISMATCH"),
        ("project_id", "other", "IDENTITY_MISMATCH"),
        ("project_version", 2, "VERSION_MISMATCH"),
        ("decision_id", "other", "IDENTITY_MISMATCH"),
        ("decision_version", 2, "VERSION_MISMATCH"),
    ],
)
def test_f_i_j_k_l_bound_inputs_cannot_be_retargeted(tmp_path, field, value, reason):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    wrong = bindings.model_copy(update={field: value})
    denied(lambda: consume(service, wrong, approved), reason)
    assert service.validate_approval(approved.id, bindings, NOW).actionable


@pytest.mark.parametrize("entity", ["opportunity", "founder", "project", "decision"])
def test_f_g_current_version_change_revokes_durably(tmp_path, entity):
    service, bindings, fixture, decision = setup(tmp_path)
    approved = confirm(service, bindings)
    with service.database.transaction() as connection:
        store = WorkspaceStore(connection)
        if entity == "opportunity":
            for version in (2, 3):
                store.opportunities.put_opportunity_version(
                    fixture.opportunity.model_copy(update={"version": version}),
                    content_hash="b" * 64 if version == 2 else bindings.opportunity_hash,
                )
        elif entity == "founder":
            store.profiles.put_founder(fixture.founder.model_copy(update={"version": 2}))
        elif entity == "project":
            store.projects.put_project(
                fixture.projects[0].project.model_copy(update={"version": 2})
            )
        else:
            store.decisions.put_decision(
                decision.model_copy(update={"version": 2}), founder_profile_id=fixture.founder.id
            )
    result = reopened(service).validate_approval(approved.id, bindings, NOW)
    assert not result.actionable
    assert result.reason == "VERSION_MISMATCH"
    with service.database.transaction() as connection:
        history = WorkspaceStore(connection).approvals.list_for_opportunity(bindings.opportunity_id)
    assert history[-1].state == "REVOKED_APPROVAL"
    assert history[1] == approved
    denied(lambda: consume(reopened(service), bindings, approved), "REVOKED")


def test_h_current_trusted_policy_change_revokes(tmp_path):
    from qualor.workspace.approval import ApprovalService

    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    changed = ApprovalService(
        service.database,
        actor_id=service.actor_id,
        policy_versions=service.policy_versions.model_copy(update={"effort": 2}),
        mode="FIXTURE",
    )
    assert changed.validate_approval(approved.id, bindings, NOW).reason == "POLICY_MISMATCH"
    assert reopened(service).validate_approval(approved.id, bindings, NOW).reason == "REVOKED"


def test_m_explicit_revocation_preserves_audit_and_restart(tmp_path):
    from qualor.workspace.models import ApprovalChange

    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    revoked = service.revoke_invalid_approvals(ApprovalChange(project_id=bindings.project_id), NOW)
    assert len(revoked) == 1
    assert revoked[0].state == "REVOKED_APPROVAL"
    assert (
        service.revoke_invalid_approvals(ApprovalChange(project_id=bindings.project_id), NOW) == ()
    )
    denied(lambda: consume(reopened(service), bindings, approved), "REVOKED")
    with service.database.transaction() as connection:
        assert WorkspaceStore(connection).approvals.get_approval(approved.id, 2) == approved


def test_n_o_p_consume_once_receipts_survive_restart_and_expiry(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    first = consume(service, bindings, approved)
    assert not first.replayed
    assert first.record.consumed_at == NOW
    retry = consume(reopened(service), bindings, approved, now=NOW + timedelta(days=2))
    assert retry.replayed and retry.record == first.record
    assert confirm(reopened(service), bindings, approved, now=NOW + timedelta(days=2)) == approved
    denied(lambda: consume(service, bindings, approved, key="different"), "CONSUMED")
    assert not reopened(service).validate_approval(approved.id, bindings, NOW).actionable
    with service.database.transaction() as connection:
        assert WorkspaceStore(connection).load_approval_graph(bindings.opportunity_id)[1:] == (
            (),
            (),
        )


@pytest.mark.parametrize("same_key", [False, True])
def test_q_competing_consumers_have_exactly_one_new_authorization(tmp_path, same_key):
    from qualor.workspace.approval import ApprovalDenied

    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)

    def attempt(index):
        try:
            return consume(
                reopened(service), bindings, approved, key="same" if same_key else str(index)
            )
        except ApprovalDenied as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [1, 2]))
    assert sum(getattr(result, "replayed", None) is False for result in outcomes) == 1
    assert sum(getattr(result, "replayed", None) is True for result in outcomes) == int(same_key)
    if not same_key:
        assert "CONSUMED" in outcomes


def test_r_abort_composed_transaction_does_not_consume(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    with pytest.raises(RuntimeError, match="abort"):
        with service.database.transaction(immediate=True) as connection:
            result = service.consume_in_transaction(
                WorkspaceStore(connection), approved.id, "consume", NOW, expected_versions=bindings
            )
            assert not result.replayed
            raise RuntimeError("abort")
    assert reopened(service).validate_approval(approved.id, bindings, NOW).actionable
    assert not consume(service, bindings, approved).replayed


@pytest.mark.parametrize("recommendation", ["WATCH", "SKIP"])
def test_non_actionable_recommendations_cannot_request(tmp_path, recommendation):
    service, bindings, _, _ = setup(tmp_path, recommendation=recommendation)
    denied(lambda: request(service, bindings), "DECISION_NOT_ACTIONABLE")


@pytest.mark.parametrize(
    "change",
    [
        {"extraction_state": "UNVERIFIED"},
        {"retrieved_at": NOW - timedelta(days=2)},
        {"last_refresh_failed_at": NOW},
        {"normalized_field": "LICENSE"},
    ],
)
def test_current_required_evidence_cannot_be_bypassed(tmp_path, change):
    service, bindings, _, _ = setup(tmp_path, evidence_change=change)
    denied(lambda: request(service, bindings), "EVIDENCE_NOT_ACTIONABLE")


def test_failed_refresh_blocks_confirmation_and_consumption(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    pending = request(service, bindings)
    WorkspaceLifecycle(service.database).mark_refresh_failed(bindings.opportunity_id, NOW)
    denied(lambda: confirm(service, bindings, pending), "EVIDENCE_NOT_ACTIONABLE")


@pytest.mark.parametrize("deadline", [(), (datetime(2026, 9, 15).date(),)])
def test_unresolved_deadline_is_visible_and_cannot_be_approved(tmp_path, deadline):
    service, bindings, _, _ = setup(tmp_path, deadline=deadline)
    denied(lambda: request(service, bindings), "DEADLINE_UNKNOWN")


def test_naive_time_is_rejected(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        request(service, bindings, now=datetime(2026, 9, 5, 12))


def test_key_cannot_be_reused_for_different_approval(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    first = confirm(service, bindings)
    second = request(service, bindings)
    denied(lambda: confirm(service, bindings, second), "IDEMPOTENCY_CONFLICT")
    consumed = consume(service, bindings, first)
    assert not consumed.replayed
    second = confirm(service, bindings, second, key="second-confirm")
    denied(lambda: consume(service, bindings, second), "IDEMPOTENCY_CONFLICT")


def test_stale_conflict_only_evidence_cannot_authorize(tmp_path):
    service, bindings, fixture, _ = setup(tmp_path)
    stale = next(e for e in fixture.evidence if e.id == "conflict_LICENSE").model_copy(
        update={"version": 2, "retrieved_at": NOW - timedelta(days=2)}
    )
    with service.database.transaction() as connection:
        WorkspaceStore(connection).evidence.put_evidence(stale, bindings.opportunity_id, 1)
    denied(lambda: request(service, bindings), "EVIDENCE_CHANGED")


def test_observed_expiry_never_revives_under_earlier_time_after_restart(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    assert not service.validate_approval(approved.id, bindings, NOW + timedelta(days=1)).actionable
    assert not reopened(service).validate_approval(approved.id, bindings, NOW).actionable


def test_gate_policy_mismatch_cannot_authorize(tmp_path):
    def change(decision):
        return decision.model_copy(
            update={
                "eligibility_gate": decision.eligibility_gate.model_copy(
                    update={"policy_version": 2}
                )
            }
        )

    service, bindings, _, _ = setup(tmp_path, decision_change=change)
    denied(lambda: request(service, bindings), "POLICY_MISMATCH")


def test_evaluation_policy_mismatch_cannot_authorize(tmp_path):
    def change(decision):
        gate = decision.eligibility_gate
        evaluations = (
            gate.evaluations[0].model_copy(update={"policy_version": 2}),
            *gate.evaluations[1:],
        )
        return decision.model_copy(
            update={"eligibility_gate": gate.model_copy(update={"evaluations": evaluations})}
        )

    service, bindings, _, _ = setup(tmp_path, decision_change=change)
    denied(lambda: request(service, bindings), "EVIDENCE_NOT_ACTIONABLE")


@pytest.mark.parametrize("stage", ["request", "confirm", "consume"])
def test_wrong_actor_service_cannot_act(tmp_path, stage):
    from qualor.workspace.approval import ApprovalService

    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    wrong = ApprovalService(
        service.database,
        actor_id="intruder",
        policy_versions=service.policy_versions,
        mode="FIXTURE",
    )
    calls = {
        "request": lambda: request(wrong, bindings),
        "confirm": lambda: confirm(wrong, bindings, approved),
        "consume": lambda: consume(wrong, bindings, approved),
    }
    denied(calls[stage], "ACTOR_MISMATCH")


def test_fixture_approval_never_becomes_live(tmp_path):
    from qualor.workspace.approval import ApprovalService

    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    live = ApprovalService(
        service.database,
        actor_id=service.actor_id,
        policy_versions=service.policy_versions,
        mode="LIVE",
    )
    denied(lambda: consume(live, bindings, approved), "MODE_MISMATCH")
    denied(lambda: request(live, bindings), "EVIDENCE_NOT_ACTIONABLE")


@pytest.mark.parametrize("phase", ["confirm", "consume"])
def test_profile_change_on_write_path_revokes_even_when_denied(tmp_path, phase):
    service, bindings, fixture, _ = setup(tmp_path)
    approval = request(service, bindings)
    if phase == "consume":
        approval = confirm(service, bindings, approval)
    with service.database.transaction() as connection:
        WorkspaceStore(connection).profiles.put_founder(
            fixture.founder.model_copy(update={"version": 2})
        )
    call = confirm if phase == "confirm" else consume
    denied(lambda: call(service, bindings, approval), "VERSION_MISMATCH")
    assert reopened(service).validate_approval(approval.id, bindings, NOW).reason == "REVOKED"


def test_confirm_does_not_extend_request_expiry(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    pending = request(service, bindings)
    approved = confirm(service, bindings, pending, now=NOW + timedelta(hours=1))
    assert approved.created_at == NOW
    assert approved.expires_at == datetime(2026, 9, 6, 12, tzinfo=UTC)


def test_caller_cannot_extend_persisted_deadline(tmp_path):
    deadline = NOW + timedelta(hours=2)
    service, bindings, _, _ = setup(tmp_path, deadline=(deadline,), recommendation="PREPARE")
    assert request(service, bindings).expires_at == deadline
    denied(
        lambda: request(service, bindings, deadline=NOW + timedelta(days=1)), "DEADLINE_MISMATCH"
    )


def test_calendar_expiry_policy_does_not_invent_timezone(tmp_path):
    from qualor.workspace.approval import approval_expiry

    service, bindings, _, _ = setup(tmp_path)
    assert approval_expiry(NOW, NOW.date()) == datetime(2026, 9, 6, 12, tzinfo=UTC)
    assert approval_expiry(NOW, None) == datetime(2026, 9, 6, 12, tzinfo=UTC)


def test_consume_requires_caller_transaction(tmp_path):
    from qualor.persistence.repositories import TransactionRequiredError

    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    connection = service.database.connect()
    try:
        with pytest.raises(TransactionRequiredError):
            service.consume_in_transaction(
                WorkspaceStore(connection), approved.id, "consume", NOW, expected_versions=bindings
            )
    finally:
        connection.close()


def test_consumption_rechecks_evidence_after_confirmation(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    WorkspaceLifecycle(service.database).mark_refresh_failed(bindings.opportunity_id, NOW)
    denied(lambda: consume(service, bindings, approved), "EVIDENCE_NOT_ACTIONABLE")


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "REVIEW_REQUIRED"),
        ("critical_coverage", ()),
    ],
)
def test_critical_unknown_or_empty_coverage_cannot_authorize(tmp_path, field, value):
    def change(decision):
        return decision.model_copy(
            update={"eligibility_gate": decision.eligibility_gate.model_copy(update={field: value})}
        )

    service, bindings, _, _ = setup(tmp_path, decision_change=change)
    denied(
        lambda: request(service, bindings),
        "DECISION_NOT_ACTIONABLE" if field == "state" else "EVIDENCE_NOT_ACTIONABLE",
    )


def test_conflict_cannot_be_overridden_by_apply_label(tmp_path):
    def change(decision):
        conflict = decision.conflict.model_copy(update={"status": "REVIEW_REQUIRED"})
        return decision.model_copy(
            update={"conflict": conflict, "conflict_status": conflict.status}
        )

    service, bindings, _, _ = setup(tmp_path, decision_change=change)
    denied(lambda: request(service, bindings), "DECISION_NOT_ACTIONABLE")


def test_new_decision_identity_for_same_graph_revokes_old_approval(tmp_path):
    service, bindings, _, decision = setup(tmp_path)
    approved = confirm(service, bindings)
    later = NOW + timedelta(seconds=1)
    replacement = decision.model_copy(
        update={"id": "reevaluated-decision", "created_at": later, "updated_at": later}
    )
    with service.database.transaction() as connection:
        WorkspaceStore(connection).decisions.put_decision(
            replacement, founder_profile_id=bindings.founder_profile_id
        )
    assert service.validate_approval(approved.id, bindings, later).reason == "GRAPH_MISMATCH"
    assert reopened(service).validate_approval(approved.id, bindings, later).reason == "REVOKED"


def test_actual_persisted_decision_founder_link_mismatch_denied(tmp_path):
    service, bindings, fixture, decision = setup(tmp_path)
    with service.database.transaction() as connection:
        store = WorkspaceStore(connection)
        other = fixture.founder.model_copy(update={"id": "different-founder"})
        store.profiles.put_founder(other)
        store.decisions.put_decision(
            decision.model_copy(update={"id": "other-decision"}), founder_profile_id=other.id
        )
    wrong = bindings.model_copy(update={"decision_id": "other-decision"})
    denied(lambda: request(service, wrong), "GRAPH_MISMATCH")


def test_expired_record_retains_expired_reason_after_restart(tmp_path):
    service, bindings, _, _ = setup(tmp_path)
    approved = confirm(service, bindings)
    expiry = NOW + timedelta(hours=24)
    assert service.validate_approval(approved.id, bindings, expiry).reason == "EXPIRED"
    assert reopened(service).validate_approval(approved.id, bindings, expiry).reason == "EXPIRED"


@pytest.mark.parametrize("stage", ["validate", "confirm", "consume", "request"])
def test_changed_critical_proof_cannot_launder_old_decision(tmp_path, stage):
    service, bindings, fixture, _ = setup(tmp_path)
    pending = request(service, bindings)
    approval = pending if stage == "confirm" else confirm(service, bindings, pending)
    replacement = next(e for e in fixture.evidence if e.id == "e_LICENSE").model_copy(
        update={
            "version": 2,
            "content_hash": "9" * 64,
            "supporting_excerpt": "Updated official rules prohibit the project license.",
        }
    )
    with service.database.transaction() as connection:
        WorkspaceStore(connection).evidence.put_evidence(replacement, bindings.opportunity_id, 1)
    if stage == "validate":
        result = reopened(service).validate_approval(approval.id, bindings, NOW)
        assert result.reason == "EVIDENCE_CHANGED"
        assert not result.actionable
    elif stage == "request":
        denied(lambda: request(reopened(service), bindings), "EVIDENCE_CHANGED")
        # Inspecting an existing approval must also durably revoke its authority.
        assert service.validate_approval(approval.id, bindings, NOW).reason == "EVIDENCE_CHANGED"
    else:
        action = confirm if stage == "confirm" else consume
        denied(lambda: action(reopened(service), bindings, approval), "EVIDENCE_CHANGED")
    assert reopened(service).validate_approval(approval.id, bindings, NOW).reason == "REVOKED"
    with service.database.transaction() as connection:
        history = WorkspaceStore(connection).approvals.list_for_opportunity(bindings.opportunity_id)
        assert history[-1].state == "REVOKED_APPROVAL"
        assert history[-1].revocation_reason == "EVIDENCE_CHANGED"
        assert history[-1].consumed_at is None


@pytest.mark.parametrize("evidence_id", ["e_LICENSE", "conflict_LICENSE"])
def test_multiple_versions_never_guess_evaluated_proof_even_same_hash(tmp_path, evidence_id):
    service, bindings, fixture, _ = setup(tmp_path)
    approval = confirm(service, bindings)
    duplicate = next(e for e in fixture.evidence if e.id == evidence_id).model_copy(
        update={"version": 2}
    )
    with service.database.transaction() as connection:
        WorkspaceStore(connection).evidence.put_evidence(duplicate, bindings.opportunity_id, 1)
    denied(lambda: request(service, bindings), "EVIDENCE_CHANGED")
    denied(lambda: consume(service, bindings, approval), "EVIDENCE_CHANGED")
    assert reopened(service).validate_approval(approval.id, bindings, NOW).reason == "REVOKED"


def test_new_unambiguous_proof_reevaluation_and_new_approval_restore_actionability(tmp_path):
    service, bindings, fixture, _ = setup(tmp_path)
    old_approval = confirm(service, bindings)
    proof = next(e for e in fixture.evidence if e.id == "e_LICENSE")
    replacement = proof.model_copy(update={"version": 2, "content_hash": "9" * 64})
    later = NOW + timedelta(seconds=1)
    # Explicit new immutable proof ID, supplied to the existing deterministic core.
    fresh = proof.model_copy(
        update={
            "id": "new-license-proof",
            "retrieved_at": later,
            "created_at": later,
            "updated_at": later,
            "content_hash": "9" * 64,
        }
    )
    rules = tuple(
        rule.model_copy(
            update={
                "evidence_ids": tuple(
                    fresh.id if ref == proof.id else ref for ref in rule.evidence_ids
                )
            }
        )
        for rule in fixture.eligibility_rules
    )
    current = DecisionFixture.model_validate(
        {
            **fixture.model_dump(),
            "evidence": tuple(fresh if item.id == proof.id else item for item in fixture.evidence),
            "eligibility_rules": rules,
            "evaluated_at": later,
        }
    )
    decision = decide_fixture(current).selected_decision
    assert decision is not None and decision.recommendation == "APPLY"
    with service.database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.evidence.put_evidence(replacement, bindings.opportunity_id, 1)
    denied(lambda: consume(service, bindings, old_approval), "EVIDENCE_CHANGED")
    with service.database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.evidence.put_evidence(fresh, bindings.opportunity_id, 1)
        store.decisions.put_decision(decision, founder_profile_id=bindings.founder_profile_id)
    new_bindings = bindings.model_copy(
        update={"decision_id": decision.id, "decision_version": decision.version}
    )
    pending = request(reopened(service), new_bindings, now=later)
    approved = confirm(service, new_bindings, pending, key="new-confirm", now=later)
    result = consume(reopened(service), new_bindings, approved, key="new-consume", now=later)
    assert not result.replayed
    assert result.record.id != old_approval.id
    assert reopened(service).validate_approval(old_approval.id, bindings, later).reason == "REVOKED"


def test_evidence_id_ambiguity_in_another_opportunity_scope_is_not_hidden(tmp_path):
    from qualor.domain import OpportunityRecord

    service, bindings, fixture, _ = setup(tmp_path)
    approval = confirm(service, bindings)
    other = OpportunityRecord.model_validate(
        {**fixture.opportunity.model_dump(), "edition": "other"}
    )
    proof = next(e for e in fixture.evidence if e.id == "e_LICENSE").model_copy(
        update={"version": 2, "content_hash": "9" * 64}
    )
    with service.database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.opportunities.put_opportunity_version(
            other, content_hash=opportunity_semantic_digest(other)
        )
        store.evidence.put_evidence(proof, other.id, 1)
    denied(lambda: request(service, bindings), "EVIDENCE_CHANGED")
    denied(lambda: consume(service, bindings, approval), "EVIDENCE_CHANGED")
    assert reopened(service).validate_approval(approval.id, bindings, NOW).reason == "REVOKED"
