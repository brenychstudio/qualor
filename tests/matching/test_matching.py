from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from qualor.domain.base import Fact
from qualor.domain.enums import Provenance
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.planning import (
    HourRange,
    MatchingRequirements,
    MaterialKind,
    MaterialReadiness,
    MaterialRequirement,
)
from qualor.domain.profiles import ProjectProfile
from qualor.matching import assess_readiness, match_project, select_best_project

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def fact(value):
    return dict(value=value, provenance="USER_ASSERTED")


def metadata(id):
    return dict(
        id=id,
        schema_version="1",
        version=1,
        created_at=NOW,
        updated_at=NOW,
        provenance=Provenance.USER_ASSERTED,
    )


def project(**changes):
    fields = dict(
        name="Project",
        problem=fact(" Climate "),
        audience=fact("Founders"),
        stage=fact("MVP"),
        technology_stack=fact(("python", "aws")),
        available_features=fact(("search", "alerts")),
        code_provenance=fact("ORIGINAL"),
        license_intent=fact("MIT"),
        estimated_adaptation_hours=fact("10"),
        material_readiness=tuple(
            MaterialReadiness(kind=k, ready=fact(True), gap_executable=Fact()) for k in MaterialKind
        ),
    )
    fields.update(changes)
    return ProjectProfile(**metadata("p1"), **fields)


def opportunity(**changes):
    req = dict(
        problem_labels=fact(("climate",)),
        audience_labels=fact(("founders",)),
        technologies=fact(("Python", "AWS")),
        features=fact(("search", "alerts")),
        stages=fact(("MVP",)),
        licenses=fact(("MIT",)),
        original_code_required=fact(True),
        max_adaptation_hours=fact("10"),
        materials=tuple(MaterialRequirement(kind=k, required=fact(True)) for k in MaterialKind),
    )
    req.update(changes)
    return OpportunityRecord(
        **metadata("ignored"),
        organizer="Org",
        program_name="Event",
        edition="2026",
        canonical_rules_url="https://example.org/rules",
        matching_requirements=MatchingRequirements(**req),
    )


def test_b24_strong_and_explicit_references():
    result = match_project(project(), opportunity(), NOW)
    assert (result.match_status, result.comparable_score, result.rating) == ("STRONG", 100, 4)
    assert len(result.factor_results) == 7
    assert all(f.requirement_refs and f.fact_refs and f.reasons for f in result.factor_results)
    assert result.adaptation_hours == HourRange(min_hours="10", max_hours="10")


def test_b25_partial_exact_set_coverage():
    result = match_project(
        project(
            technology_stack=fact(("python",)), available_features=fact(()), stage=fact("IDEA")
        ),
        opportunity(),
        NOW,
    )
    assert (result.match_status, result.comparable_score, result.rating) == ("PARTIAL", 64, 2)


def test_b26_b28_missing_fact_is_not_imputed():
    result = match_project(project(problem=Fact()), opportunity(), NOW)
    assert result.match_status == "INSUFFICIENT_EVIDENCE"
    assert result.comparable_score is None and result.rating is None
    assert "project.problem" in result.missing_project_facts


def test_b27_tied_or_unknown_portfolio_unresolved():
    first = match_project(project(), opportunity(), NOW)
    second = match_project(project().model_copy(update={"id": "p2"}), opportunity(), NOW)
    assert select_best_project((first, second)).best_project_id is None
    unknown = match_project(
        project(problem=Fact()).model_copy(update={"id": "p2"}), opportunity(), NOW
    )
    assert select_best_project((first, unknown)).best_project_id is None
    assert select_best_project((first,)).best_project_id == "p1"
    assert select_best_project(()).best_project_id is None


@pytest.mark.parametrize(
    "executable,state", [(True, "GAPS_EXECUTABLE"), (False, "NOT_READY"), (None, "UNKNOWN")]
)
def test_b29_b30_b31_required_material_gap(executable, state):
    p = project()
    items = list(p.material_readiness)
    items[0] = MaterialReadiness(
        kind=items[0].kind,
        ready=fact(False),
        gap_executable=Fact() if executable is None else fact(executable),
    )
    assert (
        assess_readiness(
            p.model_copy(update={"material_readiness": tuple(items)}), opportunity(), NOW
        ).state
        == state
    )
    assert assess_readiness(p, opportunity(), NOW).state == "READY"
    assert (
        assess_readiness(p.model_copy(update={"material_readiness": ()}), opportunity(), NOW).state
        == "UNKNOWN"
    )


