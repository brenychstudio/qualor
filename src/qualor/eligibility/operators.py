"""Pure comparisons. Type mismatch and unsupported shapes preserve uncertainty."""

from qualor.domain.enums import Operator, RuleStatus
from qualor.domain.values import Scalar


def evaluate_operator(
    operator: Operator,
    actual: Scalar | tuple[Scalar, ...] | None,
    operands: tuple[Scalar, ...],
    statuses: tuple[RuleStatus, ...] = (),
) -> RuleStatus:
    if operator in {Operator.AND, Operator.OR}:
        if not statuses or actual is not None or operands:
            return RuleStatus.UNKNOWN
        if operator == Operator.AND:
            if RuleStatus.FAIL in statuses:
                return RuleStatus.FAIL
            return (
                RuleStatus.PASS
                if all(s == RuleStatus.PASS for s in statuses)
                else RuleStatus.UNKNOWN
            )
        if RuleStatus.PASS in statuses:
            return RuleStatus.PASS
        return (
            RuleStatus.FAIL if all(s == RuleStatus.FAIL for s in statuses) else RuleStatus.UNKNOWN
        )

    if actual is None or not operands or statuses:
        return RuleStatus.UNKNOWN
    if isinstance(actual, tuple):
        # A declared stack must contain at least one allowed technology. Use AND
        # of single-technology membership rules when every technology is required.
        if operator != Operator.IN or not actual:
            return RuleStatus.UNKNOWN
        if any(item.kind != "text" for item in (*actual, *operands)):
            return RuleStatus.UNKNOWN
        return (
            RuleStatus.PASS
            if any(item.value == allowed.value for item in actual for allowed in operands)
            else RuleStatus.FAIL
        )
    if any(item.kind != actual.kind for item in operands):
        return RuleStatus.UNKNOWN
    first = operands[0].value
    value = actual.value
    if operator == Operator.IN:
        matched = value in [item.value for item in operands]
    elif operator in {Operator.EQ, Operator.BOOL_IS}:
        if len(operands) != 1 or (operator == Operator.BOOL_IS and actual.kind != "bool"):
            return RuleStatus.UNKNOWN
        matched = value == first
    elif operator in {Operator.GTE, Operator.LTE}:
        if actual.kind != "number" or len(operands) != 1:
            return RuleStatus.UNKNOWN
        matched = value >= first if operator == Operator.GTE else value <= first
    elif operator in {Operator.BETWEEN, Operator.DATE_BETWEEN}:
        allowed = {"number"} if operator == Operator.BETWEEN else {"date", "instant"}
        if actual.kind not in allowed or len(operands) != 2 or first > operands[1].value:
            return RuleStatus.UNKNOWN
        matched = first <= value <= operands[1].value
    else:
        return RuleStatus.UNKNOWN
    return RuleStatus.PASS if matched else RuleStatus.FAIL
