"""Deterministic product state: what the workspace may honestly show and offer right now.

This module is pure policy. It reads facts the workspace already recorded and answers two
questions: which degraded condition currently governs the view, and which actions the server
permits. It never recomputes a deterministic decision, so a product state can describe a
situation without ever rewriting the recommendation, eligibility or approval authority that
produced it.

It deliberately imports no read model, repository or database. Callers pass bounded primitives.
"""

from dataclasses import dataclass, field
from enum import StrEnum

# Coverage entries the deterministic gate could not close.
INCOMPLETE_COVERAGE = frozenset({"UNKNOWN", "MISSING"})
# Run states whose work is known to be incomplete by construction.
INCOMPLETE_RUNS = frozenset({"PARTIAL", "FAILED", "CANCELLED"})
# The only eligibility gate results that resolve the question.
RESOLVED_ELIGIBILITY = frozenset({"PASS", "FAIL"})


class ProductState(StrEnum):
    """The degraded or terminal conditions the product must state out loud.

    A healthy workspace has no product state at all; `derive_product_state` returns `None`
    so the default view never accumulates permanent warning surfaces.
    """

    EMPTY_PROFILE = "EMPTY_PROFILE"
    NO_RESULTS = "NO_RESULTS"
    DISCONNECTED_LIVE_PROVIDER = "DISCONNECTED_LIVE_PROVIDER"
    BUDGET_STOPPED = "BUDGET_STOPPED"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    PARTIAL_SOURCE_FAILURE = "PARTIAL_SOURCE_FAILURE"
    UNKNOWN_ELIGIBILITY = "UNKNOWN_ELIGIBILITY"
    REVOKED_APPROVAL = "REVOKED_APPROVAL"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    FINISHED_PACK = "FINISHED_PACK"


class ProductAction(StrEnum):
    """The single presentation action a product state offers.

    An action names what the person should do next. It is not permission to execute: whether
    an action can actually run is answered separately by the server's own action capability.
    """

    CREATE_PROFILE = "CREATE_PROFILE"
    ADJUST_SEARCH = "ADJUST_SEARCH"
    REVIEW_AVAILABLE_EVIDENCE = "REVIEW_AVAILABLE_EVIDENCE"
    RESOLVE_UNKNOWNS = "RESOLVE_UNKNOWNS"
    REFRESH_EVIDENCE = "REFRESH_EVIDENCE"
    RECONNECT_PROVIDER = "RECONNECT_PROVIDER"
    REVIEW_APPROVAL = "REVIEW_APPROVAL"
    REVIEW_CHANGES = "REVIEW_CHANGES"
    OPEN_APPLICATION_PACK = "OPEN_APPLICATION_PACK"


# Ordered safety policy: the first condition that holds governs the view.
#
# The ordering is "the safer actionability rule wins", read as most-restrictive first:
#
#  1. EMPTY_PROFILE              nothing can be evaluated without a founder and a project.
#  2. NO_RESULTS                 there is no opportunity to say anything about.
#  3. DISCONNECTED_LIVE_PROVIDER a live provider never connected, so the snapshot on screen
#                                may be arbitrarily old and nothing about it is current.
#  4. BUDGET_STOPPED             the run halted at a limit, so its work is incomplete by
#                                construction rather than by a source-level failure.
#  5. STALE_EVIDENCE             evidence exists but freshness policy requires renewal. This
#                                outranks the approval states below because refreshing the
#                                evidence is the cause to act on, not the approval it revoked.
#  6. PARTIAL_SOURCE_FAILURE     the run completed only in part; coverage may be incomplete.
#  7. UNKNOWN_ELIGIBILITY        the deterministic gate did not resolve.
#  8. REVOKED_APPROVAL           a prior approval no longer matches current records.
#  9. PENDING_APPROVAL           an approval is waiting for its human checkpoint.
# 10. FINISHED_PACK              terminal success; it governs only when nothing is degraded.
#
# FINISHED_PACK sitting last never hides a finished pack: pack availability is an independent
# answer, so a disconnected provider still keeps its immutable pack open for reading.
PRECEDENCE: tuple[ProductState, ...] = (
    ProductState.EMPTY_PROFILE,
    ProductState.NO_RESULTS,
    ProductState.DISCONNECTED_LIVE_PROVIDER,
    ProductState.BUDGET_STOPPED,
    ProductState.STALE_EVIDENCE,
    ProductState.PARTIAL_SOURCE_FAILURE,
    ProductState.UNKNOWN_ELIGIBILITY,
    ProductState.REVOKED_APPROVAL,
    ProductState.PENDING_APPROVAL,
    ProductState.FINISHED_PACK,
)

PRIMARY_ACTIONS: dict[ProductState, ProductAction] = {
    ProductState.EMPTY_PROFILE: ProductAction.CREATE_PROFILE,
    ProductState.NO_RESULTS: ProductAction.ADJUST_SEARCH,
    ProductState.DISCONNECTED_LIVE_PROVIDER: ProductAction.RECONNECT_PROVIDER,
    ProductState.BUDGET_STOPPED: ProductAction.REVIEW_AVAILABLE_EVIDENCE,
    ProductState.STALE_EVIDENCE: ProductAction.REFRESH_EVIDENCE,
    ProductState.PARTIAL_SOURCE_FAILURE: ProductAction.REVIEW_AVAILABLE_EVIDENCE,
    ProductState.UNKNOWN_ELIGIBILITY: ProductAction.RESOLVE_UNKNOWNS,
    ProductState.REVOKED_APPROVAL: ProductAction.REVIEW_CHANGES,
    ProductState.PENDING_APPROVAL: ProductAction.REVIEW_APPROVAL,
    ProductState.FINISHED_PACK: ProductAction.OPEN_APPLICATION_PACK,
}