def test_missing_requirement_coverage_and_unknown_outrank_executable():
    p = project()
    items = list(p.material_readiness)
    items[0] = MaterialReadiness(kind=items[0].kind, ready=fact(False), gap_executable=fact(True))
    assert (
        assess_readiness(
            p.model_copy(update={"material_readiness": tuple(items[:-1])}), opportunity(), NOW
        ).state
        == "UNKNOWN"
    )
    assert assess_readiness(p, opportunity(materials=()), NOW).state == "UNKNOWN"
    assert match_project(p, opportunity(technologies=Fact()), NOW).comparable_score is None


def test_empty_declared_requirements_are_satisfied_without_project_facts():
    result = match_project(
        project(technology_stack=Fact(), problem=Fact()),
        opportunity(technologies=fact(()), problem_labels=fact(())),
        NOW,
    )
    assert result.comparable_score == 100


def test_duplicate_ids_opportunities_and_candidate_limit():
    match = match_project(project(), opportunity(), NOW)
    with pytest.raises(ValueError):
        select_best_project((match, match))
    with pytest.raises(ValueError):
        select_best_project(
            (match, match.model_copy(update={"project_id": "p2", "opportunity_id": "other"}))
        )
    with pytest.raises(ValueError):
        select_best_project(
            tuple(match.model_copy(update={"project_id": str(i)}) for i in range(6))
        )


@pytest.mark.parametrize(
    "bounds",
    [
        dict(min_hours="2", max_hours="1"),
        dict(min_hours=-1, max_hours=2),
        dict(min_hours=True, max_hours=2),
        dict(min_hours=1.5, max_hours=2),
    ],
)
def test_strict_ranges(bounds):
    with pytest.raises(ValidationError):
        HourRange(**bounds)


def test_strict_material_boolean_duplicates_and_revalidation():
    with pytest.raises(ValidationError):
        MaterialRequirement(kind="DEMO", required=fact("false"))
    req = opportunity().matching_requirements
    with pytest.raises(ValidationError):
        opportunity(materials=(req.materials[0], req.materials[0]))
    with pytest.raises(ValidationError):
        match_project(
            project().model_copy(update={"estimated_adaptation_hours": fact(-1)}),
            opportunity(),
            NOW,
        )
    with pytest.raises(ValidationError):
        assess_readiness(project(), opportunity(), NOW.replace(tzinfo=None))


def test_portfolio_revalidates_forged_comparable_score():
    known = match_project(project(), opportunity(), NOW)
    unknown = match_project(project(problem=Fact()), opportunity(), NOW)
    with pytest.raises(ValidationError):
        select_best_project((unknown.model_copy(update={"comparable_score": 100}),))
    with pytest.raises(ValidationError):
        select_best_project((known.model_copy(update={"comparable_score": 99}),))


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"code_provenance": fact("REUSED")}, 0),
        ({"license_intent": fact("GPL")}, 0),
        ({"code_provenance": Fact()}, None),
    ],
)
def test_code_and_license_combine_conservatively(changes, expected):
    result = match_project(project(**changes), opportunity(), NOW)
    assert next(f.rating for f in result.factor_results if f.factor == "code_license") == expected


def test_weak_match_and_explicit_nonrequirements():
    result = match_project(
        project(
            problem=fact("other"),
            audience=fact("other"),
            technology_stack=fact(()),
            available_features=fact(()),
            stage=fact("IDEA"),
            estimated_adaptation_hours=fact("11"),
        ),
        opportunity(),
        NOW,
    )
    assert (result.match_status, result.comparable_score, result.rating) == ("WEAK", 29, 1)
    optional = tuple(MaterialRequirement(kind=k, required=fact(False)) for k in MaterialKind)
    assert (
        assess_readiness(project(material_readiness=()), opportunity(materials=optional), NOW).state
        == "READY"
    )


