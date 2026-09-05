from datetime import UTC, datetime
from importlib.util import find_spec
from itertools import product

import pytest
from pydantic import ValidationError

NOW = datetime(2026, 9, 5, tzinfo=UTC)
NAMES = (
    "product_fit",
    "readiness",
    "time_feasibility",
    "strategic_value",
    "economic_affordability",
)


@pytest.fixture
def api():
    assert find_spec("qualor.strategy") is not None, "Strategy policy is not implemented"
    import qualor.strategy as api

    return api


def factors(api, values):
    return api.StrategyFactors(**dict(zip(NAMES, values, strict=True)))


@pytest.mark.parametrize(
    "values,expected", [((0, 0, 0, 0, 0), 0), ((4, 4, 4, 4, 4), 100), ((4, 3, 3, 4, 2), 84)]
)
def test_b14_b15_b18_weighted_endpoints_and_example(api, values, expected):
    result = api.score_strategy(factors(api, values), NOW)
    assert result.score == expected
    assert result == api.score_strategy(factors(api, values), NOW)
    assert tuple(x.weight for x in result.breakdown) == (30, 25, 20, 15, 10)
    assert result.semantics == "PRIORITIZATION_NOT_WIN_PROBABILITY"
    assert result.evaluated_at == NOW and result.policy_version == 1


@pytest.mark.parametrize("value", [-1, 5, True, False, 1.0, "2"])
def test_b16_strict_rating_bounds(api, value):
    with pytest.raises(ValidationError):
        factors(api, (value, 4, 4, 4, 4))


@pytest.mark.parametrize("index", range(5))
def test_b17_unknown_factor_hides_aggregate(api, index):
    values = [4] * 5
    values[index] = None
    result = api.score_strategy(factors(api, values), NOW)
    assert result.score is None
    assert result.missing_strategy_factors == (NAMES[index],)
    assert result.breakdown[index].rating is None
    assert result.breakdown[index].contribution is None


def test_b19_all_ratings_produce_bounded_integer_priority(api):
    for values in product(range(5), repeat=5):
        result = api.score_strategy(factors(api, values), NOW)
        assert type(result.score) is int and 0 <= result.score <= 100


def test_b20_public_output_names_are_not_probabilities(api):
    result = api.score_strategy(factors(api, (4, 3, 3, 4, 2)), NOW)
    assert {"win_probability", "success_probability", "chance"}.isdisjoint(result.model_dump())


def test_strategy_boundary_revalidates_rating_and_time(api):
    bad = factors(api, (4, 4, 4, 4, 4)).model_copy(update={"product_fit": True})
    with pytest.raises(ValidationError):
        api.score_strategy(bad, NOW)
    with pytest.raises(ValidationError):
        api.score_strategy(factors(api, (4, 4, 4, 4, 4)), NOW.replace(tzinfo=None))


def test_strategy_assessment_rejects_forged_score_and_weights(api):
    result = api.score_strategy(factors(api, (4, 3, 3, 4, 2)), NOW)
    with pytest.raises(ValidationError):
        api.StrategyAssessment.model_validate(result.model_copy(update={"score": 100}))
    forged_factor = result.breakdown[0].model_copy(update={"weight": 100})
    with pytest.raises(ValidationError):
        api.StrategyAssessment.model_validate(
            result.model_copy(update={"breakdown": (forged_factor,) + result.breakdown[1:]})
        )


