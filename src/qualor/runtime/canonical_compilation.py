"""Merge source adapters into existing rule/evidence authority, never verdicts."""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StrictInt

from qualor.domain.base import Contract, Record, UtcInstant
from qualor.domain.enums import Category
from qualor.domain.evidence import EvidenceRecord
from qualor.domain.rules import RuleCandidate
from qualor.runtime.adapters.base import AdapterResult
from qualor.runtime.normalization import NormalizedValue, normalize_text, parse_absolute_deadline

OpportunityRuleSet = tuple[RuleCandidate, ...]


class CompiledSectionAuthority(Contract):
    rules: Annotated[OpportunityRuleSet, Field(max_length=100)]
    evidence: Annotated[tuple[EvidenceRecord, ...], Field(max_length=40)]
    deadlines: Annotated[tuple[UtcInstant, ...], Field(max_length=40)]
    supported_claim_count: Annotated[StrictInt, Field(ge=0, le=40)]


def merge_records[T: Record](records: tuple[T, ...]) -> tuple[T, ...]:
    """One immutable record per ID; conflicting content cannot select a winner."""
    unique = {}
    for record in records:
        previous = unique.get(record.id)
        if previous is not None and previous != record:
            raise ValueError("CANONICAL_AUTHORITY_ID_CONFLICT")
        unique.setdefault(record.id, record)
    return tuple(unique[key] for key in sorted(unique))


def merge_rules(rules: OpportunityRuleSet) -> OpportunityRuleSet:
    """Keep expression trees intact while checking identities below their roots."""
    roots = merge_records(rules)
    nodes = []
    pending = list(roots)
    while pending:
        rule = pending.pop()
        nodes.append(rule)
        if len(nodes) > 500:
            raise ValueError("CANONICAL_RULE_TREE_LIMIT")
        pending.extend(rule.children)
    merge_records(tuple(nodes))
    # The evaluator requires a tree, not shared child IDs across distinct roots.
    # Do not flatten or rename a shared predicate to manufacture a different tree.
    seen = set()
    pending = list(roots)
    while pending:
        rule = pending.pop()
        if rule.id in seen:
            raise ValueError("CANONICAL_RULE_STRUCTURE_CONFLICT")
        seen.add(rule.id)
        pending.extend(rule.children)
    return roots


def section_owns_evidence(evidence: EvidenceRecord, section: CompiledSectionAuthority) -> bool:
    """Identify a legacy view of the same source clause without discarding evidence."""
    fields = (
        "source_id",
        "original_url",
        "final_url",
        "retrieved_at",
        "source_type",
        "content_hash",
        "supporting_excerpt",
        "normalized_field",
    )
    return any(
        evidence.id == record.id
        or (
            all(getattr(evidence, field) == getattr(record, field) for field in fields)
            and (
                evidence.clause_context is None or evidence.clause_context == record.clause_context
            )
        )
        for record in section.evidence
    )


def _closing_instant(value: NormalizedValue) -> datetime | None:
    values = value if isinstance(value, tuple) else (value,)
    instants = tuple(parse_absolute_deadline(item) for item in values if isinstance(item, str))
    if len(instants) != len(values) or len(instants) not in {1, 2} or None in instants:
        return None
    if len(instants) == 2 and instants[0] > instants[1]:
        return None
    return instants[-1]


def require_consistent_sources(assertions: tuple[tuple[Category, NormalizedValue], ...]) -> None:
    """Different supported category assertions require review, not a chosen winner.

    This deliberately declines unresolved source disagreement without interpreting
    new legal semantics. Technology requirements remain cumulative, as in the
    legacy handoff; alternatives inside one adapter result keep their expression.
    """
    observed = {}
    for category, value in assertions:
        if value is None or category == Category.REQUIRED_TECHNOLOGY:
            continue
        if category == Category.DEADLINE:
            normalized = _closing_instant(value)
            if normalized is None:
                continue
        else:
            values = value if isinstance(value, tuple) else (value,)
            normalized = tuple(sorted({normalize_text(item) for item in values}))
        if category in observed and observed[category] != normalized:
            raise ValueError("CANONICAL_SOURCE_CONFLICT")
        observed[category] = normalized


def compile_section_authority(results: tuple[AdapterResult, ...]) -> CompiledSectionAuthority:
    """Retain adapter semantics and exact evidence; dates describe closing only."""
    unique = {}
    for result in results:
        result = AdapterResult.model_validate(result)
        identity = (
            result.category,
            tuple(rule.id for rule in result.rules),
            tuple(record.id for record in result.evidence),
        )
        previous = unique.get(identity)
        if previous is not None and previous != result:
            raise ValueError("CANONICAL_ADAPTER_AUTHORITY_CONFLICT")
        unique.setdefault(identity, result)
    results = tuple(unique.values())
    require_consistent_sources(
        tuple(
            (result.category, result.normalized_value)
            for result in results
            if result.normalization_status == "SUPPORTED"
        )
    )
    rules = merge_rules(tuple(rule for result in results for rule in result.rules))
    evidence = merge_records(tuple(record for result in results for record in result.evidence))
    deadlines = set()
    for result in results:
        if result.category != "DEADLINE" or result.normalization_status != "SUPPORTED":
            continue
        # The production deadline adapter retains opening/closing in DATE_BETWEEN,
        # and emits either one closing instant or the ordered pair as normalized values.
        if closing := _closing_instant(result.normalized_value):
            deadlines.add(closing)
    return CompiledSectionAuthority(
        rules=rules,
        evidence=evidence,
        deadlines=tuple(sorted(deadlines)),
        supported_claim_count=sum(result.normalization_status == "SUPPORTED" for result in results),
    )
