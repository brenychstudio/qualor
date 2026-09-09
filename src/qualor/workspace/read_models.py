"""Public product contracts; persistence receipts and provider payloads stay private."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from qualor.conflicts.model import ConflictCategory, ConflictStatus
from qualor.decisions.model import PolicyVersions, Recommendation
from qualor.domain import FounderProfile, ProjectProfile, Reward
from qualor.domain.base import CalendarDate, Contract, NonEmpty, PositiveInt, UtcInstant
from qualor.domain.enums import Category, ExtractionState, FreshnessStatus, GateState, SourceType
from qualor.domain.money import NonNegativeDecimal
from qualor.domain.rules import CoverageEntry
from qualor.effort import EffortEstimate
from qualor.matching import ReadinessAssessment
from qualor.matching.model import FactorResult, MatchStatus, Score
from qualor.runtime import RuntimeMode
from qualor.strategy import StrategyContribution

from .models import (
    ApprovalAction,
    ApprovalReason,
    ApprovalState,
    DraftEvidenceVersion,
    DraftJobState,
    DraftPackSection,
    Hash,
    NonNegativeInt,
    RunState,
    ShortText,
)


class ProductError(Contract):
    code: (
        ApprovalReason
        | Literal[
            "ACTION_FORBIDDEN",
            "INVALID_REQUEST",
            "INTERNAL_ERROR",
            "PROJECT_LIMIT",
            "SNAPSHOT_UNAVAILABLE",
            "AMBIGUOUS_SOURCE_RUN",
            "SOURCE_RUN_NOT_COMPLETED",
            "SOURCE_RUN_MISMATCH",
            "AMBIGUOUS_EVIDENCE_REFERENCE",
            "EVIDENCE_REFERENCE_UNAVAILABLE",
            "EVIDENCE_NOT_ACTIONABLE",
            "DRAFT_INPUT_LIMIT",
            "CONSUMPTION_WITHOUT_JOB_INTENT",
            "DRAFT_STATE_INCONSISTENT",
            "BUDGET_STOPPED",
            "REVIEW_REQUIRED",
            "STALE",
            "READ_LIMIT_EXCEEDED",
        ]
    )


class PortfolioView(Contract):
    founder: FounderProfile | None
    projects: Annotated[tuple[ProjectProfile, ...], Field(max_length=5)]


class PageInfo(Contract):
    offset: NonNegativeInt
    limit: Annotated[PositiveInt, Field(le=100)]
    total: NonNegativeInt
    has_more: StrictBool


class ProfileUpdateRequest(Contract):
    expected_version: NonNegativeInt
    profile: FounderProfile


class ProjectUpdateRequest(Contract):
    expected_version: NonNegativeInt
    project: ProjectProfile


class ApprovalRequest(Contract):
    opportunity_version: PositiveInt
    opportunity_hash: Hash
    founder_profile_id: NonEmpty
    founder_profile_version: PositiveInt
    project_id: NonEmpty
    project_version: PositiveInt
    decision_id: NonEmpty
    decision_version: PositiveInt
    policy_versions: PolicyVersions
    action: ApprovalAction = ApprovalAction.GENERATE_DRAFT_PACK


class ApprovalConfirmRequest(Contract):
    expected_versions: ApprovalRequest
    idempotency_key: ShortText


class ActionCapability(Contract):
    available: StrictBool
    reason: ApprovalReason
    approval_request: ApprovalRequest | None = None


class StrategyView(Contract):
    state: Literal["AVAILABLE", "NOT_ENOUGH_EVIDENCE"]
    score: Score | None
    semantics: Literal["PRIORITIZATION_NOT_WIN_PROBABILITY"] = "PRIORITIZATION_NOT_WIN_PROBABILITY"
    breakdown: Annotated[tuple[StrategyContribution, ...], Field(max_length=5)] = ()
    missing_factors: Annotated[tuple[NonEmpty, ...], Field(max_length=100)] = ()

    @model_validator(mode="after")
    def score_availability(self):
        if (self.state == "AVAILABLE") != (self.score is not None):
            raise ValueError("Strategy availability must match the persisted score")
        return self


class ProjectSummary(Contract):
    id: NonEmpty
    version: PositiveInt
    name: NonEmpty


class DeadlineView(Contract):
    values: Annotated[tuple[CalendarDate | UtcInstant, ...], Field(max_length=100)]
    timezone_status: Literal["UTC", "CALENDAR_DATE_ONLY", "UNKNOWN"]


class DecisionCanvasView(Contract):
    decision_id: NonEmpty | None
    decision_version: PositiveInt | None
    recommendation: Recommendation | None
    summary: NonEmpty | None
    reason_codes: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    strategy: StrategyView
    best_project: ProjectSummary | None
    eligibility: GateState | None
    effort: EffortEstimate | None
    deadline: DeadlineView
    readiness: ReadinessAssessment | None
    freshness: FreshnessStatus
    primary_blocker: NonEmpty | None
    missing_information: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    primary_action: ActionCapability


class InboxItem(Contract):
    opportunity_id: NonEmpty
    priority_rank: Annotated[
        NonNegativeInt,
        Field(
            description="Absolute server priority position; lower is higher. Not for display."
        ),
    ]
    discovered_at: Annotated[
        UtcInstant,
        Field(description="Earliest persisted created_at for this stable opportunity identity."),
    ]
    version: PositiveInt
    program_name: NonEmpty
    organizer: NonEmpty
    edition: NonEmpty
    recommendation: Recommendation | None
    run_state: RunState | None
    mode: RuntimeMode | None
    best_project: ProjectSummary | None
    deadline: DeadlineView
    effort: EffortEstimate | None
    readiness: ReadinessAssessment | None
    primary_blocker: NonEmpty | None
    freshness: FreshnessStatus
    human_action_available: StrictBool


class InboxResponse(Contract):
    items: Annotated[tuple[InboxItem, ...], Field(max_length=100)]
    profile_present: StrictBool
    page: PageInfo


class DraftJobView(Contract):
    id: NonEmpty
    version: PositiveInt
    mode: RuntimeMode
    state: DraftJobState
    started_at: UtcInstant | None
    completed_at: UtcInstant | None
    failure_reason: ShortText | None


class ApprovalView(Contract):
    id: NonEmpty
    version: PositiveInt
    actor_id: NonEmpty
    opportunity_id: NonEmpty
    action: ApprovalAction
    state: ApprovalState
    expires_at: UtcInstant
    actionable: StrictBool
    reason: ApprovalReason
    approved_snapshot: ApprovalRequest
    draft_job: DraftJobView | None = None
    pack_id: NonEmpty | None = None


class OpportunityWorkspaceResponse(Contract):
    opportunity_id: NonEmpty
    version: PositiveInt
    program_name: NonEmpty
    organizer: NonEmpty
    edition: NonEmpty
    decision: DecisionCanvasView
    freshness: FreshnessStatus
    last_refresh_failed_at: UtcInstant | None
    rewards: Annotated[tuple[Reward, ...], Field(max_length=100)]
    coverage: Annotated[tuple[CoverageEntry, ...], Field(max_length=100)]
    run_ids: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    approvals: Annotated[tuple[ApprovalView, ...], Field(max_length=100)]
    runs_page: PageInfo
    approvals_page: PageInfo


class TechnicalProvenanceView(Contract):
    source_id: NonEmpty | None
    extraction_state: ExtractionState
    policy_version: PositiveInt | None


class EvidenceProofView(Contract):
    evidence_id: NonEmpty
    evidence_version: PositiveInt
    category: Category
    excerpt: NonEmpty
    url: NonEmpty
    original_url: NonEmpty
    domain: NonEmpty
    source_type: SourceType
    source_id: NonEmpty | None
    source_version: NonEmpty
    retrieved_at: UtcInstant
    freshness: FreshnessStatus
    technical_provenance: TechnicalProvenanceView | None = None


class EvidenceClaimView(Contract):
    rule_id: NonEmpty
    state: Literal["PASS", "FAIL", "UNKNOWN", "CONFLICT", "STALE", "NOT_APPLICABLE"]
    reason_codes: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    evidence_refs: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]


class EligibilityWhyView(Contract):
    state: GateState | None
    evaluated_at: UtcInstant | None
    policy_version: PositiveInt | None


class ProjectFitWhyView(Contract):
    project: ProjectSummary | None
    match_status: MatchStatus | None
    factor_results: Annotated[tuple[FactorResult, ...], Field(max_length=7)]
    matched_requirement_refs: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    missing_facts: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    blocking_gaps: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    evaluated_at: UtcInstant | None
    policy_version: PositiveInt | None


class ConstraintsConflictWhyView(Contract):
    status: ConflictStatus | None
    checked_rule_categories: Annotated[
        tuple[tuple[NonEmpty, ConflictCategory], ...], Field(max_length=100)
    ]
    missing_rule_categories: Annotated[
        tuple[tuple[NonEmpty, ConflictCategory], ...], Field(max_length=100)
    ]
    evidence_refs: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    reasons: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    founder_constraints: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    evaluated_at: UtcInstant | None
    policy_version: PositiveInt | None


class RewardDeadlineWhyView(Contract):
    rewards: Annotated[tuple[Reward, ...], Field(max_length=100)]
    deadline: DeadlineView
    evidence_refs: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    evidence_refs_scope: Literal["CURRENT_PROOF_PAGE"] = "CURRENT_PROOF_PAGE"


class EvidenceSheetView(Contract):
    opportunity_id: NonEmpty
    opportunity_version: PositiveInt
    freshness: FreshnessStatus
    claims: Annotated[tuple[EvidenceClaimView, ...], Field(max_length=100)]
    proofs: Annotated[tuple[EvidenceProofView, ...], Field(max_length=100)]
    claims_page: PageInfo
    proofs_page: PageInfo
    coverage: Annotated[tuple[CoverageEntry, ...], Field(max_length=100)]
    eligibility: EligibilityWhyView
    project_fit: ProjectFitWhyView
    constraints_conflicts: ConstraintsConflictWhyView
    reward_deadline: RewardDeadlineWhyView


class RunView(Contract):
    id: NonEmpty
    mode: RuntimeMode
    state: RunState
    provider_state: Literal["DISCONNECTED_LIVE_PROVIDER"] | None
    opportunity_id: NonEmpty | None
    opportunity_version: PositiveInt | None
    started_at: UtcInstant | None
    completed_at: UtcInstant | None
    search_calls: NonNegativeInt
    fetched_documents: NonNegativeInt
    official_source_count: NonNegativeInt
    verified_claim_count: NonNegativeInt
    reserved_cost_usd: NonNegativeDecimal
    reported_cost_usd: NonNegativeDecimal
    termination_reason: ShortText | None


class RunEventView(Contract):
    run_id: NonEmpty
    sequence: PositiveInt
    event_type: ShortText
    mode: RuntimeMode
    occurred_at: UtcInstant
    reason_code: ShortText | None
    phase: Literal["DISCOVERING", "VERIFYING", "EVALUATING", "DECISION_UPDATED"] | None
    count: NonNegativeInt
    source_ids: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    evidence_ids: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    estimated_cost_usd: NonNegativeDecimal | None
    reported_cost_usd: NonNegativeDecimal | None


class ActivityResponse(Contract):
    runs: Annotated[tuple[RunView, ...], Field(max_length=100)]
    events: Annotated[tuple[RunEventView, ...], Field(max_length=100)]
    runs_page: PageInfo
    events_page: PageInfo


class DraftPackView(Contract):
    id: NonEmpty
    version: PositiveInt
    approval_id: NonEmpty
    approval_version: PositiveInt
    actor_id: NonEmpty
    mode: RuntimeMode
    draft_job_id: NonEmpty
    draft_job_version: PositiveInt
    opportunity_id: NonEmpty
    approved_snapshot: ApprovalRequest
    evidence_refs: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    evidence_versions: Annotated[tuple[DraftEvidenceVersion, ...], Field(max_length=100)]
    source_refs: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    missing_fields: Annotated[tuple[NonEmpty, ...], Field(max_length=100)]
    sections: Annotated[tuple[DraftPackSection, ...], Field(max_length=7)]
    generated_at: UtcInstant
    creator_kind: Literal["DETERMINISTIC"] | None
    content_kind: Literal["DRAFT_FOR_HUMAN_REVIEW"] = "DRAFT_FOR_HUMAN_REVIEW"


class SessionView(Contract):
    read_only: StrictBool
    action_token: NonEmpty | None


PUBLIC_CONTRACTS = (
    PortfolioView,
    ProfileUpdateRequest,
    ProjectUpdateRequest,
    InboxResponse,
    InboxItem,
    OpportunityWorkspaceResponse,
    DecisionCanvasView,
    EvidenceSheetView,
    ActivityResponse,
    ApprovalRequest,
    ApprovalView,
    DraftPackView,
    ApprovalConfirmRequest,
    SessionView,
    ProductError,
)
