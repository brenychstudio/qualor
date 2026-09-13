"""Atomic per-run reservations for controlled live calls and estimated cost."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from .model_policy import EXTRACTION_MAX_OUTPUT_TOKENS, STRANDS_MAX_OUTPUT_TOKENS

LIVE_INFERENCE_MAX_CALLS_PER_RUN = 3
LIVE_SEARCH_MAX_CALLS_PER_RUN = 5
LIVE_FETCH_MAX_DOCUMENTS_PER_RUN = 10
QUALOR_03_DEVELOPMENT_COST_CAP_USD = Decimal("2.00")
# Six observed calls plus the pending extraction, deterministic evaluation,
# and one terminal planner turn. The independent USD ceiling still wins first.
QUALOR_03B3_INFERENCE_MAX_CALLS_PER_RUN = 9
# The historical QUALOR-03B3 authorization, unchanged and still used by the
# diagnostic policy. It never gains a later authorization's higher ceiling.
QUALOR_03B3_COST_CAP_USD = Decimal("0.20")
# QUALOR-5F, owner-authorized 2026-09-14. The call ceiling is deliberately the
# same nine as QUALOR-03B3; only the USD ceiling rises, from the Task 12
# measurement of the canonical sequence (worst case USD 0.306591, no
# reconciliation assumed). This raises potential spend, not any other limit.
QUALOR_5F_INFERENCE_MAX_CALLS_PER_RUN = QUALOR_03B3_INFERENCE_MAX_CALLS_PER_RUN
QUALOR_5F_COST_CAP_USD = Decimal("0.35")


# Each authorization carries its own independent (inference call, USD) ceiling.
AUTHORIZED_ENVELOPES = MappingProxyType(
    {
        "BASELINE": (LIVE_INFERENCE_MAX_CALLS_PER_RUN, QUALOR_03_DEVELOPMENT_COST_CAP_USD),
        "QUALOR_03B3": (QUALOR_03B3_INFERENCE_MAX_CALLS_PER_RUN, QUALOR_03B3_COST_CAP_USD),
        "QUALOR_5F": (QUALOR_5F_INFERENCE_MAX_CALLS_PER_RUN, QUALOR_5F_COST_CAP_USD),
    }
)


class LiveCallKind(StrEnum):
    INFERENCE = "INFERENCE"
    SEARCH = "SEARCH"
    FETCH = "FETCH"


class BudgetLimitExceeded(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        current_cost_usd: Decimal | None = None,
        attempted_cost_usd: Decimal | None = None,
        cost_cap_usd: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.current_cost_usd = current_cost_usd
        self.attempted_cost_usd = attempted_cost_usd
        self.cost_cap_usd = cost_cap_usd

    @property
    def remaining_cost_usd(self) -> Decimal | None:
        if self.current_cost_usd is None or self.cost_cap_usd is None:
            return None
        return self.cost_cap_usd - self.current_cost_usd

    @property
    def projected_cost_usd(self) -> Decimal | None:
        if self.current_cost_usd is None or self.attempted_cost_usd is None:
            return None
        return self.current_cost_usd + self.attempted_cost_usd


@dataclass(frozen=True)
class LiveBudgetPolicy:
    inference_max_calls: int = LIVE_INFERENCE_MAX_CALLS_PER_RUN
    search_max_calls: int = LIVE_SEARCH_MAX_CALLS_PER_RUN
    fetch_max_documents: int = LIVE_FETCH_MAX_DOCUMENTS_PER_RUN
    cost_cap_usd: Decimal = QUALOR_03_DEVELOPMENT_COST_CAP_USD
    model_max_output_tokens: int = STRANDS_MAX_OUTPUT_TOKENS
    extraction_max_output_tokens: int = EXTRACTION_MAX_OUTPUT_TOKENS
    authorization: Literal["BASELINE", "QUALOR_03B3", "QUALOR_5F"] = "BASELINE"

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
        envelope = AUTHORIZED_ENVELOPES.get(self.policy.authorization)
        if envelope is None:
            raise ValueError("Unknown budget authorization")
        inference_ceiling, cost_ceiling = envelope
        # Type-check the cap before comparing it against any authorization ceiling.
        if (
            not isinstance(self.policy.cost_cap_usd, Decimal)
            or not self.policy.cost_cap_usd.is_finite()
            or self.policy.cost_cap_usd < 0
            or self.policy.cost_cap_usd > cost_ceiling
        ):
            raise ValueError(
                f"Configured cost cap exceeds the {self.policy.authorization} "
                f"hard ceiling of USD {cost_ceiling}"
            )
        ceilings = (
            (self.policy.inference_max_calls, inference_ceiling),
            (self.policy.search_max_calls, LIVE_SEARCH_MAX_CALLS_PER_RUN),
            (self.policy.fetch_max_documents, LIVE_FETCH_MAX_DOCUMENTS_PER_RUN),
        )
        if any(configured < 0 or configured > maximum for configured, maximum in ceilings):
            raise ValueError("Configured call limit exceeds a QUALOR-03 hard ceiling")
        if type(self.policy.model_max_output_tokens) is not int or not (
            64 <= self.policy.model_max_output_tokens <= 1600
        ):
            raise ValueError("Configured model output limit exceeds a QUALOR-03 hard ceiling")
        if type(self.policy.extraction_max_output_tokens) is not int or not (
            64 <= self.policy.extraction_max_output_tokens <= EXTRACTION_MAX_OUTPUT_TOKENS
        ):
            raise ValueError("Configured extraction output limit exceeds measured policy")

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
            raise BudgetLimitExceeded(
                "Development cost cap would be exceeded",
                current_cost_usd=self._reserved_cost_usd,
                attempted_cost_usd=estimated_cost_usd,
                cost_cap_usd=self.policy.cost_cap_usd,
            )
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

    def commit(self, receipt: int) -> None:
        """Mark a fixed-price reservation complete without changing its committed cost."""

        if receipt not in self._reservations:
            raise ValueError("Invalid or already completed cost reservation")
        del self._reservations[receipt]

    @property
    def open_reservation_count(self) -> int:
        return len(self._reservations)

    def calls_used(self, kind: LiveCallKind) -> int:
        return self._calls[LiveCallKind(kind)]

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            inference_calls=self._calls[LiveCallKind.INFERENCE],
            search_calls=self._calls[LiveCallKind.SEARCH],
            fetched_documents=self._calls[LiveCallKind.FETCH],
            reserved_cost_usd=self._reserved_cost_usd,
        )
