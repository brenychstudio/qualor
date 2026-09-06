"""Bounded public run contracts; profile assumptions and model observations stay distinct."""

from typing import Annotated, Literal

from pydantic import Field

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.decisions.model import DecisionOutput
from qualor.domain.base import Contract, NonEmpty, UtcInstant
from qualor.domain.enums import SourceType
from qualor.domain.profiles import FounderProfile

from .claims import ValidatedClaim
from .diagnostics import BoundaryEvent


class StudioInput(Contract):
    schema_version: Literal["1"]
    sanitized: Literal[True]
    goal: str = Field(min_length=1, max_length=300)
    allowed_hosts: Annotated[tuple[NonEmpty, ...], Field(min_length=1, max_length=10)]
    founder: FounderProfile
    projects: Annotated[tuple[ProjectDecisionInput, ...], Field(min_length=1, max_length=5)]


class TraceEvent(Contract):
    event: Literal[
        "SEARCH_REQUESTED",
        "SEARCH_RESULTS_RECEIVED",
        "CANDIDATE_SELECTED",
        "SOURCE_SELECTED",
        "SOURCE_FETCHED",
        "SOURCE_REFERENCE_CREATED",
        "EVIDENCE_SPANS_CREATED",
        "STRUCTURED_EXTRACTION",
        "SOURCE_SPAN_SELECTED",
        "CLAIM_EXTRACTED",
        "CLAIM_NORMALIZATION_RESULT",
        "EVIDENCE_RECORDED",
        "ELIGIBILITY_EVALUATED",
        "DECISION_EVALUATED",
        "HUMAN_REVIEW_NEEDED",
        "RUN_TERMINATED",
    ]
    reason_code: NonEmpty
    source_ids: tuple[NonEmpty, ...] = ()
    span_ids: tuple[NonEmpty, ...] = ()
    count: int = Field(default=0, ge=0)
    normalized_field: str | None = Field(default=None, max_length=80)
    normalization_status: Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS", "UNKNOWN"] | None = None
    normalizer_version: str | None = Field(default=None, max_length=20)


class SourceCitation(Contract):
    id: NonEmpty
    final_url: NonEmpty
    retrieved_at: UtcInstant
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority: SourceType
    truncated: bool


class AgentRunResult(Contract):
    mode: Literal["LIVE", "FIXTURE", "REPLAY"]
    decision: DecisionOutput
    claims: Annotated[tuple[ValidatedClaim, ...], Field(max_length=40)]
    trace: Annotated[tuple[TraceEvent, ...], Field(max_length=100)]
    termination_reason: Literal[
        "SUFFICIENT_CRITICAL_EVIDENCE",
        "HARD_FAIL_CONFIRMED",
        "BUDGET_EXHAUSTED",
        "NO_PROGRESS",
        "TOOL_FAILURE_BOUND_REACHED",
        "MAX_STEPS",
    ]
    agent_steps: int
    search_calls: int
    fetched_documents: int
    official_source_count: int
    citation_urls: tuple[NonEmpty, ...]
    contradictions: tuple[NonEmpty, ...]
    sources: Annotated[tuple[SourceCitation, ...], Field(max_length=10)] = ()
    boundary_events: Annotated[tuple[BoundaryEvent, ...], Field(max_length=160)] = ()
