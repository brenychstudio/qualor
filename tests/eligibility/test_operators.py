from itertools import product

import pytest

from qualor.domain.enums import Operator, RuleStatus
from qualor.domain.values import BoolValue, DateValue, NumberValue, TextValue


@pytest.mark.parametrize(
    "case,op,actual,operands,expected",
    [
        ("A07", "EQ", TextValue(value="ES"), (TextValue(value="ES"),), "PASS"),
        ("A08", "EQ", TextValue(value="ES"), (TextValue(value="FR"),), "FAIL"),
        ("A09", "EQ", None, (TextValue(value="ES"),), "UNKNOWN"),
        (
            "A10",
            "IN",
            TextValue(value="ES"),
            (TextValue(value="ES"), TextValue(value="FR")),
            "PASS",
        ),
        ("A11", "IN", TextValue(value="GB"), (TextValue(value="ES"),), "FAIL"),
        ("A12gte", "GTE", NumberValue(value="2"), (NumberValue(value="2"),), "PASS"),
        ("A12lte", "LTE", NumberValue(value="3"), (NumberValue(value="2"),), "FAIL"),
        (
            "A13low",
            "BETWEEN",
            NumberValue(value="1"),
            (NumberValue(value="1"), NumberValue(value="2")),
            "PASS",
        ),
        (
            "A13high",
            "BETWEEN",
            NumberValue(value="2"),
            (NumberValue(value="1"), NumberValue(value="2")),
            "PASS",
        ),
        (
            "A14",
            "DATE_BETWEEN",
            DateValue(value="2026-09-05"),
            (DateValue(value="2026-09-01"), DateValue(value="2026-09-05")),
            "PASS",
        ),
        ("A15", "BOOL_IS", BoolValue(value=False), (BoolValue(value=False),), "PASS"),
        ("bool_not_number", "EQ", BoolValue(value=True), (NumberValue(value="1"),), "UNKNOWN"),
        ("text_not_number", "GTE", TextValue(value="20"), (NumberValue(value="1"),), "UNKNOWN"),
        ("empty_membership", "IN", TextValue(value="ES"), (), "UNKNOWN"),
        (
            "reversed_range",
            "BETWEEN",
            NumberValue(value="2"),
            (NumberValue(value="3"), NumberValue(value="1")),
            "UNKNOWN",
        ),
        ("arity", "EQ", TextValue(value="ES"), (), "UNKNOWN"),
    ],
)
def test_scalar_cases(case, op, actual, operands, expected):
    from qualor.eligibility.operators import evaluate_operator

    assert evaluate_operator(Operator(op), actual, operands) == expected


@pytest.mark.parametrize(
    "case,op,statuses,expected",
    [
        ("A16", "OR", ("PASS", "UNKNOWN"), "PASS"),
        ("A17", "OR", ("FAIL", "UNKNOWN"), "UNKNOWN"),
        ("A18", "AND", ("PASS", "UNKNOWN"), "UNKNOWN"),
        ("A19", "AND", ("FAIL", "UNKNOWN"), "FAIL"),
        ("empty_and", "AND", (), "UNKNOWN"),
        ("empty_or", "OR", (), "UNKNOWN"),
        ("na_not_pass", "OR", ("NOT_APPLICABLE", "FAIL"), "UNKNOWN"),
    ],
)
def test_logical_cases(case, op, statuses, expected):
    from qualor.eligibility.operators import evaluate_operator

    assert evaluate_operator(Operator(op), None, (), tuple(map(RuleStatus, statuses))) == expected


@pytest.mark.parametrize("left,right", list(product(("PASS", "FAIL", "UNKNOWN"), repeat=2)))
def test_full_truth_tables(left, right):
    from qualor.eligibility.operators import evaluate_operator

    values = (RuleStatus(left), RuleStatus(right))
    expected_and = (
        "FAIL" if "FAIL" in values else "PASS" if values == ("PASS", "PASS") else "UNKNOWN"
    )
    expected_or = (
        "PASS" if "PASS" in values else "FAIL" if values == ("FAIL", "FAIL") else "UNKNOWN"
    )
    assert evaluate_operator(Operator.AND, None, (), values) == expected_and
    assert evaluate_operator(Operator.OR, None, (), values) == expected_or
