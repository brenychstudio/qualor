"""Immutable records for durable workspace state."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from qualor.decisions.model import PolicyVersions
from qualor.domain.base import Contract, NonEmpty, PositiveInt, Record, UtcInstant
from qualor.domain.money import NonNegativeDecimal
from qualor.runtime import RuntimeMode

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
Hash = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
ShortText = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)
]


class RunState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BUDGET_STOPPED = "BUDGET_STOPPED"


class RunRecord(Record):
    mode: RuntimeMode
    state: RunState
    opportunity_id: NonEmpty | None = None
    opportunity_version: PositiveInt | None = None
    decision_id: NonEmpty | None = None
    decision_version: PositiveInt | None = None
    search_calls: NonNegativeInt = 0
    fetched_documents: NonNegativeInt = 0
    official_source_count: NonNegativeInt = 0
    verified_claim_count: NonNegativeInt = 0
    reserved_cost_usd: NonNegativeDecimal = 0
    reported_cost_usd: NonNegativeDecimal = 0
    provider: ShortText | None = None
    model: ShortText | None = None
    termination_reason: ShortText | None = None
    started_at: UtcInstant | None = None
    completed_at: UtcInstant | None = None


class RunEventPayload(Contract):
    reason_code: ShortText | None = None
    phase: Literal["DISCOVERING", "VERIFYING", "EVALUATING", "DECISION_UPDATED"] | None = None
    status: ShortText | None = None
    source_ids: tuple[NonEmpty, ...] = ()
    evidence_ids: tuple[NonEmpty, ...] = ()
    count: NonNegativeInt = 0
    duration_ms: NonNegativeInt | None = None
    normalized_field: ShortText | None = None
    normalization_status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS", "UNKNOWN"] | None = None
    estimated_cost_usd: NonNegativeDecimal | None = None
    reported_cost_usd: NonNegativeDecimal | None = None
    failure_reason: ShortText | None = None


class RunEvent(Contract):
    run_id: NonEmpty
    sequence: PositiveInt
    event_type: Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=80)
    ]
    payload: RunEventPayload
    mode: RuntimeMode
    occurred_at: UtcInstant

    @field_validator("payload")
    @classmethod
    def payload_is_bounded_and_safe(cls, value: RunEventPayload) -> RunEventPayload:
        try:
            encoded = value.model_dump_json()
        except (TypeError, ValueError) as exc:
            raise ValueError("Run event payload must be JSON-compatible") from exc
        if len(encoded.encode("utf-8")) > 4096:
            raise ValueError("Run event payload exceeds 4096 bytes")
        return value


class ApprovalAction(StrEnum):
    GENERATE_DRAFT_PACK = "GENERATE_DRAFT_PACK"


class ApprovalState(StrEnum):
    NOT_REVIEWED = "NOT_REVIEWED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED_FOR_PREPARATION = "APPROVED_FOR_PREPARATION"
    REVOKED_APPROVAL = "REVOKED_APPROVAL"
    DRAFT_READY = "DRAFT_READY"


class ApprovalReason(StrEnum):
    VALID = "VALID"
    NOT_FOUND = "NOT_FOUND"
    PENDING = "PENDING"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"
    ACTOR_MISMATCH = "ACTOR_MISMATCH"
    ACTION_MISMATCH = "ACTION_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    GRAPH_MISMATCH = "GRAPH_MISMATCH"
    MODE_MISMATCH = "MODE_MISMATCH"
    DEADLINE_UNKNOWN = "DEADLINE_UNKNOWN"
    DEADLINE_PASSED = "DEADLINE_PASSED"
    DEADLINE_MISMATCH = "DEADLINE_MISMATCH"
    DECISION_NOT_ACTIONABLE = "DECISION_NOT_ACTIONABLE"
    EVIDENCE_NOT_ACTIONABLE = "EVIDENCE_NOT_ACTIONABLE"
    EVIDENCE_CHANGED = "EVIDENCE_CHANGED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    CHANGE_REVOKED = "CHANGE_REVOKED"
    TIME_INVALID = "TIME_INVALID"


class ApprovalBindings(Contract):
    actor_id: NonEmpty
    opportunity_id: NonEmpty
    opportunity_hash: Hash
    opportunity_version: PositiveInt
    founder_profile_id: NonEmpty
    founder_profile_version: PositiveInt
    project_id: NonEmpty
    project_version: PositiveInt
    decision_id: NonEmpty
    decision_version: PositiveInt
    policy_versions: PolicyVersions
    action: ApprovalAction


class ApprovalChange(Contract):
    opportunity_id: NonEmpty | None = None
    founder_profile_id: NonEmpty | None = None
    project_id: NonEmpty | None = None
    decision_id: NonEmpty | None = None
    policy_versions: PolicyVersions | None = None

    @model_validator(mode="after")
    def explicit_scope(self) -> "ApprovalChange":
        if not any(getattr(self, field) is not None for field in type(self).model_fields):
            raise ValueError("Approval change requires an explicit scope")
        return self


class ApprovalRecord(Record):
    actor_id: NonEmpty
    opportunity_id: NonEmpty
    opportunity_hash: Hash
    opportunity_version: PositiveInt
    founder_profile_id: NonEmpty
    founder_profile_version: PositiveInt
    project_id: NonEmpty
    project_version: PositiveInt
    decision_id: NonEmpty
    decision_version: PositiveInt
    policy_versions: PolicyVersions
    action: ApprovalAction
    state: ApprovalState
    expires_at: UtcInstant
    # Key belongs to THIS transition receipt; prior version keys remain immutable.
    idempotency_key: NonEmpty | None = None
    mode: RuntimeMode | None = None
    consumed_at: UtcInstant | None = None
    revocation_reason: ShortText | None = None


class DraftJobState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BUDGET_STOPPED = "BUDGET_STOPPED"


class DraftJobRecord(Record):
    approval_id: NonEmpty
    approval_version: PositiveInt = 1
    mode: RuntimeMode
    state: DraftJobState
    idempotency_key: NonEmpty
    started_at: UtcInstant | None = None
    completed_at: UtcInstant | None = None
    failure_reason: ShortText | None = None


class DraftPackSection(Contract):
    key: NonEmpty
    title: NonEmpty
    content: Annotated[str, StringConstraints(strict=True, max_length=20_000)]
    evidence_refs: tuple[NonEmpty, ...] = ()


class DraftStringValue(Contract):
    type: Literal["STRING"]
    value: NonEmpty


class DraftIntegerValue(Contract):
    type: Literal["INTEGER"]
    value: StrictInt


class DraftBooleanValue(Contract):
    type: Literal["BOOLEAN"]
    value: StrictBool


class DraftDecimalValue(Contract):
    type: Literal["DECIMAL"]
    value: NonNegativeDecimal


class DraftStringsValue(Contract):
    type: Literal["STRINGS"]
    value: tuple[NonEmpty, ...]


DraftAuthoringValue = Annotated[
    DraftStringValue
    | DraftIntegerValue
    | DraftBooleanValue
    | DraftDecimalValue
    | DraftStringsValue,
    Field(discriminator="type"),
]


class DraftAuthoringFact(Contract):
    key: NonEmpty
    value: DraftAuthoringValue
    source: Literal["FOUNDER_PROFILE", "PROJECT_PROFILE", "OPPORTUNITY", "EVIDENCE"]
    evidence_refs: tuple[NonEmpty, ...] = ()


class DraftPack(Record):
    approval_id: NonEmpty
    approval_version: PositiveInt = 1
    draft_job_id: NonEmpty
    draft_job_version: PositiveInt = 1
    opportunity_id: NonEmpty
    opportunity_hash: Hash
    opportunity_version: PositiveInt
    founder_profile_id: NonEmpty
    founder_profile_version: PositiveInt
    project_id: NonEmpty
    project_version: PositiveInt
    decision_id: NonEmpty
    decision_version: PositiveInt
    policy_versions: PolicyVersions
    evidence_refs: tuple[NonEmpty, ...]
    source_refs: tuple[NonEmpty, ...]
    missing_fields: tuple[NonEmpty, ...]
    authoring_facts: tuple[DraftAuthoringFact, ...]
    sections: tuple[DraftPackSection, ...]
    generated_at: UtcInstant

    @model_validator(mode="after")
    def unique_sections(self) -> "DraftPack":
        if len({section.key for section in self.sections}) != len(self.sections):
            raise ValueError("Draft pack section keys must be unique")
        return self
