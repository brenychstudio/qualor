"""Deterministic rule and aggregate authority. No external calls or supplied verdicts."""

import hashlib

from qualor.domain.enums import (
    CoverageState,
    Criticality,
    GateState,
    Operator,
    Provenance,
    ReasonCode,
    RuleStatus,
)
from qualor.domain.fixture import EvaluationContext
from qualor.domain.rules import EligibilityGate, RuleCandidate, RuleEvaluation

from .coverage import evaluate_coverage
from .evidence import evidence_issues
from .operators import evaluate_operator
from .subjects import resolve_subject

ELIGIBILITY_POLICY_VERSION = 1


def _evaluate(rule: RuleCandidate, context: EvaluationContext) -> RuleEvaluation:
    children = tuple(_evaluate(child, context) for child in rule.children)
    issues = list(evidence_issues(rule, context))
    if rule.contradiction:
        issues.append(ReasonCode.CONFLICT)
    if not rule.supported:
        issues.append(ReasonCode.UNSUPPORTED)
    if rule.operator in {Operator.AND, Operator.OR}:
        # Uncertainty can be resolved by an alternative; stale/conflicting critical evidence cannot.
        for child in children:
            issues.extend(
                code
                for code in child.reason_codes
                if code in {ReasonCode.STALE_EVIDENCE, ReasonCode.CONFLICT}
            )
        if (
            rule.subject_reference is not None
            or rule.operands
            or any(child.rule_type != rule.rule_type for child in rule.children)
        ):
            issues.append(ReasonCode.INVALID_OPERANDS)
        status = evaluate_operator(rule.operator, None, (), tuple(c.status for c in children))
    elif children:
        status = RuleStatus.UNKNOWN
        issues.append(ReasonCode.INVALID_OPERANDS)
    else:
        actual, reason = resolve_subject(rule, context)
        status = evaluate_operator(rule.operator, actual, rule.operands)
        if status == RuleStatus.UNKNOWN and not rule.not_applicable_reason:
            issues.append(reason if actual is None else ReasonCode.INVALID_OPERANDS)
    if issues:
        status = RuleStatus.UNKNOWN
    elif rule.not_applicable_reason:
        status = RuleStatus.NOT_APPLICABLE
    if not issues:
        issues.append(
            {
                RuleStatus.PASS: ReasonCode.MATCH,
                RuleStatus.FAIL: ReasonCode.MISMATCH,
                RuleStatus.UNKNOWN: ReasonCode.CRITICAL_UNKNOWN,
                RuleStatus.NOT_APPLICABLE: ReasonCode.EXPLICIT_NOT_APPLICABLE,
            }[status]
        )
    codes = tuple(dict.fromkeys(issues))
    return RuleEvaluation(
        schema_version="1",
        id="evaluation_" + rule.id,
        version=1,
        created_at=context.evaluated_at,
        updated_at=context.evaluated_at,
        provenance=Provenance.DOCUMENTED,
        rule_id=rule.id,
        status=status,
        reason_code=codes[0],
        reason_codes=codes,
        evidence_ids=rule.evidence_ids,
        subject_reference=rule.subject_reference,
        policy_version=ELIGIBILITY_POLICY_VERSION,
        evaluated_at=context.evaluated_at,
        children=children,
    )


def _validated_rules(rules: tuple[RuleCandidate, ...]) -> tuple[RuleCandidate, ...]:
    validated = tuple(RuleCandidate.model_validate(rule) for rule in rules)
    seen: set[str] = set()

    def visit(rule: RuleCandidate, depth: int) -> None:
        if depth > 16 or len(seen) >= 500:
            raise ValueError("Rule tree exceeds V1 evaluation limits")
        if rule.id in seen:
            raise ValueError("Duplicate rule IDs")
        seen.add(rule.id)
        for child in rule.children:
            if child.criticality != rule.criticality:
                raise ValueError("Composite children must preserve the parent criticality")
            visit(child, depth + 1)

    for rule in validated:
        visit(rule, 0)
    return validated


def evaluate_rule(rule: RuleCandidate, context: EvaluationContext) -> RuleEvaluation:
    return evaluate_rules((rule,), context)[0]


def evaluate_rules(
    rules: tuple[RuleCandidate, ...], context: EvaluationContext
) -> tuple[RuleEvaluation, ...]:
    context = EvaluationContext.model_validate(context)
    return tuple(_evaluate(rule, context) for rule in _validated_rules(rules))


def aggregate_eligibility(
    rules: tuple[RuleCandidate, ...], context: EvaluationContext
) -> EligibilityGate:
    context = EvaluationContext.model_validate(context)
    rules = _validated_rules(rules)
    evaluations = tuple(_evaluate(rule, context) for rule in rules)
    coverage = evaluate_coverage(rules, evaluations)
    critical = tuple(
        e for r, e in zip(rules, evaluations, strict=True) if r.criticality == Criticality.CRITICAL
    )
    reasons = [code for e in critical for code in e.reason_codes if code != ReasonCode.MATCH]
    missing = [
        entry.category.value
        for entry in coverage
        if entry.state in {CoverageState.MISSING, CoverageState.UNKNOWN}
    ]
    missing.extend(e.rule_id for e in critical if e.status == RuleStatus.UNKNOWN)
    if not rules:
        reasons.append(ReasonCode.EMPTY_RULE_SET)
    if missing:
        reasons.append(ReasonCode.INCOMPLETE_COVERAGE)
    if any(e.status == RuleStatus.FAIL for e in critical):
        state = GateState.FAIL
    elif not rules or missing or any(e.status == RuleStatus.UNKNOWN for e in critical):
        state = GateState.REVIEW_REQUIRED
    else:
        state = GateState.PASS
    digest = hashlib.sha256(
        (context.model_dump_json() + "".join(r.model_dump_json() for r in rules)).encode()
    ).hexdigest()
    return EligibilityGate(
        schema_version="1",
        id="gate_" + digest,
        version=1,
        created_at=context.evaluated_at,
        updated_at=context.evaluated_at,
        provenance=Provenance.DOCUMENTED,
        state=state,
        evaluations=evaluations,
        critical_coverage=coverage,
        missing_information=tuple(dict.fromkeys(missing)),
        reason_codes=tuple(dict.fromkeys(reasons)),
        policy_version=ELIGIBILITY_POLICY_VERSION,
        evaluated_at=context.evaluated_at,
    )
