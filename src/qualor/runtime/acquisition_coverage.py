"""Deterministic acquisition progress, separate from eligibility decisions."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category

from .acquisition_plan import (
    AcquisitionPlan,
    AcquisitionPlanItem,
    AcquisitionTier,
    ConditionalActivationReason,
    PlanActivation,
    PlanOverflow,
    activate_plan_items,
    initial_plan_activations,
)
from .normalization import NormalizationStatus
from .sections import SectionIndex, SourceSection

type AttemptKey = tuple[str, str, Category]
type PlanObligationKey = tuple[str, str, Category]
type ActivatedPlanItem = tuple[AcquisitionPlanItem, tuple[Category, ...]]
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


class AttemptTier(StrEnum):
    EXPLICIT = "EXPLICIT"
    FALLBACK = "FALLBACK"


class CategoryAccountingState(StrEnum):
    PENDING = "PENDING"
    SUPPORTED = "SUPPORTED"
    EXHAUSTED_UNRESOLVED = "EXHAUSTED_UNRESOLVED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"
    OVERFLOW_UNRESOLVED = "OVERFLOW_UNRESOLVED"


class PlanItemState(StrEnum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    EXTRACTION_ATTEMPTED = "EXTRACTION_ATTEMPTED"
    ACCOUNTED = "ACCOUNTED"
    CONTEXT_UNRESOLVED = "CONTEXT_UNRESOLVED"
    OVERFLOW_UNDISPATCHED = "OVERFLOW_UNDISPATCHED"


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
    plan_id: str | None = Field(
        default=None, pattern=r"^acquisition_plan_[a-f0-9]{32}$"
    )
    item_id: str | None = Field(default=None, pattern=r"^plan_item_[a-f0-9]{32}$")
    accounting_before: CategoryAccountingState | None = None
    accounting_after: CategoryAccountingState | None = None

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
        plan_fields = (
            self.plan_id,
            self.item_id,
            self.accounting_before,
            self.accounting_after,
        )
        if any(value is not None for value in plan_fields) and any(
            value is None for value in plan_fields
        ):
            raise ValueError("TRANSITION_PLAN_SCOPE_INCOMPLETE")
        object.__setattr__(self, "source_revision", source_revision)
        object.__setattr__(self, "category", category)
        return self


class CoverageLedger:
    """Mutable ledger exposing immutable point-in-time diagnostic snapshots."""

    def __init__(
        self, index: SectionIndex, plan: AcquisitionPlan | None = None
    ) -> None:
        self._index = index
        self._plan = plan
        self._states = (
            {
                category: (
                    AcquisitionState.SECTION_AVAILABLE
                    if any(
                        self._is_relevant(section, category)
                        for section in index.sections
                    )
                    else AcquisitionState.UNSEEN
                )
                for category in Category
            }
            if plan is None
            else {category: AcquisitionState.UNSEEN for category in Category}
        )
        self._transitions: list[CoverageTransition] = []
        self._attempts: set[AttemptKey] = set()
        self._attempt_tiers: dict[AttemptKey, AttemptTier | AcquisitionTier] = {}
        self._outcomes: dict[AttemptKey, AcquisitionOutcome] = {}
        self._active_authority_revisions: dict[AttemptKey, int] = {}
        self._seen_revisions = {index.source_revision}
        self._absence_exhausted: set[tuple[str, Category]] = set()
        self._activations: list[PlanActivation] = []
        self._plan_item_states: dict[PlanObligationKey, PlanItemState] = {}
        self._overflows: list[PlanOverflow] = []
        self._accounting_states = {
            category: CategoryAccountingState.PENDING for category in Category
        }
        self._plan_items_by_id: dict[str, AcquisitionPlanItem] = {}
        if plan is not None:
            self._initialize_plan(plan)

    @property
    def transitions(self) -> tuple[CoverageTransition, ...]:
        return tuple(self._transitions)

    @property
    def attempts(self) -> frozenset[AttemptKey]:
        return frozenset(self._attempts)

    @property
    def outcomes(self) -> Mapping[AttemptKey, AcquisitionOutcome]:
        return MappingProxyType(dict(self._outcomes))

    @property
    def attempt_tiers(self) -> Mapping[AttemptKey, AttemptTier | AcquisitionTier]:
        return MappingProxyType(dict(self._attempt_tiers))

    @property
    def activations(self) -> tuple[PlanActivation, ...]:
        return tuple(self._activations)

    @property
    def plan_item_states(self) -> Mapping[PlanObligationKey, PlanItemState]:
        return MappingProxyType(dict(self._plan_item_states))

    @property
    def overflows(self) -> tuple[PlanOverflow, ...]:
        return tuple(self._overflows)

    def state(self, category: Category) -> AcquisitionState:
        return self._states[category]

    def accounting_state(self, category: Category) -> CategoryAccountingState:
        return self._accounting_states[category]

    def active_items(
        self, tier: AcquisitionTier | None = None
    ) -> tuple[ActivatedPlanItem, ...]:
        plan = self._require_plan()
        active = []
        for item in plan.items:
            if tier is not None and item.tier is not tier:
                continue
            categories = tuple(
                category
                for plan_id, item_id, category in self._plan_item_states
                if plan_id == plan.plan_id
                and item_id == item.item_id
                and self._plan_item_states[(plan_id, item_id, category)]
                is PlanItemState.ACTIVE
            )
            if categories:
                active.append((item, categories))
        return tuple(active)

    def unresolved_obligations(
        self, category: Category | None = None
    ) -> tuple[PlanObligationKey, ...]:
        self._require_plan()
        unresolved = {
            PlanItemState.ACTIVE,
            PlanItemState.EXTRACTION_ATTEMPTED,
            PlanItemState.CONTEXT_UNRESOLVED,
            PlanItemState.OVERFLOW_UNDISPATCHED,
        }
        return tuple(
            key
            for key, state in self._plan_item_states.items()
            if state in unresolved and (category is None or key[2] is category)
        )

    def reconcile_plan(self, authority_revision: int) -> tuple[PlanActivation, ...]:
        plan = self._require_plan()
        requested: list[
            tuple[ConditionalActivationReason, Category, tuple[str, ...]]
        ] = []
        for category in Category:
            mandatory = tuple(
                key
                for key in self._plan_item_states
                if key[0] == plan.plan_id
                and key[2] is category
                and self._plan_items_by_id[key[1]].tier
                is AcquisitionTier.MANDATORY_ANCHOR
            )
            if not mandatory:
                continue
            attempted_ambiguous = tuple(
                key[1]
                for key in mandatory
                if (
                    outcome := self._outcomes.get(
                        (
                            self._index.source_revision,
                            self._plan_items_by_id[key[1]].section_id,
                            category,
                        )
                    )
                )
                is not None
                and outcome.normalization_status == "AMBIGUOUS"
            )
            if attempted_ambiguous:
                requested.append(
                    (
                        ConditionalActivationReason.AMBIGUOUS_ANCHOR,
                        category,
                        attempted_ambiguous,
                    )
                )
            terminal = {
                PlanItemState.ACCOUNTED,
                PlanItemState.CONTEXT_UNRESOLVED,
                PlanItemState.OVERFLOW_UNDISPATCHED,
            }
            if all(self._plan_item_states[key] in terminal for key in mandatory):
                supported = any(
                    self._outcomes.get(
                        (
                            self._index.source_revision,
                            self._plan_items_by_id[key[1]].section_id,
                            category,
                        )
                    )
                    and self._outcomes[
                        (
                            self._index.source_revision,
                            self._plan_items_by_id[key[1]].section_id,
                            category,
                        )
                    ].supported_rule_ids
                    for key in mandatory
                )
                if not supported:
                    requested.append(
                        (
                            ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
                            category,
                            tuple(key[1] for key in mandatory),
                        )
                    )
        activations = tuple(self._activations)
        for reason, category, causes in requested:
            activations = activate_plan_items(
                plan,
                existing=activations,
                reason=reason,
                categories=(category,),
                caused_by_item_ids=causes,
                authority_revision=authority_revision,
            )
        self._apply_activations(activations, authority_revision)
        self._recompute_plan_states()
        return self.activations

    def begin_item(
        self,
        item_id: str,
        categories: tuple[Category, ...],
        authority_revision: int,
    ) -> None:
        plan = self._require_plan()
        item = self._plan_item(item_id)
        categories = self._validate_item_categories(item, categories)
        pending = []
        for category in categories:
            obligation = (plan.plan_id, item_id, category)
            if self._plan_item_states.get(obligation) is not PlanItemState.ACTIVE:
                raise ValueError("PLAN_ITEM_NOT_ACTIVE")
            key = (self._index.source_revision, item.section_id, category)
            if key in self._attempts:
                raise ValueError("DUPLICATE_SECTION_CATEGORY_ATTEMPT")
            pending.append((obligation, key, category))
        for obligation, key, category in pending:
            self._plan_item_states[obligation] = PlanItemState.EXTRACTION_ATTEMPTED
            self._attempts.add(key)
            self._attempt_tiers[key] = item.tier
            self._active_authority_revisions[key] = authority_revision
            self._record_plan_transition(
                item,
                category,
                self._states[category],
                AcquisitionState.EXTRACTION_ATTEMPTED,
                None,
                authority_revision,
                "EXTRACTION_ATTEMPT_BEGUN",
            )
        self._recompute_plan_states()

    def complete_item(
        self,
        item_id: str,
        categories: tuple[Category, ...],
        outcomes: dict[Category, AcquisitionOutcome],
        authority_revision: int,
    ) -> None:
        plan = self._require_plan()
        item = self._plan_item(item_id)
        categories = self._validate_item_categories(item, categories)
        if set(outcomes) != set(categories):
            raise ValueError("OUTCOMES_DO_NOT_MATCH_ACTIVE_ATTEMPTS")
        before_states = {category: self._states[category] for category in categories}
        for category in categories:
            obligation = (plan.plan_id, item_id, category)
            if (
                self._plan_item_states.get(obligation)
                is not PlanItemState.EXTRACTION_ATTEMPTED
            ):
                raise ValueError("ATTEMPT_NOT_ACTIVE")
            key = (self._index.source_revision, item.section_id, category)
            if self._active_authority_revisions.get(key) != authority_revision:
                raise ValueError("AUTHORITY_REVISION_MISMATCH")
        for category, outcome in outcomes.items():
            key = (self._index.source_revision, item.section_id, category)
            self._outcomes[key] = outcome
            del self._active_authority_revisions[key]
            self._plan_item_states[(plan.plan_id, item_id, category)] = (
                PlanItemState.ACCOUNTED
            )
        self.reconcile_plan(authority_revision)
        self._recompute_plan_states()
        for category, outcome in outcomes.items():
            self._record_plan_transition(
                item,
                category,
                before_states[category],
                self._states[category],
                outcome,
                authority_revision,
                outcome.reason_code,
            )

    def operational_failure_item(
        self,
        item_id: str,
        categories: tuple[Category, ...],
        reason_code: str,
    ) -> None:
        plan = self._require_plan()
        item = self._plan_item(item_id)
        categories = self._validate_item_categories(item, categories)
        for category in categories:
            obligation = (plan.plan_id, item_id, category)
            if (
                self._plan_item_states.get(obligation)
                is not PlanItemState.EXTRACTION_ATTEMPTED
            ):
                raise ValueError("ATTEMPT_NOT_ACTIVE")
            key = (self._index.source_revision, item.section_id, category)
            authority_revision = self._active_authority_revisions.pop(key)
            self._plan_item_states[obligation] = PlanItemState.ACCOUNTED
            self._record_plan_transition(
                item,
                category,
                AcquisitionState.EXTRACTION_ATTEMPTED,
                AcquisitionState.EXHAUSTED,
                None,
                authority_revision,
                reason_code,
            )
        self.reconcile_plan(0)
        self._recompute_plan_states()

    def budget_blocked_item(
        self, item_id: str, categories: tuple[Category, ...]
    ) -> None:
        plan = self._require_plan()
        item = self._plan_item(item_id)
        categories = self._validate_item_categories(item, categories)
        for category in categories:
            obligation = (plan.plan_id, item_id, category)
            key = (self._index.source_revision, item.section_id, category)
            if (
                self._plan_item_states.get(obligation)
                is not PlanItemState.EXTRACTION_ATTEMPTED
                or key not in self._active_authority_revisions
            ):
                raise ValueError("ATTEMPT_NOT_ACTIVE")
        for category in categories:
            obligation = (plan.plan_id, item_id, category)
            key = (self._index.source_revision, item.section_id, category)
            self._active_authority_revisions.pop(key)
            self._attempts.remove(key)
            self._attempt_tiers.pop(key)
            self._plan_item_states[obligation] = PlanItemState.ACTIVE
        self._recompute_plan_states()

    def mark_context_unresolved(
        self,
        item_id: str,
        categories: tuple[Category, ...],
        authority_revision: int,
    ) -> None:
        plan = self._require_plan()
        item = self._plan_item(item_id)
        categories = self._validate_item_categories(item, categories)
        for category in categories:
            obligation = (plan.plan_id, item_id, category)
            if self._plan_item_states.get(obligation) not in {
                PlanItemState.ACTIVE,
                PlanItemState.EXTRACTION_ATTEMPTED,
            }:
                raise ValueError("PLAN_ITEM_NOT_ACTIVE")
            self._plan_item_states[obligation] = PlanItemState.CONTEXT_UNRESOLVED
            self._record_plan_transition(
                item,
                category,
                self._states[category],
                AcquisitionState.EXHAUSTED,
                None,
                authority_revision,
                "CONTEXT_UNRESOLVED",
            )
        self._recompute_plan_states()

    def mark_plan_overflow(
        self, *, dispatches_used: Literal[7], authority_revision: int
    ) -> tuple[PlanOverflow, ...]:
        plan = self._require_plan()
        del authority_revision
        for item, categories in self.active_items():
            overflow = PlanOverflow(
                item_id=item.item_id,
                categories=categories,
                reason_code="EXTRACTION_CAPACITY_REACHED",
                dispatches_used=dispatches_used,
            )
            self._overflows.append(overflow)
            for category in categories:
                self._plan_item_states[(plan.plan_id, item.item_id, category)] = (
                    PlanItemState.OVERFLOW_UNDISPATCHED
                )
        self._recompute_plan_states()
        return self.overflows

    def reconcile_index_absence(self, authority_revision: int) -> None:
        """Exhaust categories whose absence is proven by the current complete index."""

        absent = tuple(
            category
            for category in Category
            if self._states[category] is AcquisitionState.UNSEEN
            and not any(self._is_relevant(section, category) for section in self._index.sections)
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
            tier = (
                AttemptTier.EXPLICIT
                if section.candidate_categories and category in section.candidate_categories
                else AttemptTier.FALLBACK
            )
            pending.append((key, category, transition, tier))
        for key, category, transition, tier in pending:
            self._attempts.add(key)
            self._attempt_tiers[key] = tier
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
            self._record_aggregate_transition(key, category, outcome, authority_revision)

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

    def budget_blocked(self, section_id: str, categories: tuple[Category, ...]) -> None:
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
            del self._attempt_tiers[key]
            self._record_transition(
                key,
                AcquisitionState.EXTRACTION_ATTEMPTED,
                self._derived_state(category),
                None,
                authority_revision,
                "BUDGET_BLOCKED_UNDISPATCHED",
            )

    def replace_index(
        self, index: SectionIndex, plan: AcquisitionPlan | None = None
    ) -> None:
        if self._plan is not None or plan is not None:
            if plan is None:
                raise ValueError("ACQUISITION_PLAN_REQUIRED")
            self._replace_plan_index(index, plan)
            return
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
            key = (index.source_revision, relevant[0].section_id, category) if relevant else None
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

    def _initialize_plan(self, plan: AcquisitionPlan) -> None:
        if (
            plan.source_id != self._index.source_id
            or plan.source_revision != self._index.source_revision
            or plan.indexer_version != self._index.indexer_version
        ):
            raise ValueError("ACQUISITION_PLAN_INDEX_MISMATCH")
        self._plan = plan
        self._plan_items_by_id = {item.item_id: item for item in plan.items}
        self._plan_item_states = {}
        for item in plan.items:
            initial_state = (
                PlanItemState.ACTIVE
                if item.tier is AcquisitionTier.MANDATORY_ANCHOR
                else PlanItemState.INACTIVE
            )
            for category in item.categories:
                self._plan_item_states[(plan.plan_id, item.item_id, category)] = (
                    initial_state
                )
        self._activations = []
        self._overflows = []
        self._apply_activations(
            initial_plan_activations(plan, authority_revision=0), 0
        )
        self._recompute_plan_states()

    def _replace_plan_index(
        self, index: SectionIndex, plan: AcquisitionPlan
    ) -> None:
        current = self._require_plan()
        if index.source_id != self._index.source_id:
            raise ValueError("SOURCE_ID_MISMATCH")
        if self._active_authority_revisions:
            raise ValueError("SOURCE_REVISION_CHANGED_DURING_ACTIVE_ATTEMPT")
        if index.source_revision == self._index.source_revision:
            if plan.plan_id != current.plan_id:
                raise ValueError("SAME_REVISION_PLAN_ID_MISMATCH")
            self._index = index
            return
        self._index = index
        self._seen_revisions.add(index.source_revision)
        self._initialize_plan(plan)

    def _require_plan(self) -> AcquisitionPlan:
        if self._plan is None:
            raise ValueError("PLAN_MODE_REQUIRED")
        return self._plan

    def _plan_item(self, item_id: str) -> AcquisitionPlanItem:
        self._require_plan()
        try:
            return self._plan_items_by_id[item_id]
        except KeyError:
            raise ValueError("PLAN_ITEM_NOT_FOUND") from None

    def _validate_item_categories(
        self, item: AcquisitionPlanItem, categories: tuple[Category, ...]
    ) -> tuple[Category, ...]:
        if not categories or len(categories) > 2 or len(set(categories)) != len(categories):
            raise ValueError("INVALID_ACQUISITION_CATEGORIES")
        if item.categories and categories != item.categories:
            raise ValueError("PLAN_ITEM_CATEGORY_MISMATCH")
        return categories

    def _apply_activations(
        self,
        activations: tuple[PlanActivation, ...],
        authority_revision: int,
    ) -> None:
        plan = self._require_plan()
        existing = {(value.item_id, value.categories) for value in self._activations}
        for activation in activations:
            key = (activation.item_id, activation.categories)
            if key in existing:
                continue
            item = self._plan_item(activation.item_id)
            if item.categories and activation.categories != item.categories:
                raise ValueError("PLAN_ACTIVATION_CATEGORY_MISMATCH")
            self._activations.append(activation)
            existing.add(key)
            for category in activation.categories:
                obligation = (plan.plan_id, item.item_id, category)
                before = self._accounting_states[category]
                self._plan_item_states[obligation] = PlanItemState.ACTIVE
                self._transitions.append(
                    CoverageTransition(
                        key=None,
                        source_revision=self._index.source_revision,
                        category=category,
                        before=self._states[category],
                        after=AcquisitionState.SECTION_AVAILABLE,
                        outcome=None,
                        authority_revision=authority_revision,
                        cause=activation.reason.value,
                        plan_id=plan.plan_id,
                        item_id=item.item_id,
                        accounting_before=before,
                        accounting_after=CategoryAccountingState.PENDING,
                    )
                )

    def _record_plan_transition(
        self,
        item: AcquisitionPlanItem,
        category: Category,
        before: AcquisitionState,
        after: AcquisitionState,
        outcome: AcquisitionOutcome | None,
        authority_revision: int,
        cause: str,
    ) -> None:
        plan = self._require_plan()
        self._transitions.append(
            CoverageTransition(
                key=(self._index.source_revision, item.section_id, category),
                before=before,
                after=after,
                outcome=outcome,
                authority_revision=authority_revision,
                cause=cause,
                plan_id=plan.plan_id,
                item_id=item.item_id,
                accounting_before=self._accounting_states[category],
                accounting_after=self._accounting_states[category],
            )
        )

    def _recompute_plan_states(self) -> None:
        plan = self._require_plan()
        terminal = {
            PlanItemState.ACCOUNTED,
            PlanItemState.CONTEXT_UNRESOLVED,
            PlanItemState.OVERFLOW_UNDISPATCHED,
        }
        for category in Category:
            obligations = tuple(
                (key, state)
                for key, state in self._plan_item_states.items()
                if key[0] == plan.plan_id
                and key[2] is category
                and state is not PlanItemState.INACTIVE
            )
            if not obligations:
                self._states[category] = AcquisitionState.UNSEEN
                self._accounting_states[category] = CategoryAccountingState.PENDING
                continue
            states = {state for _key, state in obligations}
            if PlanItemState.EXTRACTION_ATTEMPTED in states:
                self._states[category] = AcquisitionState.EXTRACTION_ATTEMPTED
                self._accounting_states[category] = CategoryAccountingState.PENDING
                continue
            if PlanItemState.ACTIVE in states:
                self._states[category] = AcquisitionState.SECTION_AVAILABLE
                self._accounting_states[category] = CategoryAccountingState.PENDING
                continue
            if PlanItemState.CONTEXT_UNRESOLVED in states:
                self._states[category] = AcquisitionState.EXHAUSTED
                self._accounting_states[category] = (
                    CategoryAccountingState.CONTEXT_UNRESOLVED
                )
                continue
            if PlanItemState.OVERFLOW_UNDISPATCHED in states:
                self._states[category] = AcquisitionState.EXHAUSTED
                self._accounting_states[category] = (
                    CategoryAccountingState.OVERFLOW_UNRESOLVED
                )
                continue
            outcomes = tuple(
                self._outcomes.get(
                    (
                        self._index.source_revision,
                        self._plan_items_by_id[key[1]].section_id,
                        category,
                    )
                )
                for key, _state in obligations
            )
            has_support = any(outcome and outcome.supported_rule_ids for outcome in outcomes)
            safe = all(
                outcome is not None
                and outcome.context_complete
                and outcome.normalization_status not in {"AMBIGUOUS", "UNKNOWN"}
                for outcome in outcomes
            ) and all(
                self._plan_items_by_id[key[1]].context_complete
                for key, _state in obligations
            )
            if all(state in terminal for _key, state in obligations) and has_support and safe:
                self._states[category] = AcquisitionState.SUPPORTED
                self._accounting_states[category] = CategoryAccountingState.SUPPORTED
            else:
                self._states[category] = AcquisitionState.EXHAUSTED
                self._accounting_states[category] = (
                    CategoryAccountingState.EXHAUSTED_UNRESOLVED
                )

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
        outcomes = tuple(self._outcomes[key] for key in relevant_keys if key in self._outcomes)
        sections_by_id = {section.section_id: section for section in self._index.sections}
        fully_interpreted = (
            len(outcomes) == len(relevant_keys)
            and all(outcome.context_complete for outcome in outcomes)
            and all(sections_by_id[key[1]].context_complete for key in relevant_keys)
            and all(
                outcome.normalization_status not in {"AMBIGUOUS", "UNKNOWN"} for outcome in outcomes
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
