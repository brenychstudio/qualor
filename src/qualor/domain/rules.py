"""Rule candidates are inputs; evaluations and gates are engine outputs."""

from typing import Self

from pydantic import StrictBool, model_validator

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
from .evidence import ClauseContext
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
    clause_context: ClauseContext | None = None

    @model_validator(mode="after")
    def explicit_non_applicability(self) -> Self:
        if self.not_applicable_reason and (
            self.subject_reference or self.operands or self.children
        ):
            raise ValueError("Non-applicability cannot override an executable expression")
        return self


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