def test_zero_maximum_still_reports_missing_adaptation():
    result = match_project(
        project(estimated_adaptation_hours=Fact()), opportunity(max_adaptation_hours=fact("0")), NOW
    )
    assert "project.estimated_adaptation_hours" in result.missing_project_facts


# --- explicitly unbounded adaptation ----------------------------------------------------
#
# An opportunity that publishes no adaptation cap is not the same as one whose cap has not
# been read yet. The first has a definite answer -- every finite adaptation satisfies an
# absent limit -- and the second does not. Collapsing them forced the whole comparable score
# to UNKNOWN whenever a real source simply had nothing to say about adaptation hours.


def adaptation_rating(match):
    return next(f.rating for f in match.factor_results if f.factor == "adaptation")


def test_an_unread_adaptation_cap_is_still_unknown():
    """The absence of a value is never read as the absence of a limit."""
    match = match_project(project(), opportunity(max_adaptation_hours=Fact()), NOW)
    assert adaptation_rating(match) is None
    assert match.comparable_score is None


def test_a_finite_adaptation_cap_is_unchanged():
    within = match_project(project(estimated_adaptation_hours=fact("4")), opportunity(), NOW)
    beyond = match_project(project(estimated_adaptation_hours=fact("40")), opportunity(), NOW)
    assert adaptation_rating(within) == 4
    assert adaptation_rating(beyond) == 0


def test_an_explicitly_unbounded_cap_is_satisfied_rather_than_unknown():
    """Stated outright: this opportunity sets no adaptation limit."""
    match = match_project(
        project(estimated_adaptation_hours=fact("400")),
        opportunity(max_adaptation_hours=Fact(), adaptation_unbounded=fact(True)),
        NOW,
    )
    assert adaptation_rating(match) == 4
    assert match.comparable_score is not None


def test_an_explicitly_bounded_declaration_still_compares_against_the_cap():
    """`adaptation_unbounded=False` is a statement, not a licence to skip the comparison."""
    beyond = match_project(
        project(estimated_adaptation_hours=fact("40")),
        opportunity(adaptation_unbounded=fact(False)),
        NOW,
    )
    assert adaptation_rating(beyond) == 0


def test_an_unbounded_cap_cannot_also_state_a_finite_limit():
    """Two contradictory answers to one question are refused at the contract boundary."""
    with pytest.raises(ValidationError):
        MatchingRequirements(
            max_adaptation_hours=fact("10"), adaptation_unbounded=fact(True)
        )


def test_an_unbounded_adaptation_cites_the_requirement_that_answered_it():
    """A matched requirement a judge reads must be the field that actually decided it."""
    match = match_project(
        project(estimated_adaptation_hours=fact("400")),
        opportunity(max_adaptation_hours=Fact(), adaptation_unbounded=fact(True)),
        NOW,
    )
    factor = next(f for f in match.factor_results if f.factor == "adaptation")
    assert factor.requirement_refs == (
        "opportunity.matching_requirements.adaptation_unbounded",
    )
    # The numeric cap holds no value here, so it must not be presented as matched.
    matched = match.matched_requirements
    assert "opportunity.matching_requirements.max_adaptation_hours" not in matched
    assert "opportunity.matching_requirements.adaptation_unbounded" in matched


def test_a_finite_adaptation_still_cites_the_numeric_cap():
    match = match_project(project(), opportunity(), NOW)
    factor = next(f for f in match.factor_results if f.factor == "adaptation")
    assert factor.requirement_refs == (
        "opportunity.matching_requirements.max_adaptation_hours",
    )


def test_the_semantic_digest_separates_an_unbounded_cap_from_an_unread_one():
    """Versioning must see this fact, or a source that newly removes its cap would persist
    as UNCHANGED and leave an outstanding approval bound to a decision that no longer holds."""
    from qualor.workspace.versioning import opportunity_semantic_digest

    unread = opportunity_semantic_digest(opportunity(max_adaptation_hours=Fact()))
    unbounded = opportunity_semantic_digest(
        opportunity(max_adaptation_hours=Fact(), adaptation_unbounded=fact(True))
    )
    bounded = opportunity_semantic_digest(
        opportunity(max_adaptation_hours=Fact(), adaptation_unbounded=fact(False))
    )
    assert len({unread, unbounded, bounded}) == 3
