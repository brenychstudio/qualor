"""Bounded model-call accounting without prompts, values, or provider payloads."""

import json
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, StringConstraints, model_validator

from qualor.domain.base import Contract
from qualor.domain.enums import Category
from qualor.domain.money import ExactDecimal

from .adapters.base import AdapterResult

MAX_PLANNED_SLOTS = 24
MAX_DISPATCHED_MODEL_CALLS = 9
MAX_RECEIPT_OUTCOMES = 40
MAX_REJECTION_CODES = 40
MAX_MODEL_COST_USD = Decimal("0.20")

CallSlot = Annotated[StrictInt, Field(ge=1, le=MAX_PLANNED_SLOTS)]
CallIndex = Annotated[StrictInt, Field(ge=1, le=MAX_DISPATCHED_MODEL_CALLS)]
Count = Annotated[StrictInt, Field(ge=0, le=MAX_RECEIPT_OUTCOMES)]
AuthorityRevision = Annotated[StrictInt, Field(ge=0)]
SourceId = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=8, max_length=80, pattern=r"^source_[A-Za-z0-9_-]+$"
    ),
]
SectionId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^section_[a-f0-9]{32}$"),
]
SafeCode = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=1, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$"
    ),
]
BoundedCost = Annotated[ExactDecimal, Field(ge=0, le=MAX_MODEL_COST_USD)]


class ModelCallReceipt(Contract):
    call_slot: CallSlot
    call_index: CallIndex | None = None
    role: Literal["PLANNING", "EXTRACTION"]
    source_id: SourceId | None = None
    section_id: SectionId | None = None
    requested_categories: Annotated[tuple[Category, ...], Field(max_length=2)] = ()
    proposal_count: Count = 0
    supported_count: Count = 0
    conditional_count: Count = 0
    ambiguous_count: Count = 0
    unknown_count: Count = 0
    unsupported_count: Count = 0
    duplicate_count: Count = 0
    rejection_codes: Annotated[tuple[SafeCode, ...], Field(max_length=MAX_REJECTION_CODES)] = ()
    authority_revision_before: AuthorityRevision
    authority_revision_after: AuthorityRevision
    execution_state: Literal["PLANNED", "DISPATCHED", "COMPLETED", "FAILED", "BUDGET_BLOCKED"]
    cost_reserved: BoundedCost | None = None
    cost_reconciled: BoundedCost | None = None

    @model_validator(mode="after")
    def lifecycle_is_consistent(self) -> Self:
        if self.role == "PLANNING":
            if (
                self.source_id is not None
                or self.section_id is not None
                or self.requested_categories
            ):
                raise ValueError("Planning receipts cannot carry extraction scope")
        elif self.source_id is None or self.section_id is None or not self.requested_categories:
            raise ValueError("Extraction receipts require bounded source, section, and categories")
        if len(set(self.requested_categories)) != len(self.requested_categories):
            raise ValueError("Receipt categories must be unique")
        if len(set(self.rejection_codes)) != len(self.rejection_codes):
            raise ValueError("Receipt rejection codes must be unique")
        partition = (
            self.supported_count
            + self.ambiguous_count
            + self.unknown_count
            + self.unsupported_count
            + self.duplicate_count
        )
        if partition != self.proposal_count:
            raise ValueError("Receipt outcome counts must partition proposals")
        if self.conditional_count > self.supported_count:
            raise ValueError("Conditional outcomes are a subset of supported outcomes")
        if self.authority_revision_after < self.authority_revision_before:
            raise ValueError("Receipt authority revision cannot move backward")
        undispatched = self.execution_state in {"PLANNED", "BUDGET_BLOCKED"}
        if undispatched and any(
            value is not None
            for value in (self.call_index, self.cost_reserved, self.cost_reconciled)
        ):
            raise ValueError("Undispatched receipts cannot report call or cost accounting")
        if self.execution_state in {"DISPATCHED", "COMPLETED", "FAILED"} and (
            self.call_index is None or self.cost_reserved is None
        ):
            raise ValueError("Dispatched receipts require call and reservation accounting")
        if self.execution_state in {"PLANNED", "DISPATCHED"} and (
            self.proposal_count or self.rejection_codes
        ):
            raise ValueError("Nonterminal receipts cannot report final outcomes")
        if self.execution_state == "BUDGET_BLOCKED" and self.cost_reconciled is not None:
            raise ValueError("Budget-blocked receipts cannot report reconciled cost")
        return self


def _outcome_key(outcome: AdapterResult) -> str:
    payload = outcome.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