def test_derive_uses_explicit_producer_states_and_normalized_goal_coverage(api):
    from qualor.domain.base import Fact
    from qualor.domain.opportunity import OpportunityRecord
    from qualor.domain.profiles import FounderProfile, ProjectProfile
    from qualor.effort import (
        EffortAssumptions,
        ParticipationCosts,
        assess_affordability,
        assess_capacity,
        estimate_effort,
    )
    from qualor.matching import assess_readiness, match_project

    metadata = dict(
        id="x",
        schema_version="1",
        version=1,
        created_at=NOW,
        updated_at=NOW,
        provenance="USER_ASSERTED",
    )
    founder = FounderProfile(
        **metadata,
        strategic_goals=dict(value=(" Learn ", "NETWORK", "learn"), provenance="USER_ASSERTED"),
    )
    opportunity = OpportunityRecord(
        **metadata,
        organizer="Org",
        program_name="Event",
        edition="2026",
        canonical_rules_url="https://example.org",
        strategic_benefits=dict(value=("LEARN",), provenance="USER_ASSERTED"),
    )
    project = ProjectProfile(**metadata, name="Project")
    readiness = assess_readiness(project, opportunity, NOW)
    match = match_project(project, opportunity, NOW)
    effort = estimate_effort(project, EffortAssumptions(items=()), NOW)
    capacity = assess_capacity(founder, effort, opportunity, NOW)
    affordability = assess_affordability(
        founder, ParticipationCosts(complete=Fact(), items=()), NOW
    )
    result = api.derive_strategy(
        founder, opportunity, match, readiness, capacity, affordability, NOW
    )
    assert tuple(i.rating for i in result.breakdown) == (None, None, None, 2, None)
    assert result.score is None
    founder = FounderProfile.model_validate(
        founder.model_copy(update={"strategic_goals": dict(value=(), provenance="USER_ASSERTED")})
    )
    result = api.derive_strategy(
        founder, opportunity, match, readiness, capacity, affordability, NOW
    )
    assert result.breakdown[3].rating == 0
    founder = FounderProfile.model_validate(founder.model_copy(update={"strategic_goals": Fact()}))
    result = api.derive_strategy(
        founder, opportunity, match, readiness, capacity, affordability, NOW
    )
    assert result.breakdown[3].rating is None


@pytest.mark.parametrize(
    "ready,time,economic,expected",
    [
        ("READY", "SUFFICIENT", "SUFFICIENT", (4, 4, 4)),
        ("GAPS_EXECUTABLE", "INSUFFICIENT", "INSUFFICIENT", (3, 0, 0)),
        ("NOT_READY", "UNKNOWN", "UNKNOWN", (0, None, None)),
        ("UNKNOWN", "SUFFICIENT", "SUFFICIENT", (None, 4, 4)),
    ],
)
def test_derive_maps_each_explicit_state(api, ready, time, economic, expected):
    from qualor.domain.opportunity import OpportunityRecord
    from qualor.domain.profiles import FounderProfile, ProjectProfile
    from qualor.effort import AffordabilityAssessment, CapacityAssessment
    from qualor.matching import assess_readiness, match_project
    from qualor.matching.model import ProjectMatch

    metadata = dict(
        id="x",
        schema_version="1",
        version=1,
        created_at=NOW,
        updated_at=NOW,
        provenance="USER_ASSERTED",
    )
    founder = FounderProfile(
        **metadata, strategic_goals=dict(value=("Learn",), provenance="USER_ASSERTED")
    )
    opportunity = OpportunityRecord(
        **metadata,
        organizer="Org",
        program_name="Event",
        edition="2026",
        canonical_rules_url="https://example.org",
        strategic_benefits=dict(value=("Learn",), provenance="USER_ASSERTED"),
    )
    project = ProjectProfile(**metadata, name="Project")
    base_match = match_project(project, opportunity, NOW)
    match = ProjectMatch.model_validate(
        base_match.model_copy(
            update={
                "factor_results": tuple(
                    f.model_copy(update={"rating": 4}) for f in base_match.factor_results
                ),
                "rating": 4,
                "comparable_score": 100,
                "match_status": "STRONG",
            }
        )
    )
    readiness = assess_readiness(project, opportunity, NOW).model_copy(update={"state": ready})
    capacity = CapacityAssessment(
        state=time,
        available_hours=None if time == "UNKNOWN" else "10",
        remaining_wall_hours="10",
        usable_hours=None if time == "UNKNOWN" else "10",
        required_hours="20" if time == "INSUFFICIENT" else "5",
        reasons=("Supplied assessment",),
        missing_information=("founder.available_hours",) if time == "UNKNOWN" else (),
        evaluated_at=NOW,
    )
    affordability = AffordabilityAssessment(
        state=economic,
        cash_required=None
        if economic == "UNKNOWN"
        else dict(amount="20" if economic == "INSUFFICIENT" else "0", currency="USD"),
        cash_budget=None if economic == "UNKNOWN" else dict(amount="10", currency="USD"),
        reasons=("Supplied assessment",),
        missing_information=("founder.max_cash_commitment",) if economic == "UNKNOWN" else (),
        evaluated_at=NOW,
    )
    result = api.derive_strategy(
        founder, opportunity, match, readiness, capacity, affordability, NOW
    )
    assert tuple(result.breakdown[i].rating for i in (1, 2, 4)) == expected
    assert result.breakdown[0].rating == 4 and result.breakdown[3].rating == 4
    if ready == "READY":
        assert result.score == 100
