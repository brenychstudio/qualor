"""Deterministic, bounded scheduling of section extraction work."""

import hashlib
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category

from .acquisition_coverage import AcquisitionState, AttemptTier, CoverageLedger
from .budget import BudgetSnapshot, LiveBudgetGuard
from .sections import SectionIndex, SourceSection

MAX_EXTRACTION_JOB_SPAN_IDS = 12

NoExtractionReason = Literal[
    "RUN_TERMINATED",
    "STEP_BOUND",
    "BUDGET_BLOCKED",
    "SOURCE_EXHAUSTED",
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


class NoExtractionJob(Contract):
    reason_code: NoExtractionReason
    pivot_eligible: StrictBool


class SectionScheduler:
    """Choose one stable, unattempted section/category extraction job."""

    def __init__(
        self,
        index: SectionIndex,
        ledger: CoverageLedger,
        budget: LiveBudgetGuard,
    ) -> None:
        self._index = index
        self._ledger = ledger
        self._budget = budget
        self._sections_by_id = {section.section_id: section for section in index.sections}
        self._ordered_sections = tuple(
            sorted(index.sections, key=lambda section: (section.start_offset, section.section_id))
        )

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
        snapshot = self._budget.snapshot()
        if not self._inference_available(snapshot):
            return NoExtractionJob(reason_code="BUDGET_BLOCKED", pivot_eligible=False)
        self._ledger.reconcile_index_absence(authority_revision)

        contexts: dict[str, tuple[tuple[str, ...], tuple[str, ...]] | None] = {}
        explicit_candidates: dict[Category, tuple[SourceSection, ...]] = {}
        fallback_candidates: dict[Category, tuple[SourceSection, ...]] = {}
        context_unresolved = False
        for category in Category:
            if self._ledger.state(category) is not AcquisitionState.SECTION_AVAILABLE:
                continue
            explicit_sections, fallback_sections = self._unattempted_sections(category)
            for sections, candidates in (
                (explicit_sections, explicit_candidates),
                (fallback_sections, fallback_candidates),
            ):
                safe_sections = []
                for section in sections:
                    context = contexts.setdefault(section.section_id, self._context_for(section))
                    if context is None:
                        context_unresolved = True
                        continue
                    safe_sections.append(section)
                candidates[category] = tuple(safe_sections)
        use_explicit = any(explicit_candidates.values())
        candidates = explicit_candidates if use_explicit else fallback_candidates
        primary_categories = tuple(category for category in Category if candidates.get(category))
        selected = None
        if primary_categories:
            primary_category = min(
                primary_categories,
                key=lambda category: (
                    self._explicit_attempt_depth(category) if use_explicit else 0,
                    tuple(Category).index(category),
                ),
            )
            selected = candidates[primary_category][0]
        if selected is None:
            reason = "CONTEXT_UNRESOLVED" if context_unresolved else "SOURCE_EXHAUSTED"
            return NoExtractionJob(reason_code=reason, pivot_eligible=True)

        context = contexts[selected.section_id]
        assert context is not None
        context_section_ids, span_ids = context
        categories = tuple(
            category
            for category in Category
            if candidates.get(category)
            and candidates[category][0].section_id == selected.section_id
        )[:2]
        return ExtractionJob(
            job_id=self._job_id(selected, categories, authority_revision),
            source_id=self._index.source_id,
            source_revision=self._index.source_revision,
            section_id=selected.section_id,
            categories=categories,
            span_ids=span_ids,
            context_section_ids=context_section_ids,
            authority_revision=authority_revision,
        )

    def begin(self, job: ExtractionJob) -> None:
        if (
            job.source_id != self._index.source_id
            or job.source_revision != self._index.source_revision
            or job.section_id not in self._sections_by_id
        ):
            raise ValueError("EXTRACTION_JOB_SOURCE_MISMATCH")
        if job.job_id != self._job_id(
            self._sections_by_id[job.section_id], job.categories, job.authority_revision
        ):
            raise ValueError("EXTRACTION_JOB_ID_MISMATCH")
        self._ledger.begin(job.section_id, job.categories, job.authority_revision)

    def _inference_available(self, snapshot: BudgetSnapshot) -> bool:
        return snapshot.inference_calls < self._budget.policy.inference_max_calls

    def _unattempted_sections(
        self, category: Category
    ) -> tuple[tuple[SourceSection, ...], tuple[SourceSection, ...]]:
        attempts = self._ledger.attempts
        relevant = tuple(
            section
            for section in self._ordered_sections
            if (not section.candidate_categories or category in section.candidate_categories)
            and (self._index.source_revision, section.section_id, category) not in attempts
        )
        return (
            tuple(section for section in relevant if section.candidate_categories),
            tuple(section for section in relevant if not section.candidate_categories),
        )

    def _explicit_attempt_depth(self, category: Category) -> int:
        return sum(
            source_revision == self._index.source_revision
            and attempted_category is category
            and tier is AttemptTier.EXPLICIT
            for (
                source_revision,
                _section_id,
                attempted_category,
            ), tier in self._ledger.attempt_tiers.items()
        )

    def _context_for(self, target: SourceSection) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
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
        section: SourceSection,
        categories: tuple[Category, ...],
        authority_revision: int,
    ) -> str:
        material = "\0".join(
            (
                self._index.source_revision,
                section.section_id,
                *(category.value for category in categories),
                str(authority_revision),
            )
        ).encode()
        return "extraction_job_" + hashlib.sha256(material).hexdigest()[:32]
