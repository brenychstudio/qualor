from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib.util import find_spec

import pytest
from pydantic import ValidationError

from qualor.domain.base import Fact
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.planning import HourRange
from qualor.domain.profiles import FounderProfile, ProjectProfile

NOW = datetime(2026, 9, 5, tzinfo=UTC)


@pytest.fixture
def api():
    assert find_spec("qualor.effort") is not None, "Effort policy is not implemented"
    import qualor.effort as api

    return api


def fact(value):
    return dict(value=value, provenance="USER_ASSERTED")


def metadata(id):
    return dict(
        id=id,
        schema_version="1",
        version=1,
        created_at=NOW,
        updated_at=NOW,
        provenance="USER_ASSERTED",
    )


def project(adaptation="0.3"):
    return ProjectProfile(
        **metadata("p"),
        name="Project",
        estimated_adaptation_hours=Fact() if adaptation is None else fact(adaptation),
    )


def founder(hours="20", cash="10", currency="USD"):
    return FounderProfile(
        **metadata("f"),
        available_hours=Fact() if hours is None else fact(hours),
        max_cash_commitment=Fact() if cash is None else fact(dict(amount=cash, currency=currency)),
    )


def opportunity(deadlines):
    return OpportunityRecord(
        **metadata("o"),
        organizer="Org",
        program_name="Event",
        edition="2026",
        canonical_rules_url="https://example.org",
        deadlines=deadlines,
    )


def assumptions(api, omit=None, missing=None):
    return api.EffortAssumptions(
        items=tuple(
            api.EffortItem(
                category=c,
                hours=None if c == missing else HourRange(min_hours="0.1", max_hours="0.2"),
                confidence="HIGH",
                reason="Explicit estimate",
            )
            for c in api.EffortCategory
            if c != omit
        )
    )


def test_b32_b34_exact_totals_and_repeatability(api):
    result = api.estimate_effort(project(), assumptions(api), NOW)
    assert (result.min_total, result.max_total) == (Decimal("0.9"), Decimal("1.5"))
    assert result.adaptation_range == HourRange(min_hours="0.3", max_hours="0.3")
    assert len(result.breakdown) == 6
    assert result == api.estimate_effort(project(), assumptions(api), NOW)
    assert result.evaluated_at == NOW and result.policy_version == 1


@pytest.mark.parametrize("mode", ["adaptation", "omitted", "unknown"])
def test_b33_missing_effort_hides_full_totals(api, mode):
    result = api.estimate_effort(
        project(None if mode == "adaptation" else "0.3"),
        assumptions(
            api,
            omit="DEMO" if mode == "omitted" else None,
            missing="DEMO" if mode == "unknown" else None,
        ),
        NOW,
    )
    assert result.min_total is None and result.max_total is None
    assert result.missing_information


@pytest.mark.parametrize("minimum,maximum", [("2", "1"), (True, "2"), (0.1, "2")])
def test_b32_ranges_reject_unordered_and_inexact(api, minimum, maximum):
    with pytest.raises(ValidationError):
        api.EffortItem(
            category="DEMO",
            hours=dict(min_hours=minimum, max_hours=maximum),
            confidence="HIGH",
            reason="Estimate",
        )


def test_duplicate_categories_reject(api):
    item = assumptions(api).items[0]
    with pytest.raises(ValidationError):
        api.EffortAssumptions(items=(item, item))


@pytest.mark.parametrize(
    "hours,deadline,expected",
    [
        ("1.5", timedelta(hours=2), "SUFFICIENT"),
        ("1.4", timedelta(hours=2), "INSUFFICIENT"),
        ("20", timedelta(hours=1, minutes=29, seconds=59), "INSUFFICIENT"),
        ("20", timedelta(hours=1, minutes=30), "SUFFICIENT"),
        ("20", timedelta(hours=-1), "INSUFFICIENT"),
        (None, timedelta(hours=2), "UNKNOWN"),
    ],
)
def test_capacity_conservative_max_and_exact_wall_hours(api, hours, deadline, expected):
    effort = api.estimate_effort(project(), assumptions(api), NOW)
    result = api.assess_capacity(founder(hours), effort, opportunity((NOW + deadline,)), NOW)
    assert result.state == expected


@pytest.mark.parametrize(
    "deadlines", [(), (date(2026, 9, 6),), (NOW + timedelta(days=1), date(2026, 9, 7))]
)
def test_uncertain_deadline_never_assumes_capacity(api, deadlines):
    effort = api.estimate_effort(project(), assumptions(api), NOW)
    assert api.assess_capacity(founder(), effort, opportunity(deadlines), NOW).state == "UNKNOWN"


