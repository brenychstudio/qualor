"""Rule candidates are inputs; evaluations and gates are engine outputs."""

from pydantic import StrictBool

from .base import Contract, NonEmpty, PositiveInt, Record, UtcInstant
from .enums import (
    Category,
    CoverageState,
    Criticality,
    GateState,
    Operator,
    ReasonCode,
    RuleStatus,
    SubjectReference,
)
from .values import Scalar


class RuleCandidate(Record):
    rule_type: Category
    operator: Operator
    operands: tuple[Scalar, ...] = ()
    subject_reference: SubjectReference | None = None
    children: tuple["RuleCandidate", ...] = ()
    criticality: Criticality
    evidence_ids: tuple[NonEmpty, ...]
    supported: StrictBool
    source_text_summary: NonEmpty
    not_applicable_reason: NonEmpty | None = None
    contradiction: StrictBool = False


class RuleEvaluation(Record):
    rule_id: NonEmpty
    status: RuleStatus
    reason_code: ReasonCode
    reason_codes: tuple[ReasonCode, ...]
    evidence_ids: tuple[NonEmpty, ...]
    subject_reference: SubjectReference | None
    policy_version: PositiveInt
    evaluated_at: UtcInstant
    children: tuple["RuleEvaluation", ...] = ()


class CoverageEntry(Contract):
    category: Category
    state: CoverageState
    rule_ids: tuple[NonEmpty, ...] = ()
    reasons: tuple[NonEmpty, ...] = ()


class EligibilityGate(Record):
    state: GateState
    evaluations: tuple[RuleEvaluation, ...]
    critical_coverage: tuple[CoverageEntry, ...]
    missing_information: tuple[NonEmpty, ...]
    reason_codes: tuple[ReasonCode, ...]
    policy_version: PositiveInt
    evaluated_at: UtcInstant
