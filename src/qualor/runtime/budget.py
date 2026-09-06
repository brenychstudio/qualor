"""Atomic per-run reservations for controlled live calls and estimated cost."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Literal

LIVE_INFERENCE_MAX_CALLS_PER_RUN = 3
LIVE_SEARCH_MAX_CALLS_PER_RUN = 5
LIVE_FETCH_MAX_DOCUMENTS_PER_RUN = 10
QUALOR_03_DEVELOPMENT_COST_CAP_USD = Decimal("2.00")


class LiveCallKind(StrEnum):
    INFERENCE = "INFERENCE"
    SEARCH = "SEARCH"
    FETCH = "FETCH"


class BudgetLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveBudgetPolicy:
    inference_max_calls: int = LIVE_INFERENCE_MAX_CALLS_PER_RUN
    search_max_calls: int = LIVE_SEARCH_MAX_CALLS_PER_RUN
    fetch_max_documents: int = LIVE_FETCH_MAX_DOCUMENTS_PER_RUN
    cost_cap_usd: Decimal = QUALOR_03_DEVELOPMENT_COST_CAP_USD
    authorization: Literal["BASELINE", "QUALOR_03B3"] = "BASELINE"

    def limit_for(self, kind: LiveCallKind) -> int:
        return {
            LiveCallKind.INFERENCE: self.inference_max_calls,
            LiveCallKind.SEARCH: self.search_max_calls,
            LiveCallKind.FETCH: self.fetch_max_documents,
        }[kind]


@dataclass(frozen=True)
class BudgetSnapshot:
    inference_calls: int
    search_calls: int
    fetched_documents: int
    reserved_cost_usd: Decimal


@dataclass
class LiveBudgetGuard:
    policy: LiveBudgetPolicy = field(default_factory=LiveBudgetPolicy)
    _calls: dict[LiveCallKind, int] = field(
        default_factory=lambda: dict.fromkeys(LiveCallKind, 0), init=False, repr=False
    )
    _reserved_cost_usd: Decimal = field(default=Decimal("0"), init=False, repr=False)
    _reservations: dict[int, Decimal] = field(default_factory=dict, init=False, repr=False)
    _next_receipt: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.policy.authorization not in {"BASELINE", "QUALOR_03B3"}:
            raise ValueError("Unknown budget authorization")
        b3 = self.policy.authorization == "QUALOR_03B3"
        if b3 and self.policy.cost_cap_usd > Decimal("0.20"):
            raise ValueError("QUALOR-03B3 hard ceiling is USD 0.20")
        ceilings = (
            (self.policy.inference_max_calls, 6 if b3 else LIVE_INFERENCE_MAX_CALLS_PER_RUN),
            (self.policy.search_max_calls, LIVE_SEARCH_MAX_CALLS_PER_RUN),
            (self.policy.fetch_max_documents, LIVE_FETCH_MAX_DOCUMENTS_PER_RUN),
        )
        if any(configured < 0 or configured > maximum for configured, maximum in ceilings):
            raise ValueError("Configured call limit exceeds a QUALOR-03 hard ceiling")
        if (
            not isinstance(self.policy.cost_cap_usd, Decimal)
            or self.policy.cost_cap_usd < 0
            or self.policy.cost_cap_usd > QUALOR_03_DEVELOPMENT_COST_CAP_USD
        ):
            raise ValueError("Configured cost cap exceeds a QUALOR-03 hard ceiling")

    def reserve(self, kind: LiveCallKind, *, estimated_cost_usd: Decimal = Decimal("0")) -> int:
        kind = LiveCallKind(kind)
        if not isinstance(estimated_cost_usd, Decimal):
            raise TypeError("estimated_cost_usd must be Decimal")
        if not estimated_cost_usd.is_finite() or estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd cannot be negative")
        if self._calls[kind] >= self.policy.limit_for(kind):
            raise BudgetLimitExceeded(f"{kind.value} call cap reached")
        next_cost = self._reserved_cost_usd + estimated_cost_usd
        if next_cost > self.policy.cost_cap_usd:
            raise BudgetLimitExceeded("Development cost cap would be exceeded")
        self._calls[kind] += 1
        self._reserved_cost_usd = next_cost
        self._next_receipt += 1
        self._reservations[self._next_receipt] = estimated_cost_usd
        return self._next_receipt

    def reconcile(self, receipt: int, *, actual_cost_usd: Decimal) -> None:
        reserved = self._reservations.get(receipt)
        if (
            reserved is None
            or not isinstance(actual_cost_usd, Decimal)
            or not actual_cost_usd.is_finite()
            or not 0 <= actual_cost_usd <= reserved
        ):
            raise ValueError("Invalid or already reconciled cost reservation")
        self._reserved_cost_usd -= reserved - actual_cost_usd
        del self._reservations[receipt]

    def calls_used(self, kind: LiveCallKind) -> int:
        return self._calls[LiveCallKind(kind)]

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            inference_calls=self._calls[LiveCallKind.INFERENCE],
            search_calls=self._calls[LiveCallKind.SEARCH],
            fetched_documents=self._calls[LiveCallKind.FETCH],
            reserved_cost_usd=self._reserved_cost_usd,
        )