def cost(api, kind="CASH_SPEND", amount="5", currency="USD", covered=None, accepted=None):
    return api.ParticipationCost(
        kind=kind,
        amount=None if amount is None else dict(amount=amount, currency=currency),
        covered=Fact() if covered is None else fact(covered),
        accepted=Fact() if accepted is None else fact(accepted),
        reason="Stated cost",
    )


def assess(api, items=(), complete=True, **budget):
    return api.assess_affordability(
        founder(**budget),
        api.ParticipationCosts(
            complete=Fact() if complete is None else fact(complete), items=items
        ),
        NOW,
    )


def test_cash_costs_sum_exactly_and_respect_budget(api):
    items = (cost(api, amount="5.1"), cost(api, "ENTRY_FEE", "2.2"), cost(api, "TRAVEL", "2.7"))
    result = assess(api, items)
    assert result.state == "SUFFICIENT"
    assert result.cash_required.amount == Decimal("10.0")
    assert assess(api, items, cash="9.99").state == "INSUFFICIENT"


@pytest.mark.parametrize("complete", [False, None])
def test_incomplete_cost_coverage_is_unknown(api, complete):
    assert assess(api, complete=complete).state == "UNKNOWN"


def test_unknown_amount_budget_or_currency_cannot_pass(api):
    assert assess(api, (cost(api, amount=None),)).state == "UNKNOWN"
    assert assess(api, (cost(api),), cash=None).state == "UNKNOWN"
    assert assess(api, (cost(api, currency="EUR"),)).state == "UNKNOWN"
    assert assess(api, (cost(api, currency="UAH"),), currency="EUR").state == "UNKNOWN"


def test_same_uah_cost_and_budget_need_no_currency_conversion(api):
    result = assess(api, (cost(api, amount="5.25", currency="UAH"),), currency="UAH")
    assert result.state == "SUFFICIENT"
    assert result.cash_required.currency == "UAH"
    assert result.cash_required.amount == Decimal("5.25")


def test_b22_credits_never_enlarge_cash_budget(api):
    credit = cost(api, "CLOUD_CREDIT", "1000", covered=True)
    assert assess(api, (credit, cost(api, amount="11"))).state == "INSUFFICIENT"
    assert assess(api, (credit,)).cash_required.amount == Decimal("0")
    assert assess(api, (cost(api, "CLOUD_CREDIT", covered=None),)).state == "UNKNOWN"
    assert assess(api, (cost(api, "CLOUD_CREDIT", covered=False),)).state == "INSUFFICIENT"


@pytest.mark.parametrize(
    "accepted,state", [(True, "SUFFICIENT"), (False, "INSUFFICIENT"), (None, "UNKNOWN")]
)
def test_b23_equity_requires_explicit_consent(api, accepted, state):
    result = assess(api, (cost(api, "EQUITY_REQUIREMENT", amount=None, accepted=accepted),))
    assert result.state == state
    assert result.cash_required.amount == Decimal("0")


def test_pure_boundaries_revalidate_copied_inputs_and_timestamp(api):
    bad = assumptions(api).model_copy(
        update={"items": (dict(category="DEMO", hours=None, confidence="HIGH", reason=""),)}
    )
    with pytest.raises(ValidationError):
        api.estimate_effort(project(), bad, NOW)
    with pytest.raises(ValidationError):
        api.estimate_effort(project(), assumptions(api), NOW.replace(tzinfo=None))
    bad_cost = cost(api).model_copy(update={"accepted": fact(1)})
    with pytest.raises(ValidationError):
        api.assess_affordability(
            founder(),
            api.ParticipationCosts.model_construct(complete=fact(True), items=(bad_cost,)),
            NOW,
        )


def test_capacity_rejects_forged_effort_totals(api):
    effort = api.estimate_effort(project(), assumptions(api), NOW)
    forged = effort.model_copy(update={"min_total": Decimal("0"), "max_total": Decimal("0")})
    with pytest.raises(ValidationError):
        api.assess_capacity(founder(), forged, opportunity((NOW + timedelta(days=1),)), NOW)


def test_missing_effort_never_passes_capacity(api):
    effort = api.estimate_effort(project(None), assumptions(api), NOW)
    assert (
        api.assess_capacity(founder(), effort, opportunity((NOW + timedelta(days=1),)), NOW).state
        == "UNKNOWN"
    )
