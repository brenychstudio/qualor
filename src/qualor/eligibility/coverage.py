"""Coverage is derived from critical rule outcomes, never supplied as a PASS shortcut."""

from qualor.domain.enums import Category, CoverageState, Criticality, RuleStatus
from qualor.domain.rules import CoverageEntry, RuleCandidate, RuleEvaluation

COVERAGE_POLICY_VERSION = 1
REQUIRED_CATEGORIES = tuple(Category)


def evaluate_coverage(
    rules: tuple[RuleCandidate, ...], evaluations: tuple[RuleEvaluation, ...]
) -> tuple[CoverageEntry, ...]:
    if len(rules) != len(evaluations) or any(
        rule.id != evaluation.rule_id for rule, evaluation in zip(rules, evaluations, strict=True)
    ):
        raise ValueError("Coverage requires corresponding evaluations in rule order")
    entries = []
    for category in REQUIRED_CATEGORIES:
        pairs = [
            (r, e)
            for r, e in zip(rules, evaluations, strict=True)
            if r.criticality == Criticality.CRITICAL and r.rule_type == category
        ]
        reasons = tuple(r.not_applicable_reason for r, _ in pairs if r.not_applicable_reason)
        if not pairs:
            state = CoverageState.MISSING
        elif any(e.status == RuleStatus.UNKNOWN for _, e in pairs):
            state = CoverageState.UNKNOWN
        elif all(e.status == RuleStatus.NOT_APPLICABLE for _, e in pairs):
            state = (
                CoverageState.NOT_APPLICABLE_WITH_REASON
                if len(reasons) == len(pairs)
                else CoverageState.UNKNOWN
            )
        else:
            state = CoverageState.EVALUATED
        entries.append(
            CoverageEntry(
                category=category,
                state=state,
                rule_ids=tuple(r.id for r, _ in pairs),
                reasons=reasons,
            )
        )
    return tuple(entries)