class ReceiptLedger:
    """Run-owned receipt state; this observer never authorizes or refunds spend."""

    def __init__(self) -> None:
        self._receipts: list[ModelCallReceipt] = []
        self._dispatched = 0

    def plan(
        self,
        role,
        *,
        source_id=None,
        section_id=None,
        categories=(),
        authority_revision=0,
    ) -> int:
        if len(self._receipts) >= MAX_PLANNED_SLOTS:
            raise ValueError("MODEL_RECEIPT_PLAN_LIMIT")
        slot = len(self._receipts) + 1
        self._receipts.append(
            ModelCallReceipt(
                call_slot=slot,
                role=role,
                source_id=source_id,
                section_id=section_id,
                requested_categories=tuple(categories),
                authority_revision_before=authority_revision,
                authority_revision_after=authority_revision,
                execution_state="PLANNED",
            )
        )
        return slot

    def dispatch(self, slot, *, reservation: Decimal):
        current = self._current(slot)
        if current.execution_state != "PLANNED":
            raise ValueError("Receipt dispatch requires a planned slot")
        if self._dispatched >= MAX_DISPATCHED_MODEL_CALLS:
            raise ValueError("MODEL_RECEIPT_DISPATCH_LIMIT")
        self._dispatched += 1
        self._replace(
            slot,
            call_index=self._dispatched,
            cost_reserved=reservation,
            execution_state="DISPATCHED",
        )

    def complete(
        self,
        slot,
        *,
        outcomes: tuple[AdapterResult, ...],
        authority_revision: int,
        reconciled: Decimal | None,
    ):
        current = self._current(slot)
        if current.execution_state != "DISPATCHED":
            raise ValueError("Receipt is terminal or was not dispatched")
        if current.cost_reconciled is not None:
            if reconciled is not None and reconciled != current.cost_reconciled:
                raise ValueError("Receipt reconciliation cannot be rewritten")
            reconciled = current.cost_reconciled
        seen: set[str] = set()
        unique = []
        duplicates = 0
        for outcome in outcomes:
            key = _outcome_key(outcome)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
                unique.append(outcome)
        status_counts = {
            status: sum(item.normalization_status == status for item in unique)
            for status in ("SUPPORTED", "AMBIGUOUS", "UNKNOWN", "UNSUPPORTED")
        }
        rejection_codes = tuple(
            dict.fromkeys(
                code
                for item in unique
                if item.normalization_status != "SUPPORTED"
                for code in item.reason_codes
            )
        )
        if duplicates:
            rejection_codes = (*rejection_codes, "DUPLICATE_PROPOSAL")
        self._replace(
            slot,
            proposal_count=len(outcomes),
            supported_count=status_counts["SUPPORTED"],
            conditional_count=sum(
                item.normalization_status == "SUPPORTED" and item.conditional for item in unique
            ),
            ambiguous_count=status_counts["AMBIGUOUS"],
            unknown_count=status_counts["UNKNOWN"],
            unsupported_count=status_counts["UNSUPPORTED"],
            duplicate_count=duplicates,
            rejection_codes=rejection_codes,
            authority_revision_after=authority_revision,
            execution_state="COMPLETED",
            cost_reconciled=reconciled,
        )

    def reconcile(self, slot, *, reconciled: Decimal) -> None:
        """Observe successful budget reconciliation before semantic processing finishes."""

        current = self._current(slot)
        if current.execution_state != "DISPATCHED" or current.cost_reconciled is not None:
            raise ValueError("Receipt reconciliation requires one dispatched slot")
        self._replace(slot, cost_reconciled=reconciled)

    def fail(self, slot, *, code: str, budget_blocked: bool):
        current = self._current(slot)
        if current.execution_state not in {"PLANNED", "DISPATCHED"}:
            raise ValueError("Receipt is terminal")
        if budget_blocked != (current.execution_state == "PLANNED"):
            raise ValueError("Budget denial must precede dispatch")
        self._replace(
            slot,
            rejection_codes=(code,),
            execution_state="BUDGET_BLOCKED" if budget_blocked else "FAILED",
        )

    def snapshot(self) -> tuple[ModelCallReceipt, ...]:
        return tuple(self._receipts)

    def _current(self, slot: int) -> ModelCallReceipt:
        if type(slot) is not int or not 1 <= slot <= len(self._receipts):
            raise ValueError("Unknown receipt slot")
        return self._receipts[slot - 1]

    def _replace(self, slot: int, **changes) -> None:
        current = self._current(slot)
        payload = current.model_dump()
        payload.update(changes)
        self._receipts[slot - 1] = ModelCallReceipt.model_validate(payload)
