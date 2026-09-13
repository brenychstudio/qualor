"""Deterministic acquisition progress, separate from eligibility decisions."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category

from .normalization import NormalizationStatus
from .sections import SectionIndex, SourceSection

type AttemptKey = tuple[str, str, Category]
AuthorityRevision = Annotated[StrictInt, Field(ge=0)]
SafeReasonCode = Annotated[
    str,
    Field(min_length=1, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$"),
]


class AcquisitionState(StrEnum):
    UNSEEN = "UNSEEN"
    SECTION_AVAILABLE = "SECTION_AVAILABLE"
    EXTRACTION_ATTEMPTED = "EXTRACTION_ATTEMPTED"
    SUPPORTED = "SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    EXHAUSTED = "EXHAUSTED"


class AcquisitionOutcome(Contract):
    normalization_status: NormalizationStatus
    supported_rule_ids: tuple[NonEmpty, ...]
    conditional: StrictBool
    context_complete: StrictBool
    reason_code: SafeReasonCode

    @model_validator(mode="after")
    def unique_supported_rules(self) -> Self:
        if len(set(self.supported_rule_ids)) != len(self.supported_rule_ids):
            raise ValueError("DUPLICATE_SUPPORTED_RULE_ID")
        return self


class CoverageTransition(Contract):
    key: AttemptKey | None
    source_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    category: Category | None = None
    before: AcquisitionState
    after: AcquisitionState
    outcome: AcquisitionOutcome | None
    authority_revision: AuthorityRevision
    cause: SafeReasonCode | None = None

    @model_validator(mode="after")
    def source_scope_is_explicit_and_consistent(self) -> Self:
        source_revision = self.source_revision
        category = self.category
        if self.key is not None:
            if source_revision is not None and source_revision != self.key[0]:
                raise ValueError("TRANSITION_SOURCE_REVISION_MISMATCH")
            if category is not None and category is not self.key[2]:
                raise ValueError("TRANSITION_CATEGORY_MISMATCH")
            source_revision = source_revision or self.key[0]
            category = category or self.key[2]
        if source_revision is None or category is None:
            raise ValueError("TRANSITION_SOURCE_SCOPE_REQUIRED")
        object.__setattr__(self, "source_revision", source_revision)
        object.__setattr__(self, "category", category)
        return self


class CoverageLedger:
    """Mutable ledger exposing immutable point-in-time diagnostic snapshots."""

    def __init__(self, index: SectionIndex) -> None:
        self._index = index
        self._states = {
            category: (
                AcquisitionState.SECTION_AVAILABLE
                if any(self._is_relevant(section, category) for section in index.sections)
                else AcquisitionState.UNSEEN
            )
            for category in Category
        }
        self._transitions: list[CoverageTransition] = []
        self._attempts: set[AttemptKey] = set()
        self._outcomes: dict[AttemptKey, AcquisitionOutcome] = {}
        self._active_authority_revisions: dict[AttemptKey, int] = {}
        self._seen_revisions = {index.source_revision}
        self._absence_exhausted: set[tuple[str, Category]] = set()

    @property
    def transitions(self) -> tuple[CoverageTransition, ...]:
        return tuple(self._transitions)

    @property
    def attempts(self) -> frozenset[AttemptKey]:
        return frozenset(self._attempts)

    @property
    def outcomes(self) -> Mapping[AttemptKey, AcquisitionOutcome]:
        return MappingProxyType(dict(self._outcomes))

    def state(self, category: Category) -> AcquisitionState:
        return self._states[category]

    def reconcile_index_absence(self, authority_revision: int) -> None:
        """Exhaust categories whose absence is proven by the current complete index."""

        absent = tuple(
            category
            for category in Category
            if self._states[category] is AcquisitionState.UNSEEN
            and not any(
                self._is_relevant(section, category) for section in self._index.sections
            )
        )
        for category in absent:
            self._absence_exhausted.add((self._index.source_revision, category))
            self._record_transition(
                None,
                AcquisitionState.UNSEEN,
                AcquisitionState.EXHAUSTED,
                None,
                authority_revision,
                "NO_RELEVANT_SECTION_INDEXED",
                source_revision=self._index.source_revision,
                category=category,
            )

    def begin(
        self,
        section_id: str,
        categories: tuple[Category, ...],
        authority_revision: int,
    ) -> None:
        section = self._section(section_id)
        if not categories or len(set(categories)) != len(categories):
            raise ValueError("INVALID_ACQUISITION_CATEGORIES")
        pending = []
        for category in categories:
            if not self._is_relevant(section, category):
                raise ValueError("SECTION_CATEGORY_NOT_INDEXED")
            key = (self._index.source_revision, section_id, category)
            if key in self._attempts:
                raise ValueError("DUPLICATE_SECTION_CATEGORY_ATTEMPT")
            if self._states[category] is not AcquisitionState.SECTION_AVAILABLE:
                raise ValueError("CATEGORY_NOT_AVAILABLE")
            transition = CoverageTransition(
                key=key,
                before=self._states[category],
                after=AcquisitionState.EXTRACTION_ATTEMPTED,
                outcome=None,
                authority_revision=authority_revision,
                cause="EXTRACTION_ATTEMPT_BEGUN",
            )
            pending.append((key, category, transition))
        for key, category, transition in pending:
            self._attempts.add(key)
            self._active_authority_revisions[key] = authority_revision
            self._states[category] = AcquisitionState.EXTRACTION_ATTEMPTED
            self._transitions.append(transition)

    def complete(
        self,
        section_id: str,
        outcomes: dict[Category, AcquisitionOutcome],
        authority_revision: int,
    ) -> None:
        self._section(section_id)
        active = {
            key[2]
            for key in self._active_authority_revisions
            if key[:2] == (self._index.source_revision, section_id)
        }
        if set(outcomes) != active:
            raise ValueError("OUTCOMES_DO_NOT_MATCH_ACTIVE_ATTEMPTS")
        pending = []
        for category, outcome in outcomes.items():
            key = (self._index.source_revision, section_id, category)
            if self._active_authority_revisions[key] != authority_revision:
                raise ValueError("AUTHORITY_REVISION_MISMATCH")
            semantic_state = {
                "SUPPORTED": AcquisitionState.SUPPORTED,
                "AMBIGUOUS": AcquisitionState.AMBIGUOUS,
                "UNSUPPORTED": AcquisitionState.UNSUPPORTED,
                "UNKNOWN": AcquisitionState.UNSUPPORTED,
            }[outcome.normalization_status]
            pending.append((key, category, outcome, semantic_state))

        for key, category, outcome, semantic_state in pending:
            self._outcomes[key] = outcome
            del self._active_authority_revisions[key]
            if semantic_state is AcquisitionState.SUPPORTED:
                next_state = self._derived_state(category)
                self._record_transition(
                    key,
                    AcquisitionState.EXTRACTION_ATTEMPTED,
                    next_state,
                    outcome,
                    authority_revision,
                    self._derived_cause(next_state),
                )
                continue
            self._record_transition(
                key,
                AcquisitionState.EXTRACTION_ATTEMPTED,
                semantic_state,
                outcome,
                authority_revision,
                outcome.reason_code,
            )
            self._record_aggregate_transition(
                key, category, outcome, authority_revision
            )

    def operational_failure(
        self,
        section_id: str,
        categories: tuple[Category, ...],
        reason_code: str,
    ) -> None:
        self._section(section_id)
        if not categories or len(set(categories)) != len(categories):
            raise ValueError("INVALID_ACQUISITION_CATEGORIES")
        pending = []
        for category in categories:
            key = (self._index.source_revision, section_id, category)
            try:
                authority_revision = self._active_authority_revisions[key]
            except KeyError:
                raise ValueError("ATTEMPT_NOT_ACTIVE") from None
            diagnostic = AcquisitionOutcome(
                normalization_status="UNKNOWN",
                supported_rule_ids=(),
                conditional=False,
                context_complete=False,
                reason_code=reason_code,
            )
            pending.append((key, category, authority_revision, diagnostic))
        for key, category, authority_revision, diagnostic in pending:
            del self._active_authority_revisions[key]
            self._record_transition(
                key,
                AcquisitionState.EXTRACTION_ATTEMPTED,
                self._derived_state(category),
                diagnostic,
                authority_revision,
                reason_code,
            )

    def budget_blocked(
        self, section_id: str, categories: tuple[Category, ...]
    ) -> None:
        section = self._section(section_id)
        if not categories or len(set(categories)) != len(categories):
            raise ValueError("INVALID_ACQUISITION_CATEGORIES")
        for category in categories:
            if not self._is_relevant(section, category):
                raise ValueError("SECTION_CATEGORY_NOT_INDEXED")
            key = (self._index.source_revision, section_id, category)
            if key in self._attempts and key not in self._active_authority_revisions:
                raise ValueError("ATTEMPT_ALREADY_DISPATCHED")
            if key not in self._active_authority_revisions:
                raise ValueError("ATTEMPT_NOT_ACTIVE")
        for category in categories:
            key = (self._index.source_revision, section_id, category)
            authority_revision = self._active_authority_revisions.pop(key)
            self._attempts.remove(key)
            self._record_transition(
                key,
                AcquisitionState.EXTRACTION_ATTEMPTED,
                self._derived_state(category),
                None,
                authority_revision,
                "BUDGET_BLOCKED_UNDISPATCHED",
            )

    def replace_index(self, index: SectionIndex) -> None:
        if index.source_id != self._index.source_id:
            raise ValueError("SOURCE_ID_MISMATCH")
        if index.source_revision == self._index.source_revision:
            self._index = index
            return
        if self._active_authority_revisions:
            raise ValueError("SOURCE_REVISION_CHANGED_DURING_ACTIVE_ATTEMPT")
        before_states = dict(self._states)
        restored = index.source_revision in self._seen_revisions
        self._index = index
        next_states = {
            category: (
                self._derived_state(category)
                if any(self._is_relevant(section, category) for section in index.sections)
                else (
                    AcquisitionState.EXHAUSTED
                    if (index.source_revision, category) in self._absence_exhausted
                    else AcquisitionState.UNSEEN
                )
            )
            for category in Category
        }
        self._states = next_states
        cause = "SOURCE_REVISION_RESTORED" if restored else "SOURCE_REVISION_REOPENED"
        for category in Category:
            relevant = tuple(
                section for section in index.sections if self._is_relevant(section, category)
            )
            changed = before_states[category] is not next_states[category]
            if not changed and not (restored and relevant):
                continue
            key = (
                (index.source_revision, relevant[0].section_id, category)
                if relevant
                else None
            )
            self._record_transition(
                key,
                before_states[category],
                next_states[category],
                None,
                0,
                cause,
                source_revision=index.source_revision,
                category=category,
            )
        self._seen_revisions.add(index.source_revision)

    def _record_aggregate_transition(
        self,
        key: AttemptKey | None,
        category: Category,
        outcome: AcquisitionOutcome,
        authority_revision: int,
    ) -> None:
        before = self._states[category]
        after = self._derived_state(category)
        if after is not before:
            self._record_transition(
                key,
                before,
                after,
                outcome,
                authority_revision,
                self._derived_cause(after),
            )

    def _record_transition(
        self,
        key: AttemptKey | None,
        before: AcquisitionState,
        after: AcquisitionState,
        outcome: AcquisitionOutcome | None,
        authority_revision: int,
        cause: str,
        *,
        source_revision: str | None = None,
        category: Category | None = None,
    ) -> None:
        if key is not None:
            source_revision = source_revision or key[0]
            category = category or key[2]
        if source_revision is None or category is None:
            raise ValueError("TRANSITION_SOURCE_SCOPE_REQUIRED")
        self._transitions.append(
            CoverageTransition(
                key=key,
                source_revision=source_revision,
                category=category,
                before=before,
                after=after,
                outcome=outcome,
                authority_revision=authority_revision,
                cause=cause,
            )
        )
        self._states[category] = after

    def _derived_state(self, category: Category) -> AcquisitionState:
        relevant_keys = tuple(
            (self._index.source_revision, section.section_id, category)
            for section in self._index.sections
            if self._is_relevant(section, category)
        )
        if any(key not in self._attempts for key in relevant_keys):
            return AcquisitionState.SECTION_AVAILABLE
        outcomes = tuple(
            self._outcomes[key] for key in relevant_keys if key in self._outcomes
        )
        sections_by_id = {section.section_id: section for section in self._index.sections}
        fully_interpreted = (
            len(outcomes) == len(relevant_keys)
            and all(outcome.context_complete for outcome in outcomes)
            and all(sections_by_id[key[1]].context_complete for key in relevant_keys)
            and all(
                outcome.normalization_status not in {"AMBIGUOUS", "UNKNOWN"}
                for outcome in outcomes
            )
        )
        has_support = any(outcome.supported_rule_ids for outcome in outcomes)
        if fully_interpreted and has_support:
            return AcquisitionState.SUPPORTED
        return AcquisitionState.EXHAUSTED

    @staticmethod
    def _derived_cause(state: AcquisitionState) -> str:
        return {
            AcquisitionState.SECTION_AVAILABLE: "RELEVANT_SECTION_REMAINS",
            AcquisitionState.SUPPORTED: "GOVERNING_CONTEXT_SUPPORTED",
            AcquisitionState.EXHAUSTED: "RELEVANT_SECTIONS_EXHAUSTED",
        }[state]

    @staticmethod
    def _is_relevant(section: SourceSection, category: Category) -> bool:
        return not section.candidate_categories or category in section.candidate_categories

    def _section(self, section_id: str):
        try:
            return next(
                section for section in self._index.sections if section.section_id == section_id
            )
        except StopIteration:
            raise ValueError("SECTION_NOT_INDEXED") from None
