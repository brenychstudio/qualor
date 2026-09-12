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


# --- NOT_IN: exclusion-list eligibility -------------------------------------------------
#
# Official eligibility is frequently written as an exclusion list -- open to everyone except
# these jurisdictions -- which IN cannot express without inverting the source into an invented
# allow-list. NOT_IN inherits every conservative guard the other scalar operators already
# have: an unknown subject, an unstated source set, or a type mismatch all stay UNKNOWN.


@pytest.mark.parametrize(
    "case,actual,operands,expected",
    [
        ("excluded value is refused", TextValue(value="Russia"),
         (TextValue(value="Russia"), TextValue(value="Cuba")), "FAIL"),
        ("value outside the excluded set passes", TextValue(value="Spain"),
         (TextValue(value="Russia"), TextValue(value="Cuba")), "PASS"),
        ("an unknown subject stays unknown", None, (TextValue(value="Russia"),), "UNKNOWN"),
        ("an unstated excluded set stays unknown", TextValue(value="Spain"), (), "UNKNOWN"),
        ("a type mismatch stays unknown", TextValue(value="Spain"),
         (NumberValue(value="1"),), "UNKNOWN"),
    ],
)
def test_not_in_excludes_without_inventing_an_allow_list(case, actual, operands, expected):
    from qualor.eligibility.operators import evaluate_operator

    assert evaluate_operator(Operator.NOT_IN, actual, operands) == RuleStatus(expected), case


def test_not_in_over_a_declared_collection_stays_unknown():
    """Excluding one member of a declared stack is not the same as excluding the stack."""
    from qualor.eligibility.operators import evaluate_operator

    assert evaluate_operator(
        Operator.NOT_IN,
        (TextValue(value="Python"), TextValue(value="Rust")),
        (TextValue(value="Rust"),),
    ) == RuleStatus.UNKNOWN


def test_in_and_not_in_are_exact_complements_on_comparable_scalars():
    """Neither operator may quietly become the other, at any value in the set or outside it."""
    from qualor.eligibility.operators import evaluate_operator

    operands = (TextValue(value="Russia"), TextValue(value="Cuba"))
    for value in ("Russia", "Cuba", "Spain", "Portugal"):
        actual = TextValue(value=value)
        inside = evaluate_operator(Operator.IN, actual, operands)
        outside = evaluate_operator(Operator.NOT_IN, actual, operands)
        assert {inside, outside} == {RuleStatus.PASS, RuleStatus.FAIL}, value
