"""Check evidence references and metadata without fetching or interpreting source text."""

from datetime import date, datetime

from qualor.domain.enums import ExtractionState, FreshnessStatus, ReasonCode, SourceType
from qualor.domain.fixture import EvaluationContext
from qualor.domain.rules import RuleCandidate

from .freshness import evaluate_freshness

HARD_SOURCES = {SourceType.OFFICIAL_RULES, SourceType.OFFICIAL_FAQ, SourceType.OFFICIAL_APPLICATION}


def evidence_issues(rule: RuleCandidate, context: EvaluationContext) -> tuple[ReasonCode, ...]:
    if not rule.evidence_ids:
        return (ReasonCode.MISSING_EVIDENCE,)
    lookup = {item.id: item for item in context.evidence}
    deadlines = context.opportunity.deadlines
    deadline: date | datetime | None = None
    if any(type(item) is date for item in deadlines):
        deadline = next(item for item in deadlines if type(item) is date)
    elif deadlines:
        deadline = min(deadlines)
    issues = []
    for evidence_id in rule.evidence_ids:
        evidence = lookup.get(evidence_id)
        if evidence is None:
            issues.append(ReasonCode.MISSING_EVIDENCE)
            continue
        accepted_source = evidence.source_type in HARD_SOURCES or (
            evidence.source_type == SourceType.SYNTHETIC_FIXTURE and context.mode == "FIXTURE"
        )
        if (
            not accepted_source
            or evidence.normalized_field != rule.rule_type
            or evidence.extraction_state != ExtractionState.REVIEWED
        ):
            issues.append(ReasonCode.UNVERIFIED_EVIDENCE)
        freshness = evaluate_freshness(evidence.retrieved_at, context.evaluated_at, deadline)
        if freshness == FreshnessStatus.STALE:
            issues.append(ReasonCode.STALE_EVIDENCE)
        elif freshness == FreshnessStatus.UNKNOWN:
            issues.append(ReasonCode.UNVERIFIED_EVIDENCE)
    return tuple(dict.fromkeys(issues))
