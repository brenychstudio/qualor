"""The server owns product state. These tests pin the matrix and its precedence.

Every case asserts the state, the underlying recommendation, evidence availability, the
primary presentation action, approval availability and pack availability separately, so a
product state can never quietly rewrite deterministic decision authority.
"""

import pytest

from qualor.workspace.product_state import (
    PRECEDENCE,
    ProductAction,
    ProductState,
    ProductStateInputs,
    derive_product_state,
)


def inputs(**changes) -> ProductStateInputs:
    """A healthy, fully evaluated APPLY decision. Each test degrades exactly one thing."""
    base = dict(
        profile_present=True,
        result_count=3,
        run_state="COMPLETED",
        provider_state=None,
        termination_reason="SUFFICIENT_CRITICAL_EVIDENCE",
        freshness="FRESH",
        coverage_states=("EVALUATED", "EVALUATED"),
        evidence_count=4,
        eligibility_states=("PASS",),
        recommendation="APPLY",
        approval_state=None,
        approval_reason=None,
        pack_id=None,
        action_available=True,
        action_reason="VALID",
    )
    return ProductStateInputs(**{**base, **changes})


def test_healthy_workspace_reports_no_degraded_product_state():
    result = derive_product_state(inputs())
    assert result.state is None
    assert result.primary_action is None
    assert result.recommendation_visible is True
    assert result.evidence_available is True
    assert result.approval_available is True


def test_empty_profile_blocks_evaluation_and_hides_any_recommendation():
    result = derive_product_state(
        inputs(profile_present=False, recommendation=None, eligibility_states=(None,))
    )
    assert result.state is ProductState.EMPTY_PROFILE
    assert result.primary_action is ProductAction.CREATE_PROFILE
    assert result.recommendation_visible is False
    assert result.evidence_available is False
    assert result.approval_available is False
    assert result.draft_pack_available is False


def test_no_results_reports_an_empty_workspace_without_inventing_an_opportunity():
    result = derive_product_state(
        inputs(result_count=0, recommendation=None, eligibility_states=(None,), run_state=None)
    )
    assert result.state is ProductState.NO_RESULTS
    assert result.primary_action is ProductAction.ADJUST_SEARCH
    assert result.recommendation_visible is False
    assert result.evidence_available is False
    assert result.approval_available is False


def test_partial_source_failure_keeps_the_deterministic_decision_and_marks_coverage():
    result = derive_product_state(
        inputs(
            run_state="PARTIAL",
            termination_reason="NO_PROGRESS",
            coverage_states=("EVALUATED", "MISSING"),
        )
    )
    assert result.state is ProductState.PARTIAL_SOURCE_FAILURE
    assert result.primary_action is ProductAction.REVIEW_AVAILABLE_EVIDENCE
    assert result.recommendation_visible is True
    assert result.evidence_available is True
    assert result.coverage_complete is False


def test_stale_evidence_retains_prior_proof_without_renewing_actionability():
    # The approval authority already refuses non-FRESH evidence, so a stale workspace can
    # never present a VALID action capability. Product state reports that, it does not add
    # a second freshness rule of its own.
    result = derive_product_state(
        inputs(freshness="STALE", action_available=False, action_reason="DECISION_NOT_ACTIONABLE")
    )
    assert result.state is ProductState.STALE_EVIDENCE
    assert result.primary_action is ProductAction.REFRESH_EVIDENCE
    assert result.recommendation_visible is True
    assert result.evidence_available is True
    assert result.approval_available is False


def test_unknown_eligibility_never_reads_as_pass():
    result = derive_product_state(
        inputs(
            eligibility_states=(None,),
            recommendation="WATCH",
            action_available=False,
            action_reason="DECISION_NOT_ACTIONABLE",
        )
    )
    assert result.state is ProductState.UNKNOWN_ELIGIBILITY
    assert result.primary_action is ProductAction.RESOLVE_UNKNOWNS
    assert result.recommendation_visible is True
    assert result.evidence_available is True
    assert result.approval_available is False


def test_review_required_eligibility_is_also_unresolved():
    result = derive_product_state(
        inputs(
            eligibility_states=("REVIEW_REQUIRED",),
            recommendation="WATCH",
            action_available=False,
            action_reason="REVIEW_REQUIRED",
        )
    )
    assert result.state is ProductState.UNKNOWN_ELIGIBILITY


def test_budget_stopped_retains_admitted_evidence_without_fabricating_completion():
    result = derive_product_state(
        inputs(
            run_state="BUDGET_STOPPED",
            termination_reason="BUDGET_EXHAUSTED",
            action_available=False,
            action_reason="DECISION_NOT_ACTIONABLE",
        )
    )
    assert result.state is ProductState.BUDGET_STOPPED
    assert result.primary_action is ProductAction.REVIEW_AVAILABLE_EVIDENCE
    assert result.reason == "BUDGET_EXHAUSTED"
    assert result.evidence_available is True
    assert result.approval_available is False


