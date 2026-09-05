from datetime import timedelta

import pytest
from conftest import replace
from pydantic import ValidationError

from qualor.domain.enums import Category


def legal_rule(rules):
    return next(rule for rule in rules if rule.rule_type == Category.LEGAL_ENTITY)


def change_rule(rules, category=Category.LEGAL_ENTITY, **changes):
    return tuple(replace(rule, **changes) if rule.rule_type == category else rule for rule in rules)


def test_A01_full_coverage_pass_and_repeatable(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    gate = aggregate_eligibility(rules, context)
    assert gate.state == "PASS"
    assert len(gate.critical_coverage) == 9
    assert gate.model_dump_json() == aggregate_eligibility(rules, context).model_dump_json()


def test_A02_A21_hard_fail_overrides_missing_coverage(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    context = replace(
        context,
        founder=replace(
            context.founder, legal_form={"value": "SOLE_TRADER", "provenance": "USER_ASSERTED"}
        ),
    )
    gate = aggregate_eligibility((legal_rule(rules),), context)
    assert gate.state == "FAIL"
    assert gate.evaluations[0].status == "FAIL"


def test_A03_critical_unknown_review(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    context = replace(context, founder=replace(context.founder, legal_form={}))
    assert aggregate_eligibility(rules, context).state == "REVIEW_REQUIRED"


def test_A04_stale_critical_evidence_review(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    context = replace(
        context,
        evidence=tuple(
            replace(e, retrieved_at=context.evaluated_at - timedelta(hours=25))
            for e in context.evidence
        ),
    )
    gate = aggregate_eligibility(rules, context)
    assert gate.state == "REVIEW_REQUIRED"
    assert "STALE_EVIDENCE" in gate.reason_codes


def test_A05_missing_is_not_na(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    gate = aggregate_eligibility((legal_rule(rules),), context)
    assert gate.state == "REVIEW_REQUIRED"
    assert sum(c.state == "MISSING" for c in gate.critical_coverage) == 8


def test_A06_empty_rules_review(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, _ = scenario()
    gate = aggregate_eligibility((), context)
    assert gate.state == "REVIEW_REQUIRED"
    assert "EMPTY_RULE_SET" in gate.reason_codes


def test_A20_residence_not_citizenship(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    rules = change_rule(
        rules,
        Category.GEOGRAPHY,
        subject_reference="founder.citizenship",
        not_applicable_reason=None,
        operands=[dict(kind="text", value="Spain")],
    )
    gate = aggregate_eligibility(rules, context)
    assert gate.state == "REVIEW_REQUIRED"
    assert next(e for e in gate.evaluations if e.rule_id == "r_GEOGRAPHY").status == "UNKNOWN"


@pytest.mark.parametrize("source", ["SEARCH_SNIPPET", "THIRD_PARTY", "OFFICIAL_ANNOUNCEMENT"])
def test_A22_geography_silence_in_snippet_not_worldwide(scenario, source):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    context = replace(
        context,
        evidence=tuple(
            replace(e, source_type=source) if e.normalized_field == Category.GEOGRAPHY else e
            for e in context.evidence
        ),
    )
    rules = change_rule(
        rules,
        Category.GEOGRAPHY,
        subject_reference="founder.country_of_residence",
        not_applicable_reason=None,
        operator="IN",
        operands=[dict(kind="text", value="Spain")],
    )
    assert aggregate_eligibility(rules, context).state == "REVIEW_REQUIRED"


def test_A23_new_project_requires_documented_provenance(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    context = replace(
        context,
        project=replace(
            context.project, is_new_project={"value": True, "provenance": "USER_ASSERTED"}
        ),
    )
    rules = change_rule(
        rules,
        Category.PROJECT_POLICY,
        not_applicable_reason=None,
        subject_reference="project.is_new_project",
        operator="BOOL_IS",
        operands=[dict(kind="bool", value=True)],
    )
    gate = aggregate_eligibility(rules, context)
    assert gate.state == "REVIEW_REQUIRED"
    assert "PROVENANCE_REQUIRED" in gate.reason_codes


@pytest.mark.parametrize("ids", [[], ["absent"], ["e_GEOGRAPHY"]])
def test_A24_missing_or_unrelated_evidence_cannot_pass(scenario, ids):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    assert (
        aggregate_eligibility(change_rule(rules, evidence_ids=ids), context).state
        == "REVIEW_REQUIRED"
    )


def test_A25_unsupported_critical_candidate(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    assert (
        aggregate_eligibility(change_rule(rules, supported=False), context).state
        == "REVIEW_REQUIRED"
    )
    with pytest.raises(ValidationError):
        replace(legal_rule(rules), operator="GUESS")


def test_A26_critical_contradiction_prevents_pass(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    gate = aggregate_eligibility(change_rule(rules, contradiction=True), context)
    assert gate.state == "REVIEW_REQUIRED"
    assert "CONFLICT" in gate.reason_codes


def test_A27_na_requires_nonempty_reason_and_evidence(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    with pytest.raises(ValidationError):
        replace(legal_rule(rules), not_applicable_reason="  ")
    rules = change_rule(
        rules,
        not_applicable_reason="No incorporation required",
        evidence_ids=[],
        subject_reference=None,
        operands=[],
    )
    assert aggregate_eligibility(rules, context).state == "REVIEW_REQUIRED"


def test_noncritical_unknown_does_not_override_critical_pass(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    extra = replace(legal_rule(rules), id="optional", criticality="NON_CRITICAL", supported=False)
    assert aggregate_eligibility((*rules, extra), context).state == "PASS"


@pytest.mark.parametrize("operator,expected", [("OR", "PASS"), ("AND", "REVIEW_REQUIRED")])
def test_composite_preserves_alternatives(scenario, operator, expected):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    good = replace(legal_rule(rules), id="child_good")
    unknown = replace(good, id="child_unknown", supported=False)
    rules = change_rule(
        rules, operator=operator, operands=[], subject_reference=None, children=[good, unknown]
    )
    assert aggregate_eligibility(rules, context).state == expected


def test_stale_or_conflicted_alternative_cannot_be_hidden(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    good = replace(legal_rule(rules), id="child_good")
    conflict = replace(good, id="child_conflict", contradiction=True)
    rules = change_rule(
        rules, operator="OR", operands=[], subject_reference=None, children=[good, conflict]
    )
    assert aggregate_eligibility(rules, context).state == "REVIEW_REQUIRED"


def test_duplicate_ids_rejected_instead_of_overwriting(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    with pytest.raises(ValueError):
        aggregate_eligibility((*rules, rules[0]), context)
    with pytest.raises(ValidationError):
        replace(context, evidence=(*context.evidence, context.evidence[0]))


def test_semantically_wrong_subject_cannot_fill_category(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    rules = change_rule(
        rules,
        Category.GEOGRAPHY,
        not_applicable_reason=None,
        subject_reference="founder.legal_form",
    )
    assert aggregate_eligibility(rules, context).state == "REVIEW_REQUIRED"


def test_na_cannot_override_an_executable_rule(scenario):
    _, rules = scenario()
    with pytest.raises(ValidationError):
        replace(legal_rule(rules), not_applicable_reason="Ignore the actual rule")


def test_noncritical_parent_cannot_hide_critical_children(scenario):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    child = replace(legal_rule(rules), id="critical_child")
    parent = replace(
        child,
        id="parent",
        operator="AND",
        operands=[],
        subject_reference=None,
        criticality="NON_CRITICAL",
        children=[child],
    )
    with pytest.raises(ValueError):
        aggregate_eligibility((parent,), context)


def test_direct_rule_api_revalidates_mutated_copies(scenario):
    from qualor.eligibility import evaluate_rule

    context, rules = scenario()
    invalid = legal_rule(rules).model_copy(update={"supported": "true"})
    with pytest.raises(ValidationError):
        evaluate_rule(invalid, context)


@pytest.mark.parametrize("stack,expected", [(["Python", "Rust"], "PASS"), (["Rust"], "FAIL")])
def test_required_technology_membership(scenario, stack, expected):
    from qualor.eligibility import aggregate_eligibility

    context, rules = scenario()
    context = replace(
        context,
        project=replace(
            context.project, technology_stack={"value": stack, "provenance": "DOCUMENTED"}
        ),
    )
    rules = change_rule(
        rules,
        Category.REQUIRED_TECHNOLOGY,
        not_applicable_reason=None,
        subject_reference="project.technology_stack",
        operator="IN",
        operands=[dict(kind="text", value="Python")],
    )
    assert aggregate_eligibility(rules, context).state == expected