# Which recorded approval governs the view when an opportunity has several.
# The most consequential outcome wins, so a finished pack is never masked by an older
# pending request and a revocation is never masked by a superseded approval.
GOVERNING_APPROVAL_ORDER: tuple[str, ...] = (
    "DRAFT_READY",
    "REVOKED_APPROVAL",
    "PENDING_APPROVAL",
    "APPROVED_FOR_PREPARATION",
    "NOT_REVIEWED",
)


def select_governing_approval(approvals):
    """Pick one approval deterministically from `(state, reason, pack_id)` entries."""
    for wanted in GOVERNING_APPROVAL_ORDER:
        for entry in approvals:
            if entry[0] == wanted:
                return entry
    return None


@dataclass(frozen=True)
class ProductStateInputs:
    """Facts the workspace already recorded. Nothing here is inferred from presentation."""

    profile_present: bool
    result_count: int
    run_state: str | None
    provider_state: str | None
    termination_reason: str | None
    freshness: str
    coverage_states: tuple[str, ...]
    evidence_count: int
    #: Every eligibility state recorded in the scope being described. A selected opportunity
    #: contributes one; a list contributes one per row. An empty scope has answered nothing.
    eligibility_states: tuple[str | None, ...]
    recommendation: str | None
    approval_state: str | None
    approval_reason: str | None
    pack_id: str | None
    action_available: bool
    action_reason: str


@dataclass(frozen=True)
class ProductStateResult:
    """One governing state plus the availabilities each workspace region must respect."""

    state: ProductState | None
    primary_action: ProductAction | None
    reason: str | None
    evidence_available: bool
    approval_available: bool
    draft_pack_available: bool
    coverage_complete: bool
    recommendation_visible: bool
    pack_id: str | None = None
    # Always None. Product state describes a situation; it never restates a decision.
    recommendation_override: None = field(default=None, init=False)


def _conditions(given: ProductStateInputs) -> dict[ProductState, bool]:
    """Which conditions currently hold. Several may hold at once; precedence picks one."""
    return {
        ProductState.EMPTY_PROFILE: not given.profile_present,
        ProductState.NO_RESULTS: given.result_count == 0,
        ProductState.DISCONNECTED_LIVE_PROVIDER: given.provider_state
        == "DISCONNECTED_LIVE_PROVIDER",
        ProductState.BUDGET_STOPPED: given.run_state == "BUDGET_STOPPED",
        ProductState.STALE_EVIDENCE: given.freshness == "STALE",
        ProductState.PARTIAL_SOURCE_FAILURE: given.run_state in INCOMPLETE_RUNS,
        # Unresolved if any recorded state is, or if nothing was recorded at all. A
        # resolved majority never speaks for a row that is still open.
        ProductState.UNKNOWN_ELIGIBILITY: not given.eligibility_states
        or any(state not in RESOLVED_ELIGIBILITY for state in given.eligibility_states),
        ProductState.REVOKED_APPROVAL: given.approval_state == "REVOKED_APPROVAL",
        ProductState.PENDING_APPROVAL: given.approval_state == "PENDING_APPROVAL",
        ProductState.FINISHED_PACK: given.pack_id is not None,
    }


def _reason(state: ProductState | None, given: ProductStateInputs) -> str | None:
    """The bounded persisted code that explains this state, never invented prose."""
    if state in {ProductState.REVOKED_APPROVAL, ProductState.PENDING_APPROVAL}:
        return given.approval_reason
    if state in {
        ProductState.BUDGET_STOPPED,
        ProductState.PARTIAL_SOURCE_FAILURE,
        ProductState.DISCONNECTED_LIVE_PROVIDER,
    }:
        return given.termination_reason
    return None


def derive_product_state(given: ProductStateInputs) -> ProductStateResult:
    """Pick the governing state by declared precedence and project allowed actions."""
    holding = _conditions(given)
    state = next((candidate for candidate in PRECEDENCE if holding[candidate]), None)

    evaluated = given.profile_present and given.result_count > 0
    return ProductStateResult(
        state=state,
        primary_action=PRIMARY_ACTIONS[state] if state else None,
        reason=_reason(state, given),
        # Proof stays readable whenever the workspace admitted any evidence, including
        # evidence that is now stale, partial or behind a disconnected provider.
        evidence_available=evaluated and given.evidence_count > 0,
        # Approval permission is the server's existing action capability, never re-derived.
        approval_available=evaluated and given.action_available and given.action_reason == "VALID",
        # An immutable pack that already exists stays readable in every degraded state.
        draft_pack_available=given.pack_id is not None,
        coverage_complete=not any(
            entry in INCOMPLETE_COVERAGE for entry in given.coverage_states
        ),
        # A recommendation is shown whenever the deterministic engine produced one.
        recommendation_visible=evaluated and given.recommendation is not None,
        pack_id=given.pack_id,
    )