def test_disconnected_live_provider_shows_the_last_snapshot_without_implying_progress():
    result = derive_product_state(
        inputs(
            run_state="FAILED",
            provider_state="DISCONNECTED_LIVE_PROVIDER",
            termination_reason="PROVIDER_DISCONNECTED",
            action_available=False,
            action_reason="EVIDENCE_NOT_ACTIONABLE",
        )
    )
    assert result.state is ProductState.DISCONNECTED_LIVE_PROVIDER
    assert result.primary_action is ProductAction.RECONNECT_PROVIDER
    assert result.evidence_available is True
    assert result.approval_available is False


def test_pending_approval_keeps_the_decision_visible_and_starts_no_draft():
    result = derive_product_state(
        inputs(approval_state="PENDING_APPROVAL", approval_reason="PENDING")
    )
    assert result.state is ProductState.PENDING_APPROVAL
    assert result.primary_action is ProductAction.REVIEW_APPROVAL
    assert result.recommendation_visible is True
    assert result.evidence_available is True
    assert result.draft_pack_available is False


def test_revoked_approval_exposes_the_bounded_server_cause():
    result = derive_product_state(
        inputs(
            approval_state="REVOKED_APPROVAL",
            approval_reason="CHANGE_REVOKED",
            action_available=False,
            action_reason="CHANGE_REVOKED",
        )
    )
    assert result.state is ProductState.REVOKED_APPROVAL
    assert result.primary_action is ProductAction.REVIEW_CHANGES
    assert result.reason == "CHANGE_REVOKED"
    assert result.recommendation_visible is True
    assert result.evidence_available is True
    assert result.approval_available is False


def test_finished_pack_stays_attributable_and_openable():
    result = derive_product_state(
        inputs(
            approval_state="DRAFT_READY",
            approval_reason="CONSUMED",
            pack_id="pack-1",
            action_available=False,
            action_reason="CONSUMED",
        )
    )
    assert result.state is ProductState.FINISHED_PACK
    assert result.primary_action is ProductAction.OPEN_APPLICATION_PACK
    assert result.draft_pack_available is True
    assert result.pack_id == "pack-1"
    assert result.evidence_available is True
    assert result.approval_available is False


# --- precedence edges -------------------------------------------------------------------


def test_partial_run_with_an_apply_decision_never_rewrites_the_recommendation():
    given = inputs(
        run_state="PARTIAL",
        termination_reason="MAX_STEPS",
        coverage_states=("EVALUATED", "MISSING"),
    )
    result = derive_product_state(given)
    assert given.recommendation == "APPLY"
    assert result.state is ProductState.PARTIAL_SOURCE_FAILURE
    assert result.recommendation_visible is True
    assert result.recommendation_override is None


def test_partial_run_with_complete_coverage_still_allows_a_server_approved_action():
    result = derive_product_state(
        inputs(
            run_state="PARTIAL",
            termination_reason="MAX_STEPS",
            action_available=True,
            action_reason="VALID",
        )
    )
    assert result.state is ProductState.PARTIAL_SOURCE_FAILURE
    assert result.coverage_complete is True
    assert result.approval_available is True


def test_stale_evidence_outranks_the_approval_it_invalidated():
    result = derive_product_state(
        inputs(
            freshness="STALE",
            approval_state="REVOKED_APPROVAL",
            approval_reason="EXPIRED",
            action_available=False,
            action_reason="EXPIRED",
        )
    )
    assert result.state is ProductState.STALE_EVIDENCE
    assert result.evidence_available is True
    assert result.approval_available is False


def test_disconnected_provider_never_hides_an_already_finished_pack():
    result = derive_product_state(
        inputs(
            run_state="FAILED",
            provider_state="DISCONNECTED_LIVE_PROVIDER",
            termination_reason="PROVIDER_DISCONNECTED",
            approval_state="DRAFT_READY",
            approval_reason="CONSUMED",
            pack_id="pack-1",
            action_available=False,
            action_reason="CONSUMED",
        )
    )
    assert result.state is ProductState.DISCONNECTED_LIVE_PROVIDER
    assert result.draft_pack_available is True
    assert result.pack_id == "pack-1"
    assert result.evidence_available is True


def test_unknown_eligibility_with_partially_admitted_evidence_keeps_the_sheet_available():
    result = derive_product_state(
        inputs(
            eligibility_states=(None,),
            recommendation="WATCH",
            evidence_count=1,
            coverage_states=("EVALUATED", "UNKNOWN"),
            action_available=False,
            action_reason="DECISION_NOT_ACTIONABLE",
        )
    )
    assert result.state is ProductState.UNKNOWN_ELIGIBILITY
    assert result.evidence_available is True
    assert result.coverage_complete is False
    assert result.approval_available is False


