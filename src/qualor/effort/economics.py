"""Explicit participation costs only; credits and equity never become cash."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import StrictBool, TypeAdapter

from qualor.domain.base import Contract, Fact, NonEmpty, UtcInstant
from qualor.domain.money import Money
from qualor.domain.profiles import FounderProfile

from .policy import EFFORT_POLICY_VERSION


class CostKind(StrEnum):
    CASH_SPEND = "CASH_SPEND"
    ENTRY_FEE = "ENTRY_FEE"
    TRAVEL = "TRAVEL"
    CLOUD_CREDIT = "CLOUD_CREDIT"
    EQUITY_REQUIREMENT = "EQUITY_REQUIREMENT"


class ParticipationCost(Contract):
    kind: CostKind
    amount: Money | None
    covered: Fact[StrictBool]
    accepted: Fact[StrictBool]
    reason: NonEmpty


class ParticipationCosts(Contract):
    complete: Fact[StrictBool]
    items: tuple[ParticipationCost, ...]


class AffordabilityState(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class AffordabilityAssessment(Contract):
    state: AffordabilityState
    cash_required: Money | None
    cash_budget: Money | None
    reasons: tuple[NonEmpty, ...]
    missing_information: tuple[NonEmpty, ...]
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1


def assess_affordability(
    founder: FounderProfile, costs: ParticipationCosts, evaluated_at: datetime
) -> AffordabilityAssessment:
    founder = FounderProfile.model_validate(founder)
    costs = ParticipationCosts.model_validate(costs)
    evaluated_at = TypeAdapter(UtcInstant).validate_python(evaluated_at)
    missing, reasons = [], []
    insufficient = False
    budget = founder.max_cash_commitment.value
    if costs.complete.value is not True:
        missing.append("participation_costs.complete")
    if budget is None:
        missing.append("founder.max_cash_commitment")
    total = Decimal(0)
    cash_known = budget is not None
    for index, item in enumerate(costs.items):
        ref = f"participation_costs.items.{index}"
        if item.kind in {CostKind.CASH_SPEND, CostKind.ENTRY_FEE, CostKind.TRAVEL}:
            if item.amount is None:
                missing.append(ref + ".amount")
                cash_known = False
            elif budget is None or item.amount.currency != budget.currency:
                missing.append(ref + ".comparable_currency")
                cash_known = False
            else:
                total += item.amount.amount
        else:
            field = "covered" if item.kind == CostKind.CLOUD_CREDIT else "accepted"
            status = getattr(item, field).value
            if status is None:
                missing.append(ref + "." + field)
            elif not status:
                insufficient = True
                reasons.append(ref + "." + field + " is explicitly false.")
    required = Money(amount=total, currency=budget.currency) if cash_known else None
    if required is not None and total > budget.amount:
        insufficient = True
        reasons.append("Explicit cash costs exceed the stated cash budget.")
    state = (
        AffordabilityState.INSUFFICIENT
        if insufficient
        else (AffordabilityState.UNKNOWN if missing else AffordabilityState.SUFFICIENT)
    )
    return AffordabilityAssessment(
        state=state,
        cash_required=required,
        cash_budget=budget,
        reasons=tuple(reasons)
        or ("Cash, credit coverage and equity consent are assessed separately.",),
        missing_information=tuple(missing),
        evaluated_at=evaluated_at,
        policy_version=EFFORT_POLICY_VERSION,
    )
