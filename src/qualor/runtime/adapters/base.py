"""Bounded source compiler primitives; no applicant facts or verdicts."""

import hashlib
import json
import re
from datetime import datetime
from typing import Annotated, Protocol, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from qualor.domain.base import Contract
from qualor.domain.enums import Category, Criticality, ExtractionState, Operator, Provenance
from qualor.domain.evidence import EvidenceRecord
from qualor.domain.rules import RuleCandidate
from qualor.runtime.normalization import NormalizationStatus, NormalizedValue, normalize_text
from qualor.runtime.section_extraction import GroundedSectionCandidate

SafeReason = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,79}$")]


class AdapterResult(Contract):
    category: Category
    normalization_status: NormalizationStatus
    normalized_value: NormalizedValue
    rules: Annotated[tuple[RuleCandidate, ...], Field(max_length=100)]
    evidence: Annotated[tuple[EvidenceRecord, ...], Field(max_length=40)]
    conditional: StrictBool
    reason_codes: Annotated[tuple[SafeReason, ...], Field(min_length=1, max_length=40)]

    @model_validator(mode="after")
    def bound_tree(self) -> Self:
        pending = list(self.rules)
        count = 0
        while pending:
            rule = pending.pop()
            count += 1
            if count > 100:
                raise ValueError("ADAPTER_RULE_LIMIT")
            pending.extend(rule.children)
        return self


class SemanticAdapter(Protocol):
    def compile(
        self, candidate: GroundedSectionCandidate, *, evaluated_at: datetime
    ) -> AdapterResult: ...


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:32]


def body(candidate: GroundedSectionCandidate) -> str:
    """Parsing view only. Evidence always uses the original individual excerpts."""
    text = " ".join(candidate.quotes).strip()
    # Remove a standalone section heading, never any part of its clause.
    if len(candidate.quotes) == 1 and "\n" in text:
        heading, remainder = text.split("\n", 1)
        if re.fullmatch(
            r"(?:\d+(?:\.\d+)*[.)]?\s+)?(?:Requirements|Eligibility|Deadline|"
            r"Entrant types?|Geography|Legal entity|Project policy|License|"
            r"Technology requirements|Financial support|Reward conditions)",
            heading,
            re.I,
        ):
            text = remainder
    return " ".join(text.split()).rstrip(".")


def fullmatch(pattern: str, text: str):
    return re.fullmatch(pattern, text, flags=re.IGNORECASE)


def literal_values(text: str, proposed: NormalizedValue) -> tuple[tuple[str, ...], str] | None:
    """Accept a complete literal or explicit list; preserve multiword proper names."""
    values = proposed if isinstance(proposed, tuple) else (proposed,)
    if not values or any(not isinstance(value, str) or not value.strip() for value in values):
        return None
    if len(values) > 40:
        raise ValueError("ADAPTER_VALUE_LIMIT")
    if any(value not in text for value in values):
        return None  # Evaluator text membership is case-sensitive; never alter a literal.
    normalized = tuple(normalize_text(value) for value in values)
    text = normalize_text(text)
    if len(values) == 1 and text == '"' + normalized[0] + '"':
        return values, "single"
    if len(values) == 1 and text == normalized[0]:
        if re.search(r"\b(?:and|or)\b", text):
            return None  # Ambiguous unquoted list versus proper name.
        return values, "single"
    for relation in ("or", "and"):
        forms = {f" {relation} ".join(normalized)}
        if len(values) > 1:
            forms.add(", ".join(normalized[:-1]) + f", {relation} " + normalized[-1])
            forms.add(", ".join(normalized[:-1]) + f" {relation} " + normalized[-1])
        if text in forms:
            return values, relation
    return None


def split_condition(text: str) -> tuple[str, str]:
    """Separate an explicit residual only; never split arbitrary proper values."""
    match = re.search(
        r",? (?:only if|if|unless|except|provided that|subject to|"
        r"and (?:publish|obtain|disclose))\b",
        text,
        re.I,
    )
    return (text[: match.start()], text[match.start() :]) if match else (text, "")


