"""Deterministic, bounded execution of an immutable acquisition plan."""

import hashlib
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category

from .acquisition_coverage import CategoryAccountingState, CoverageLedger
from .acquisition_plan import AcquisitionPlan, AcquisitionPlanItem, AcquisitionTier
from .budget import BudgetSnapshot, LiveBudgetGuard
from .sections import SectionIndex

MAX_EXTRACTION_JOB_SPAN_IDS = 12

NoExtractionReason = Literal[
    "RUN_TERMINATED",
    "STEP_BOUND",
    "BUDGET_BLOCKED",
    "PLAN_EXHAUSTED",
    "CONTEXT_UNRESOLVED",
]


class ExtractionJob(Contract):
    job_id: str = Field(pattern=r"^extraction_job_[a-f0-9]{32}$")
    source_id: NonEmpty
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    section_id: str = Field(pattern=r"^section_[a-f0-9]{32}$")
    categories: Annotated[tuple[Category, ...], Field(min_length=1, max_length=2)]
    span_ids: Annotated[
        tuple[NonEmpty, ...], Field(min_length=1, max_length=MAX_EXTRACTION_JOB_SPAN_IDS)
    ]
    context_section_ids: tuple[str, ...]
    authority_revision: Annotated[StrictInt, Field(ge=0)]
    plan_id: str = Field(pattern=r"^acquisition_plan_[a-f0-9]{32}$")
    plan_item_id: str = Field(pattern=r"^plan_item_[a-f0-9]{32}$")
    tier: AcquisitionTier


class NoExtractionJob(Contract):
    reason_code: NoExtractionReason
    pivot_eligible: StrictBool


class SectionScheduler:
    """Schedule only active, finite plan obligations in their stored rank order."""

    def __init__(
        self,
        index: SectionIndex,
        plan: AcquisitionPlan,
        ledger: CoverageLedger,
        budget: LiveBudgetGuard,
    ) -> None:
        if (
            plan.source_id != index.source_id
            or plan.source_revision != index.source_revision
            or plan.indexer_version != index.indexer_version
        ):
            raise ValueError("ACQUISITION_PLAN_INDEX_MISMATCH")
        self._index = index
        self._plan = plan
        self._ledger = ledger
        self._budget = budget
        self._sections_by_id = {section.section_id: section for section in index.sections}
        # Planning calls may already have been reserved on this shared run budget.
        # Capacity is therefore the actual inference reservations made after this
        # scheduler was constructed, never logical attempts or plan-item count.
        self._initial_inference_calls = budget.snapshot().inference_calls

    def next_job(
        self,
        *,
        authority_revision: int,
        steps_remaining: int,
        terminated: bool,
    ) -> ExtractionJob | NoExtractionJob:
        if terminated:
            return NoExtractionJob(reason_code="RUN_TERMINATED", pivot_eligible=False)
        if steps_remaining <= 0:
            return NoExtractionJob(reason_code="STEP_BOUND", pivot_eligible=False)
        dispatches_used = self._extraction_dispatches_used()
        if dispatches_used == self._plan.max_extraction_jobs:
            self._ledger.mark_plan_overflow(
                dispatches_used=dispatches_used, authority_revision=authority_revision
            )
            return NoExtractionJob(reason_code="PLAN_EXHAUSTED", pivot_eligible=False)
        if not self._inference_available(self._budget.snapshot()):
            return NoExtractionJob(reason_code="BUDGET_BLOCKED", pivot_eligible=False)

        self._ledger.reconcile_plan(authority_revision)
        context_unresolved = False
        for item, categories in self._ledger.active_items():
            context = self._context_for(item)
            if context is None:
                self._ledger.mark_context_unresolved(
                    item.item_id, categories, authority_revision
                )
                context_unresolved = True
                continue
            context_section_ids, span_ids = context
            return ExtractionJob(
                job_id=self._job_id(item, categories, authority_revision),
                source_id=self._index.source_id,
                source_revision=self._index.source_revision,
                section_id=item.section_id,
                categories=categories,
                span_ids=span_ids,
                context_section_ids=context_section_ids,
                authority_revision=authority_revision,
                plan_id=self._plan.plan_id,
                plan_item_id=item.item_id,
                tier=item.tier,
            )
        return NoExtractionJob(
            reason_code=(
                "CONTEXT_UNRESOLVED"
                if context_unresolved
                or any(
                    self._ledger.accounting_state(category)
                    is CategoryAccountingState.CONTEXT_UNRESOLVED
                    for category in Category
                )
                else "PLAN_EXHAUSTED"
            ),
            pivot_eligible=False,
        )

    def begin(self, job: ExtractionJob) -> None:
        if (
            job.source_id != self._index.source_id
            or job.source_revision != self._index.source_revision
            or job.plan_id != self._plan.plan_id
            or job.section_id not in self._sections_by_id
        ):
            raise ValueError("EXTRACTION_JOB_SOURCE_MISMATCH")
        item = next((item for item in self._plan.items if item.item_id == job.plan_item_id), None)
        if item is None or item.section_id != job.section_id or item.tier is not job.tier:
            raise ValueError("EXTRACTION_JOB_PLAN_MISMATCH")
        if job.categories != item.categories:
            raise ValueError("EXTRACTION_JOB_PLAN_CATEGORIES_MISMATCH")
        if job.job_id != self._job_id(item, job.categories, job.authority_revision):
            raise ValueError("EXTRACTION_JOB_ID_MISMATCH")
        self._ledger.begin_item(item.item_id, job.categories, job.authority_revision)

    def _extraction_dispatches_used(self) -> int:
        return self._budget.snapshot().inference_calls - self._initial_inference_calls

    def _inference_available(self, snapshot: BudgetSnapshot) -> bool:
        return snapshot.inference_calls < self._budget.policy.inference_max_calls

    def _context_for(
        self, item: AcquisitionPlanItem
    ) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
        target = self._sections_by_id[item.section_id]
        pending = list(target.context_section_ids)
        required_ids: set[str] = set()
        visited = {target.section_id}
        while pending:
            section_id = pending.pop()
            if section_id in visited:
                continue
            visited.add(section_id)
            section = self._sections_by_id[section_id]
            if not section.context_complete:
                return None
            required_ids.add(section_id)
            pending.extend(section.context_section_ids)
        if not target.context_complete:
            return None
        context_sections = tuple(
            sorted(
                (self._sections_by_id[section_id] for section_id in required_ids),
                key=lambda section: (section.start_offset, section.section_id),
            )
        )
        admitted_sections = (target, *context_sections)
        if any(not section.span_ids for section in admitted_sections):
            return None
        span_ids = tuple(
            dict.fromkeys(span_id for section in admitted_sections for span_id in section.span_ids)
        )
        if not span_ids or len(span_ids) > MAX_EXTRACTION_JOB_SPAN_IDS:
            return None
        return tuple(section.section_id for section in context_sections), span_ids

    def _job_id(
        self,
        item: AcquisitionPlanItem,
        categories: tuple[Category, ...],
        authority_revision: int,
    ) -> str:
        material = "\0".join(
            (
                self._plan.plan_id,
                item.item_id,
                self._index.source_revision,
                *(category.value for category in categories),
                str(authority_revision),
            )
        ).encode()
        return "extraction_job_" + hashlib.sha256(material).hexdigest()[:32]
