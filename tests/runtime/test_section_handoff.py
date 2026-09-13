"""Offline production adapters feed the one existing decision authority."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from qualor.domain.base import Fact
from qualor.domain.fixture import EvaluationInput
from qualor.eligibility.evidence import effective_deadlines
from qualor.runtime.adapters import adapt_candidate
from qualor.runtime.claims import ExtractedClaim, validate_claim
from qualor.runtime.handoff import compile_decision_bundle
from qualor.runtime.run_models import RuntimeDecisionBundle

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)
OPENING = "2026-09-01T00:00:00Z"
CLOSING = "2026-09-20T17:00:00Z"


@pytest.fixture(autouse=True)
def fixed_handoff_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr("qualor.runtime.handoff.datetime", Clock)


def run_with(inputs, results=(), claims=()):
    return SimpleNamespace(
        mode="FIXTURE",
        inputs=inputs,
        sources={},
        candidates={},
        claims={item.evidence.id: item for item in claims},
        contradictions=(),
        section_results=tuple(results),
    )


def compile_candidate(candidate):
    return adapt_candidate(candidate, evaluated_at=NOW)


@pytest.fixture
def deadline(grounded_candidate):
    return compile_candidate(
        grounded_candidate(
            "DEADLINE",
            (OPENING, CLOSING),
            f"Submissions are accepted from {OPENING} to {CLOSING}.",
        )
    )


def evaluations(bundle):
    rules = bundle.decision_input.eligibility_rules
    verdicts = bundle.decision.candidates[0].eligibility_gate.evaluations
    return {rule.rule_type: value for rule, value in zip(rules, verdicts, strict=True)}


@pytest.mark.parametrize(
    "category,value,quote,scope,field,fact_value",
    (
        (
            "ENTRANT_TYPE",
            "INDIVIDUAL",
            "Open to individuals.",
            "founder",
            "legal_form",
            "INDIVIDUAL",
        ),
        (
            "LEGAL_ENTITY",
            "INDIVIDUAL",
            "Individuals may participate.",
            "founder",
            "legal_form",
            "INDIVIDUAL",
        ),
        (
            "LICENSE",
            ("MIT", "Apache-2.0"),
            "Projects must intend to use MIT or Apache-2.0 licenses.",
            "project",
            "license_intent",
            "MIT",
        ),
        (
            "FINANCIAL_SUPPORT",
            "PROHIBITED",
            "Projects must not have sponsor support.",
            "project",
            "has_sponsor_support",
            False,
        ),
        (
            "REWARD_CONDITIONS",
            "REQUIRED",
            "Projects must meet reward conditions.",
            "project",
            "reward_conditions_met",
            True,
        ),
    ),
)
def test_formerly_unmapped_rules_use_only_independent_facts(
    grounded_candidate, studio_inputs, deadline, category, value, quote, scope, field, fact_value
):
    result = compile_candidate(
        grounded_candidate(
            category,
            value,
            quote,
            text=quote,
            qualifiers=(quote,) if category == "FINANCIAL_SUPPORT" else (),
        )
    )
    unknown = compile_decision_bundle(run_with(studio_inputs, (deadline, result)))
    assert category in evaluations(unknown)
    assert evaluations(unknown)[category].status == "UNKNOWN"
    assert unknown.decision_input.founder == studio_inputs.founder
    assert unknown.decision_input.projects == studio_inputs.projects
    fact = Fact(value=fact_value, provenance="USER_ASSERTED")
    if scope == "founder":
        inputs = studio_inputs.model_copy(
            update={"founder": studio_inputs.founder.model_copy(update={field: fact})}
        )
    else:
        project = studio_inputs.projects[0]
        inputs = studio_inputs.model_copy(
            update={
                "projects": (
                    project.model_copy(
                        update={"project": project.project.model_copy(update={field: fact})}
                    ),
                )
            }
        )
    known = compile_decision_bundle(run_with(inputs, (deadline, result)))
    assert evaluations(known)[category].status == "PASS"
    assert known.opportunity.organizer == known.opportunity.program_name == "UNKNOWN"
    assert known.opportunity.rewards == ()
    assert known.opportunity.matching_requirements is None


def test_interval_opening_never_becomes_an_effective_closing_deadline(studio_inputs, deadline):
    bundle = compile_decision_bundle(run_with(studio_inputs, (deadline,)))
    closing = datetime(2026, 9, 20, 17, tzinfo=UTC)
    assert bundle.opportunity.deadlines == (closing,)
    rule = bundle.decision_input.eligibility_rules[0]
    assert rule.operator == "DATE_BETWEEN"
    assert tuple(value.value for value in rule.operands) == (
        datetime(2026, 9, 1, tzinfo=UTC),
        closing,
    )
    context = EvaluationInput(
        founder=bundle.decision_input.founder,
        project=bundle.decision_input.projects[0].project,
        opportunity=bundle.opportunity,
        evidence=bundle.evidence,
        evaluated_at=NOW,
        mode="FIXTURE",
    )
    assert set(effective_deadlines((rule,), context)) == {closing}
    assert evaluations(bundle)["DEADLINE"].status == "PASS"
    assert bundle.decision.recommendation == "WATCH"


@pytest.mark.parametrize(
    "value,quote,expected",
    (
        (CLOSING, f"Deadline: {CLOSING}.", (datetime(2026, 9, 20, 17, tzinfo=UTC),)),
        ("2026-09-20", "Deadline: 2026-09-20.", ()),
        ("September 20, 2026 at 5:00 PM CST", "Deadline: September 20, 2026 at 5:00 PM CST.", ()),
    ),
)
def test_only_supported_absolute_closings_enter_opportunity(
    grounded_candidate, studio_inputs, value, quote, expected
):
    result = compile_candidate(grounded_candidate("DEADLINE", value, quote))
    bundle = compile_decision_bundle(run_with(studio_inputs, (result,)))
    assert bundle.opportunity.deadlines == expected
    assert evaluations(bundle)["DEADLINE"].status == "UNKNOWN"


def test_open_legal_residual_cannot_pass_from_country_not_excluded(
    grounded_candidate, studio_inputs, deadline
):
    result = compile_candidate(
        grounded_candidate(
            "GEOGRAPHY",
            "Northland",
            "Entrants must not reside in Northland or any jurisdiction where participation "
            "is prohibited by law.",
        )
    )
    inputs = studio_inputs.model_copy(
        update={
            "founder": studio_inputs.founder.model_copy(
                update={"country_of_residence": Fact(value="Southland", provenance="USER_ASSERTED")}
            )
        }
    )
    bundle = compile_decision_bundle(run_with(inputs, (result, deadline)))
    assert evaluations(bundle)["GEOGRAPHY"].status == "UNKNOWN"
    assert bundle.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"
    geography = next(
        r for r in bundle.decision_input.eligibility_rules if r.rule_type == "GEOGRAPHY"
    )
    assert geography.operator == "AND"
    assert len(geography.children) == 2
    assert not geography.supported


def test_nested_alternatives_and_conjunctions_reach_existing_engine(
    grounded_candidate, studio_inputs, deadline, monkeypatch
):
    import qualor.runtime.handoff as handoff

    result = compile_candidate(
        grounded_candidate(
            "LEGAL_ENTITY",
            ("INDIVIDUAL", "INCORPORATED_COMPANY"),
            "Open to individuals or incorporated companies incorporated between "
            "2020-01-01 and 2026-01-01.",
        )
    )
    inputs = studio_inputs.model_copy(
        update={
            "founder": studio_inputs.founder.model_copy(
                update={"legal_form": Fact(value="INDIVIDUAL", provenance="USER_ASSERTED")}
            )
        }
    )
    spy = Mock(wraps=handoff.decide)
    monkeypatch.setattr(handoff, "decide", spy)
    run = run_with(inputs, (result, deadline))
    run.opportunity_version_resolver = lambda opportunity: opportunity.model_copy(
        update={"version": 7}
    )
    bundle = handoff.compile_decision_bundle(run)
    assert spy.call_count == 1
    assert spy.call_args.args == (bundle.decision_input,)
    assert bundle.opportunity.version == 7
    assert all(item.opportunity_version == 7 for item in bundle.decision.candidates)
    legal = next(
        r for r in bundle.decision_input.eligibility_rules if r.rule_type == "LEGAL_ENTITY"
    )
    assert legal.operator == "OR"
    assert legal.children[1].operator == "AND"
    assert legal.children[1].children[1].operator == "DATE_BETWEEN"
    assert evaluations(bundle)["LEGAL_ENTITY"].status == "PASS"
    assert evaluations(bundle)["LEGAL_ENTITY"].children[1].status == "FAIL"


def test_qualifiers_exceptions_and_evidence_survive_bundle_serialization(
    grounded_candidate, studio_inputs, deadline
):
    quote = "Projects must use Copper SDK and Silver API."
    qualifier = "Entrants must obtain organizer approval."
    exception = "Except where the organizer authorizes a substitute."
    candidate = grounded_candidate(
        "REQUIRED_TECHNOLOGY",
        ("Copper SDK", "Silver API"),
        quote,
        qualifiers=(qualifier,),
        exceptions=(exception,),
    )
    result = compile_candidate(candidate)
    bundle = compile_decision_bundle(run_with(studio_inputs, (result, deadline)))
    restored = RuntimeDecisionBundle.model_validate_json(bundle.model_dump_json())
    rules = {rule.id: rule for rule in restored.decision_input.eligibility_rules}
    assert result.rules[0].id in rules
    assert rules[result.rules[0].id] == result.rules[0]
    assert rules[result.rules[0].id].clause_context == candidate.context
    assert candidate.context.qualifiers == (qualifier,)
    assert candidate.context.exceptions == (exception,)
    retained = {e.id: e for e in restored.evidence}
    for record in result.evidence:
        assert retained[record.id] == record
        assert retained[record.id].clause_context == candidate.context
        assert retained[record.id].provenance == "DOCUMENTED"
    assert evaluations(restored)["REQUIRED_TECHNOLOGY"].status == "UNKNOWN"


def test_duplicate_results_do_not_duplicate_rules_evidence_or_supported_count(
    grounded_candidate, studio_inputs, deadline
):
    from qualor.runtime.canonical_compilation import compile_section_authority

    result = compile_candidate(
        grounded_candidate("ENTRANT_TYPE", "INDIVIDUAL", "Open to individuals.")
    )
    first = compile_section_authority((result, deadline))
    repeated = compile_section_authority((deadline, result, deadline, result))
    assert first == repeated
    assert repeated.supported_claim_count == 2
    assert len(repeated.rules) == len(repeated.evidence) == 2
    assert compile_decision_bundle(run_with(studio_inputs, (result, deadline))) == (
        compile_decision_bundle(run_with(studio_inputs, (deadline, result, result, deadline)))
    )


@pytest.mark.parametrize("kind", ("evidence", "rule", "nested_rule"))
def test_conflicting_immutable_ids_fail_closed_before_decision(
    grounded_candidate, studio_inputs, monkeypatch, kind
):
    import qualor.runtime.handoff as handoff

    result = compile_candidate(
        grounded_candidate(
            "REQUIRED_TECHNOLOGY",
            ("Copper SDK", "Silver API"),
            "Projects must use Copper SDK and Silver API.",
        )
    )
    if kind == "evidence":
        changed = result.model_copy(
            update={"evidence": (result.evidence[0].model_copy(update={"content_hash": "f" * 64}),)}
        )
    else:
        root = result.rules[0]
        if kind == "nested_rule":
            root = root.model_copy(
                update={
                    "id": "other-root",
                    "children": (
                        root.children[0].model_copy(update={"supported": False}),
                        root.children[1],
                    ),
                }
            )
        else:
            root = root.model_copy(update={"supported": False})
        changed = result.model_copy(update={"rules": (root,)})
    spy = Mock(wraps=handoff.decide)
    monkeypatch.setattr(handoff, "decide", spy)
    for order in ((result, changed), (changed, result)):
        with pytest.raises(ValueError, match="CONFLICT"):
            handoff.compile_decision_bundle(run_with(studio_inputs, order))
    assert spy.call_count == 0


def test_mirrored_legacy_claim_does_not_duplicate_section_rule_or_drop_other_evidence(
    grounded_candidate, studio_inputs, document
):
    candidate = grounded_candidate(
        "REQUIRED_TECHNOLOGY",
        "Widget SDK",
        "Projects must use Widget SDK.",
    )
    result = compile_candidate(candidate)

    def legacy(source):
        return validate_claim(
            ExtractedClaim(
                source_id=source.id,
                source_url=source.final_url,
                field="required_technology",
                value="Widget SDK",
                excerpt="Projects must use Widget SDK.",
                state="CANDIDATE",
                confidence="HIGH",
            ),
            {source.id: source},
        )

    mirror = legacy(candidate.source)
    other = document("Projects must use Widget SDK.").model_copy(
        update={
            "id": "independent-source",
            "final_url": "https://example.org/faq",
        }
    )
    independent = legacy(other)
    bundle = compile_decision_bundle(run_with(studio_inputs, (result,), (mirror, independent)))
    assert len(bundle.decision_input.eligibility_rules) == 2
    assert {e.id for e in bundle.evidence} == {
        result.evidence[0].id,
        mirror.evidence.id,
        independent.evidence.id,
    }
    assert result.rules[0].id in {r.id for r in bundle.decision_input.eligibility_rules}
    # The independent legacy claim still contributes its established requirements.
    assert bundle.opportunity.matching_requirements.technologies.evidence_refs == (
        independent.evidence.id,
    )


def test_same_evidence_id_shared_by_legacy_and_section_is_reused(grounded_candidate, studio_inputs):
    candidate = grounded_candidate("PROJECT_POLICY", "NEW_ONLY", "Projects must be new.")
    result = compile_candidate(candidate)
    admitted = validate_claim(
        ExtractedClaim(
            source_id=candidate.source.id,
            source_url=candidate.source.final_url,
            field="project_policy",
            value="NEW_ONLY",
            excerpt=candidate.quotes[0],
            state="CANDIDATE",
            confidence="HIGH",
        ),
        {candidate.source.id: candidate.source},
    ).model_copy(update={"evidence": result.evidence[0]})
    bundle = compile_decision_bundle(run_with(studio_inputs, (result,), (admitted,)))
    assert bundle.decision_input.eligibility_rules == result.rules
    assert bundle.evidence == result.evidence


def test_empty_sections_preserve_legacy_bundle_bytes(studio_inputs, document):
    source = document("Projects must use Widget SDK.")
    admitted = validate_claim(
        ExtractedClaim(
            source_id=source.id,
            source_url=source.final_url,
            field="required_technology",
            value="Widget SDK",
            excerpt=source.text,
            state="CANDIDATE",
            confidence="HIGH",
        ),
        {source.id: source},
    )
    run = run_with(studio_inputs, claims=(admitted,))
    with_empty = compile_decision_bundle(run).model_dump_json()
    del run.section_results
    assert compile_decision_bundle(run).model_dump_json() == with_empty


def test_shared_child_identity_cannot_weaken_a_separate_top_level_obligation(
    grounded_candidate, studio_inputs
):
    result = compile_candidate(
        grounded_candidate(
            "LEGAL_ENTITY",
            ("INDIVIDUAL", "INCORPORATED_COMPANY"),
            "Open to individuals or incorporated companies.",
        )
    )
    # A repeated node in a different logical position is not a repeated whole result:
    # OR(individual, company) AND individual cannot be reduced to the OR alone.
    separate = result.model_copy(update={"rules": (result.rules[0].children[0],)})
    with pytest.raises(ValueError, match="STRUCTURE_CONFLICT"):
        compile_decision_bundle(run_with(studio_inputs, (result, separate)))


def test_unsupported_and_optional_observations_keep_evidence_without_invented_rules(
    grounded_candidate, studio_inputs
):
    from qualor.runtime.canonical_compilation import compile_section_authority

    unsupported = compile_candidate(
        grounded_candidate(
            "REWARD_CONDITIONS",
            "1000",
            "The total prize pool is 1000 credits.",
        )
    )
    optional = compile_candidate(
        grounded_candidate(
            "REQUIRED_TECHNOLOGY",
            "Widget SDK",
            "Projects may optionally use Widget SDK.",
        )
    )
    authority = compile_section_authority((unsupported, optional, optional))
    assert authority.supported_claim_count == 1
    assert len(authority.evidence) == 2
    assert len(authority.rules) == 1
    assert not authority.rules[0].supported
    bundle = compile_decision_bundle(run_with(studio_inputs, (unsupported, optional)))
    assert bundle.opportunity.rewards == ()
    assert bundle.opportunity.matching_requirements is None
    assert bundle.opportunity.deadlines == ()
    assert bundle.decision.candidates[0].eligibility_gate.state == "REVIEW_REQUIRED"


def test_section_extension_exception_removes_mirrored_legacy_deadline_authority(
    grounded_candidate, studio_inputs
):
    expired = "2026-09-01T17:00:00Z"
    quote = f"Deadline: {expired}."
    exception = "Except where the organizer grants an extension."
    candidate = grounded_candidate("DEADLINE", expired, quote, exceptions=(exception,))
    result = compile_candidate(candidate)
    legacy = validate_claim(
        ExtractedClaim(
            source_id=candidate.source.id,
            source_url=candidate.source.final_url,
            field="deadline",
            value=expired,
            excerpt=quote,
            state="CANDIDATE",
            confidence="HIGH",
        ),
        {candidate.source.id: candidate.source},
    )
    assert legacy.normalization_status == "SUPPORTED"
    assert result.normalization_status == "UNKNOWN"
    bundle = compile_decision_bundle(run_with(studio_inputs, (result,), (legacy,)))
    assert bundle.opportunity.deadlines == ()
    assert bundle.decision.recommendation == "WATCH"
    assert {item.id for item in bundle.evidence} == {
        legacy.evidence.id,
        *(item.id for item in result.evidence),
    }
    assert bundle.decision_input.eligibility_rules == result.rules


@pytest.mark.parametrize("category", ("FINANCIAL_SUPPORT", "DEADLINE"))
def test_distinct_source_contradictions_fail_before_decision(
    category, grounded_candidate, studio_inputs, monkeypatch
):
    import qualor.runtime.handoff as handoff
    from qualor.runtime.canonical_compilation import compile_section_authority

    if category == "FINANCIAL_SUPPORT":
        quote = "Projects must not have sponsor support."
        first = compile_candidate(
            grounded_candidate(
                category,
                "PROHIBITED",
                quote,
                text=quote,
                qualifiers=(quote,),
            )
        )
        second = compile_candidate(
            grounded_candidate(
                category,
                "REQUIRED",
                "Projects must have sponsor support.",
            )
        )
    else:
        first = compile_candidate(
            grounded_candidate(
                category,
                CLOSING,
                f"Deadline: {CLOSING}.",
            )
        )
        expired = "2026-09-01T17:00:00Z"
        second = compile_candidate(
            grounded_candidate(
                category,
                expired,
                f"Deadline: {expired}.",
            )
        )
    assert first.normalization_status == second.normalization_status == "SUPPORTED"
    assert first.evidence[0].id != second.evidence[0].id
    spy = Mock(wraps=handoff.decide)
    monkeypatch.setattr(handoff, "decide", spy)
    for order in ((first, second), (second, first)):
        with pytest.raises(ValueError, match="SOURCE_CONFLICT"):
            compile_section_authority(order)
        with pytest.raises(ValueError, match="SOURCE_CONFLICT"):
            handoff.compile_decision_bundle(run_with(studio_inputs, order))
    assert spy.call_count == 0


@pytest.mark.parametrize("category", ("FINANCIAL_SUPPORT", "DEADLINE"))
def test_mixed_legacy_and_section_contradictions_fail_before_decision(
    category, grounded_candidate, document, studio_inputs, monkeypatch
):
    import qualor.runtime.handoff as handoff

    if category == "FINANCIAL_SUPPORT":
        quote = "Projects must not have sponsor support."
        result = compile_candidate(
            grounded_candidate(
                category,
                "PROHIBITED",
                quote,
                text=quote,
                qualifiers=(quote,),
            )
        )
        legacy_value = "REQUIRED"
        legacy_quote = "Sponsor support is REQUIRED."
    else:
        result = compile_candidate(
            grounded_candidate(
                category,
                CLOSING,
                f"Deadline: {CLOSING}.",
            )
        )
        legacy_value = "2026-09-01T17:00:00Z"
        legacy_quote = f"Deadline: {legacy_value}."
    source = document(legacy_quote)
    legacy = validate_claim(
        ExtractedClaim(
            source_id=source.id,
            source_url=source.final_url,
            field=category.lower(),
            value=legacy_value,
            excerpt=legacy_quote,
            state="CANDIDATE",
            confidence="HIGH",
        ),
        {source.id: source},
    )
    assert legacy.normalization_status == result.normalization_status == "SUPPORTED"
    spy = Mock(wraps=handoff.decide)
    monkeypatch.setattr(handoff, "decide", spy)
    with pytest.raises(ValueError, match="SOURCE_CONFLICT"):
        handoff.compile_decision_bundle(run_with(studio_inputs, (result,), (legacy,)))
    assert spy.call_count == 0


def test_compatible_interval_and_closing_sources_keep_one_closing(
    grounded_candidate, studio_inputs, deadline
):
    closing = compile_candidate(
        grounded_candidate(
            "DEADLINE",
            CLOSING,
            f"Deadline: {CLOSING}.",
        )
    )
    bundle = compile_decision_bundle(run_with(studio_inputs, (deadline, closing)))
    assert bundle.opportunity.deadlines == (datetime(2026, 9, 20, 17, tzinfo=UTC),)
    assert len(bundle.decision_input.eligibility_rules) == 2