class Compiler:
    """One compilation transaction with evidence shared by every governing rule."""

    def __init__(self, candidate: GroundedSectionCandidate, evaluated_at: datetime):
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("ADAPTER_CLOCK_REQUIRES_TIMEZONE")
        self.candidate = candidate
        self.clock = evaluated_at
        self.category = candidate.candidate.category
        self.reasons = []
        self.records = []
        self.rule_count = 0
        source = candidate.source
        self.identity = (
            source.id,
            source.content_hash,
            candidate.context.section_id,
            self.category,
            # Grounding capabilities bind exact source offsets. Equal excerpts at
            # different positions must not collapse into one support association.
            candidate.candidate.span_ids,
            candidate.candidate.qualifier_span_ids,
            candidate.candidate.exception_span_ids,
            candidate.context.span_ids,
        )
        excerpts = list(candidate.quotes)
        for excerpt in (*candidate.context.qualifiers, *candidate.context.exceptions):
            if excerpt not in excerpts:
                excerpts.append(excerpt)
        if len(excerpts) > 40:
            raise ValueError("ADAPTER_EVIDENCE_LIMIT")
        for index, excerpt in enumerate(excerpts):
            if excerpt != excerpt.strip():
                raise ValueError("ADAPTER_EVIDENCE_WHITESPACE_UNREPRESENTED")
            if not excerpt.strip() or len(excerpt) > 700 or excerpt not in source.text:
                raise ValueError("ADAPTER_EVIDENCE_INVALID")
            self.records.append(
                EvidenceRecord(
                    **self.record("evidence_" + _digest((self.identity, index, excerpt))),
                    source_id=source.id,
                    original_url=source.original_url,
                    final_url=source.final_url,
                    retrieved_at=source.retrieved_at,
                    source_type=source.authority,
                    content_hash=source.content_hash,
                    supporting_excerpt=excerpt,
                    normalized_field=self.category,
                    extraction_state=ExtractionState.UNVERIFIED,
                    clause_context=candidate.context,
                )
            )

    def record(self, identifier):
        return dict(
            schema_version="1",
            id=identifier,
            version=1,
            created_at=self.clock,
            updated_at=self.clock,
            provenance=Provenance.DOCUMENTED,
        )

    def rule(
        self,
        operator=Operator.AND,
        subject=None,
        operands=(),
        *,
        children=(),
        supported=True,
        reason="SOURCE_EXPRESSION",
        criticality=Criticality.CRITICAL,
    ):
        self.rule_count += 1
        if self.rule_count > 100:
            raise ValueError("ADAPTER_RULE_LIMIT")
        expression = (
            operator,
            subject,
            [v.model_dump(mode="json") for v in operands],
            [child.id for child in children],
            supported,
            reason,
            self.rule_count,
        )
        return RuleCandidate(
            **self.record(
                "rule_" + _digest((self.identity, tuple(r.id for r in self.records), expression))
            ),
            rule_type=self.category,
            operator=operator,
            subject_reference=subject,
            operands=operands,
            children=children,
            criticality=criticality,
            evidence_ids=tuple(record.id for record in self.records),
            supported=supported,
            source_text_summary=reason,
            clause_context=self.candidate.context,
        )

    def unresolved(self, reason="UNREPRESENTED_SOURCE_CONDITION", *, operands=()):
        if reason not in self.reasons:
            self.reasons.append(reason)
        return self.rule(supported=False, operands=operands, reason=reason)

    def combine(self, rules, operator=Operator.AND, *, supported=True):
        rules = tuple(rules)
        if len(rules) == 1 and supported:
            return rules[0]
        return self.rule(operator, children=rules, supported=supported)

    def early(self):
        if self.candidate.candidate.state == "UNKNOWN":
            return self.finish(self.unresolved("MODEL_RETAINED_UNKNOWN"), status="UNKNOWN")
        return None

    def finish(
        self,
        rule=None,
        *,
        value=None,
        status="UNSUPPORTED",
        conditional=False,
        interpreted=False,
        consumed_context=False,
    ):
        rule = rule or self.unresolved()
        context = self.candidate.context
        if not self.candidate.semantic_context_complete:
            rule = self.combine(
                (rule, self.unresolved("CLAUSE_CONTEXT_INCOMPLETE")), supported=False
            )
            status, value, conditional = "UNKNOWN", None, True
        elif not consumed_context and (
            bool(context.exceptions)
            or any(excerpt not in self.candidate.quotes for excerpt in context.qualifiers)
            or re.search(
                r"\b(?:if|unless|except|provided that|subject to)\b",
                body(self.candidate),
                re.I,
            )
        ):
            rule = self.combine(
                (rule, self.unresolved("APPLICABILITY_UNRESOLVED")), supported=False
            )
            status, conditional = "UNKNOWN", True
        records = self.records
        if interpreted:
            # Interpretation of a predicate is distinct from the applicant satisfying it.
            records = [
                r.model_copy(update={"extraction_state": ExtractionState.REVIEWED}) for r in records
            ]
        return AdapterResult(
            category=self.category,
            normalization_status=status,
            normalized_value=value,
            rules=(rule,),
            evidence=tuple(records),
            conditional=conditional,
            reason_codes=tuple(self.reasons or ["SOURCE_EXPRESSION_SUPPORTED"]),
        )