def test_pending_approval_leaves_the_deterministic_recommendation_unchanged():
    given = inputs(approval_state="PENDING_APPROVAL", approval_reason="PENDING")
    result = derive_product_state(given)
    assert given.recommendation == "APPLY"
    assert result.recommendation_override is None
    assert result.state is ProductState.PENDING_APPROVAL


def test_revoked_approval_retains_historical_proof():
    result = derive_product_state(
        inputs(
            approval_state="REVOKED_APPROVAL",
            approval_reason="VERSION_MISMATCH",
            evidence_count=2,
            action_available=False,
            action_reason="VERSION_MISMATCH",
        )
    )
    assert result.state is ProductState.REVOKED_APPROVAL
    assert result.evidence_available is True


def test_budget_stop_outranks_a_pending_approval():
    result = derive_product_state(
        inputs(
            run_state="BUDGET_STOPPED",
            termination_reason="BUDGET_EXHAUSTED",
            approval_state="PENDING_APPROVAL",
            approval_reason="PENDING",
            action_available=False,
            action_reason="DECISION_NOT_ACTIONABLE",
        )
    )
    assert result.state is ProductState.BUDGET_STOPPED
    assert result.approval_available is False


def test_missing_profile_outranks_every_other_degraded_condition():
    result = derive_product_state(
        inputs(
            profile_present=False,
            freshness="STALE",
            run_state="BUDGET_STOPPED",
            provider_state=None,
            approval_state="REVOKED_APPROVAL",
            approval_reason="CHANGE_REVOKED",
            recommendation=None,
            eligibility_states=(None,),
        )
    )
    assert result.state is ProductState.EMPTY_PROFILE


def test_evidence_sheet_stays_unavailable_when_no_evidence_was_ever_admitted():
    result = derive_product_state(inputs(evidence_count=0, freshness="STALE"))
    assert result.evidence_available is False


def test_precedence_is_a_declared_ordered_policy_covering_every_state():
    assert set(PRECEDENCE) == set(ProductState)
    assert len(PRECEDENCE) == len(ProductState)
    assert PRECEDENCE[0] is ProductState.EMPTY_PROFILE
    assert PRECEDENCE[-1] is ProductState.FINISHED_PACK


@pytest.mark.parametrize("state", list(ProductState))
def test_every_product_state_projects_exactly_one_primary_action(state):
    from qualor.workspace.product_state import PRIMARY_ACTIONS

    assert isinstance(PRIMARY_ACTIONS[state], ProductAction)


@pytest.mark.parametrize(
    ("available", "reason", "expected"),
    [
        (True, "VALID", True),
        (False, "VALID", False),
        (True, "DECISION_NOT_ACTIONABLE", False),
        (True, "EVIDENCE_NOT_ACTIONABLE", False),
        (True, "EXPIRED", False),
    ],
)
def test_approval_availability_tracks_the_server_capability_exactly(available, reason, expected):
    """Product state never widens or narrows the approval answer the server already gave."""
    result = derive_product_state(inputs(action_available=available, action_reason=reason))
    assert result.approval_available is expected


# --- eligibility across a scope of more than one opportunity ---------------------------
#
# The inbox lists many opportunities and has to answer the eligibility question for all of
# them at once. Passing no eligibility at all made `None not in {PASS, FAIL}` hold on every
# request, so the list route asserted UNKNOWN_ELIGIBILITY permanently — including over rows
# whose own persisted decision had already passed. The scope now carries every recorded
# state, and stays unresolved if any one of them is.


def test_every_recorded_eligibility_resolved_leaves_the_scope_healthy():
    result = derive_product_state(inputs(eligibility_states=("PASS", "FAIL", "PASS")))
    assert result.state is None


def test_one_unresolved_eligibility_governs_the_whole_scope():
    """Conservative by construction: a resolved majority never speaks for an unresolved row."""
    result = derive_product_state(inputs(eligibility_states=("PASS", "REVIEW_REQUIRED", "PASS")))
    assert result.state is ProductState.UNKNOWN_ELIGIBILITY
    assert result.primary_action is ProductAction.RESOLVE_UNKNOWNS


@pytest.mark.parametrize("states", [(), (None,), ("UNKNOWN",), ("PASS", None)])
def test_an_absent_or_unresolved_eligibility_is_never_read_as_resolved(states):
    """UNKNOWN is not PASS, and an empty scope has answered nothing."""
    assert derive_product_state(inputs(eligibility_states=states)).state is (
        ProductState.UNKNOWN_ELIGIBILITY
    )
