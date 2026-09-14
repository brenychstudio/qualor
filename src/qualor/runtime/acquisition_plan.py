"""Immutable deterministic acquisition planning for indexed source sections."""

import hashlib
import json
from collections import defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category

from .sections import (
    ROUTING_VERSION,
    SectionIndex,
    SectionRoutingReason,
    SourceSection,
)


class AcquisitionTier(StrEnum):
    MANDATORY_ANCHOR = "MANDATORY_ANCHOR"
    CONDITIONAL_DISCOVERY = "CONDITIONAL_DISCOVERY"
    RESERVE_FALLBACK = "RESERVE_FALLBACK"


class ConditionalActivationReason(StrEnum):
    NO_SUPPORTED_ANCHOR = "NO_SUPPORTED_ANCHOR"
    AMBIGUOUS_ANCHOR = "AMBIGUOUS_ANCHOR"
    INCOMPLETE_GOVERNING_CONTEXT = "INCOMPLETE_GOVERNING_CONTEXT"
    RULE_LIKE_FALLBACK = "RULE_LIKE_FALLBACK"
    EXPLICIT_REFERENCE_REQUIRED = "EXPLICIT_REFERENCE_REQUIRED"
    GLOBAL_CONTEXT_REQUIRED = "GLOBAL_CONTEXT_REQUIRED"
    ROUTING_UNCERTAIN = "ROUTING_UNCERTAIN"


class AcquisitionRanking(Contract):
    tier_rank: Annotated[StrictInt, Field(ge=0, le=2)]
    category_rank: Annotated[StrictInt, Field(ge=0, le=8)] | None
    local_signal_rank: Annotated[StrictInt, Field(ge=0, le=3)]
    context_dependency_count: Annotated[StrictInt, Field(ge=0, le=12)]
    start_offset: Annotated[StrictInt, Field(ge=0)]


class AcquisitionPlanItem(Contract):
    item_id: str = Field(pattern=r"^plan_item_[a-f0-9]{32}$")
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    section_id: str
    categories: tuple[Category, ...]
    tier: AcquisitionTier
    context_section_ids: tuple[str, ...]
    context_complete: StrictBool
    activation_reasons: tuple[ConditionalActivationReason, ...]
    routing_reason_codes: tuple[SectionRoutingReason, ...]
    ranking: AcquisitionRanking

    @model_validator(mode="after")
    def valid_item(self) -> Self:
        if len(self.categories) > 2 or len(set(self.categories)) != len(self.categories):
            raise ValueError("PLAN_ITEM_CATEGORIES_INVALID")
        if self.categories != _ordered_categories(self.categories):
            raise ValueError("PLAN_ITEM_CATEGORY_ORDER_INVALID")
        if self.tier is AcquisitionTier.RESERVE_FALLBACK:
            if self.categories or self.activation_reasons:
                raise ValueError("RESERVE_ITEM_SHAPE_INVALID")
            if self.ranking.category_rank is not None:
                raise ValueError("RESERVE_CATEGORY_RANK_INVALID")
        else:
            if not self.categories:
                raise ValueError("ADDRESSED_ITEM_REQUIRES_CATEGORY")
            if self.ranking.category_rank != _category_rank(self.categories[0]):
                raise ValueError("PLAN_ITEM_CATEGORY_RANK_INVALID")
        if self.tier is AcquisitionTier.MANDATORY_ANCHOR and self.activation_reasons:
            raise ValueError("MANDATORY_ITEM_CANNOT_HAVE_ACTIVATION_REASONS")
        if (
            self.tier is AcquisitionTier.CONDITIONAL_DISCOVERY
            and not self.activation_reasons
        ):
            raise ValueError("CONDITIONAL_ITEM_REQUIRES_ACTIVATION_REASON")
        if len(self.context_section_ids) > 12 or len(set(self.context_section_ids)) != len(
            self.context_section_ids
        ):
            raise ValueError("PLAN_ITEM_CONTEXT_INVALID")
        if len(set(self.activation_reasons)) != len(self.activation_reasons):
            raise ValueError("PLAN_ITEM_ACTIVATION_REASONS_INVALID")
        if len(set(self.routing_reason_codes)) != len(self.routing_reason_codes):
            raise ValueError("PLAN_ITEM_ROUTING_REASONS_INVALID")
        if self.ranking.tier_rank != _tier_rank(self.tier):
            raise ValueError("PLAN_ITEM_TIER_RANK_INVALID")
        return self


class AcquisitionPlan(Contract):
    plan_id: str = Field(pattern=r"^acquisition_plan_[a-f0-9]{32}$")
    source_id: NonEmpty
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    indexer_version: NonEmpty
    routing_version: Literal["bounded-acquisition-routing-v1"] = ROUTING_VERSION
    policy_name: Literal["QUALOR_5F"] = "QUALOR_5F"
    planning_calls_reserved: Literal[2] = 2
    max_extraction_jobs: Literal[7] = 7
    items: tuple[AcquisitionPlanItem, ...]

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        if not self.items:
            raise ValueError("ACQUISITION_PLAN_EMPTY")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("DUPLICATE_PLAN_ITEM")
        if any(item.source_revision != self.source_revision for item in self.items):
            raise ValueError("PLAN_ITEM_REVISION_MISMATCH")
        pairs: set[tuple[str, Category]] = set()
        for item in self.items:
            for category in item.categories:
                pair = (item.section_id, category)
                if pair in pairs:
                    raise ValueError("DUPLICATE_SECTION_CATEGORY_PLAN_PAIR")
                pairs.add(pair)
        return self


class PlanActivation(Contract):
    item_id: str = Field(pattern=r"^plan_item_[a-f0-9]{32}$")
    categories: tuple[Category, ...]
    reason: ConditionalActivationReason
    caused_by_item_ids: tuple[str, ...]
    authority_revision: Annotated[StrictInt, Field(ge=0)]

    @model_validator(mode="after")
    def valid_activation(self) -> Self:
        if not 1 <= len(self.categories) <= 2:
            raise ValueError("PLAN_ACTIVATION_CATEGORY_COUNT_INVALID")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("PLAN_ACTIVATION_CATEGORIES_DUPLICATE")
        if self.categories != _ordered_categories(self.categories):
            raise ValueError("PLAN_ACTIVATION_CATEGORY_ORDER_INVALID")
        if len(set(self.caused_by_item_ids)) != len(self.caused_by_item_ids):
            raise ValueError("PLAN_ACTIVATION_CAUSES_DUPLICATE")
        return self


class PlanOverflow(Contract):
    item_id: str = Field(pattern=r"^plan_item_[a-f0-9]{32}$")
    categories: tuple[Category, ...]
    reason_code: Literal["EXTRACTION_CAPACITY_REACHED"]
    dispatches_used: Literal[7]

    @model_validator(mode="after")
    def valid_overflow(self) -> Self:
        if not 1 <= len(self.categories) <= 2:
            raise ValueError("PLAN_OVERFLOW_CATEGORY_COUNT_INVALID")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("PLAN_OVERFLOW_CATEGORIES_DUPLICATE")
        return self


_ACTIVATION_PRECEDENCE = (
    ConditionalActivationReason.INCOMPLETE_GOVERNING_CONTEXT,
    ConditionalActivationReason.EXPLICIT_REFERENCE_REQUIRED,
    ConditionalActivationReason.GLOBAL_CONTEXT_REQUIRED,
    ConditionalActivationReason.AMBIGUOUS_ANCHOR,
    ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
    ConditionalActivationReason.RULE_LIKE_FALLBACK,
    ConditionalActivationReason.ROUTING_UNCERTAIN,
)


def _tier_rank(tier: AcquisitionTier) -> int:
    return list(AcquisitionTier).index(tier)


def _category_rank(category: Category) -> int:
    return list(Category).index(category)


def _ordered_categories(categories: tuple[Category, ...]) -> tuple[Category, ...]:
    return tuple(sorted(categories, key=_category_rank))


def _local_mandatory(section: SourceSection, category: Category) -> bool:
    return category in section.routing.body_categories and section.routing.rule_like


def _local_signal_rank(
    section: SourceSection, category: Category, tier: AcquisitionTier
) -> int:
    if tier is AcquisitionTier.RESERVE_FALLBACK:
        return 3
    if category in section.routing.body_categories and section.routing.rule_like:
        return 0
    if category in section.routing.body_categories:
        return 1
    if category in section.routing.heading_categories and section.routing.rule_like:
        return 2
    return 3


def _activation_reasons(
    section: SourceSection,
    category: Category,
    *,
    mandatory_categories: set[Category],
) -> tuple[ConditionalActivationReason, ...]:
    reasons = set()
    if not section.context_complete:
        reasons.add(ConditionalActivationReason.INCOMPLETE_GOVERNING_CONTEXT)
    if category not in mandatory_categories:
        reasons.add(ConditionalActivationReason.NO_SUPPORTED_ANCHOR)
    if section.routing.rule_like and category in section.routing.rule_like_category_hints:
        reasons.update(
            {
                ConditionalActivationReason.RULE_LIKE_FALLBACK,
                ConditionalActivationReason.ROUTING_UNCERTAIN,
            }
        )
    if SectionRoutingReason.STRUCTURAL_REFERENCE in section.routing.reason_codes:
        reasons.add(ConditionalActivationReason.EXPLICIT_REFERENCE_REQUIRED)
    if SectionRoutingReason.GLOBAL_SCOPE in section.routing.reason_codes:
        reasons.add(ConditionalActivationReason.GLOBAL_CONTEXT_REQUIRED)
    if not reasons:
        reasons.add(ConditionalActivationReason.NO_SUPPORTED_ANCHOR)
    return tuple(reason for reason in _ACTIVATION_PRECEDENCE if reason in reasons)


def _canonical_digest(payload: object, prefix: str) -> str:
    material = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return prefix + hashlib.sha256(material).hexdigest()[:32]


def _item_payload(
    *,
    section: SourceSection,
    categories: tuple[Category, ...],
    tier: AcquisitionTier,
    activation_reasons: tuple[ConditionalActivationReason, ...],
    ranking: AcquisitionRanking,
) -> dict[str, object]:
    return {
        "source_revision": section.source_revision,
        "routing_version": section.routing.routing_version,
        "section_id": section.section_id,
        "categories": [category.value for category in categories],
        "tier": tier.value,
        "context_section_ids": list(section.context_section_ids),
        "context_complete": section.context_complete,
        "activation_reasons": [reason.value for reason in activation_reasons],
        "routing_reason_codes": [
            reason.value for reason in section.routing.reason_codes
        ],
        "ranking": ranking.model_dump(mode="json"),
    }


def _make_item(
    section: SourceSection,
    categories: tuple[Category, ...],
    tier: AcquisitionTier,
    activation_reasons: tuple[ConditionalActivationReason, ...],
) -> AcquisitionPlanItem:
    ranking = AcquisitionRanking(
        tier_rank=_tier_rank(tier),
        category_rank=_category_rank(categories[0]) if categories else None,
        local_signal_rank=(
            min(_local_signal_rank(section, category, tier) for category in categories)
            if categories
            else 3
        ),
        context_dependency_count=len(section.context_section_ids),
        start_offset=section.start_offset,
    )
    payload = _item_payload(
        section=section,
        categories=categories,
        tier=tier,
        activation_reasons=activation_reasons,
        ranking=ranking,
    )
    return AcquisitionPlanItem(
        item_id=_canonical_digest(payload, "plan_item_"),
        source_revision=section.source_revision,
        section_id=section.section_id,
        categories=categories,
        tier=tier,
        context_section_ids=section.context_section_ids,
        context_complete=section.context_complete,
        activation_reasons=activation_reasons,
        routing_reason_codes=section.routing.reason_codes,
        ranking=ranking,
    )


def _chunks(categories: tuple[Category, ...]) -> tuple[tuple[Category, ...], ...]:
    return tuple(categories[index : index + 2] for index in range(0, len(categories), 2))


def build_acquisition_plan(index: SectionIndex) -> AcquisitionPlan:
    section_ids = {section.section_id for section in index.sections}
    if not index.sections or any(
        context_id not in section_ids
        for section in index.sections
        for context_id in section.context_section_ids
    ):
        raise ValueError("SECTION_INDEX_INCOMPLETE")
    if any(section.routing.routing_version != ROUTING_VERSION for section in index.sections):
        raise ValueError("ROUTING_VERSION_MISMATCH")

    mandatory_categories = {
        category
        for section in index.sections
        for category in Category
        if _local_mandatory(section, category)
    }
    records: list[tuple[AcquisitionPlanItem, int]] = []
    depths: defaultdict[tuple[AcquisitionTier, Category], int] = defaultdict(int)
    for section in sorted(index.sections, key=lambda value: (value.start_offset, value.section_id)):
        candidates = _ordered_categories(
            tuple(
                category
                for category in Category
                if category in section.routing.body_categories
                or category in section.routing.heading_categories
                or category in section.routing.rule_like_category_hints
            )
        )
        if not candidates:
            records.append(
                (
                    _make_item(section, (), AcquisitionTier.RESERVE_FALLBACK, ()),
                    0,
                )
            )
            continue
        grouped: defaultdict[
            tuple[AcquisitionTier, tuple[ConditionalActivationReason, ...], int],
            list[Category],
        ] = defaultdict(list)
        for category in candidates:
            tier = (
                AcquisitionTier.MANDATORY_ANCHOR
                if _local_mandatory(section, category)
                else AcquisitionTier.CONDITIONAL_DISCOVERY
            )
            reasons = (
                ()
                if tier is AcquisitionTier.MANDATORY_ANCHOR
                else _activation_reasons(
                    section, category, mandatory_categories=mandatory_categories
                )
            )
            grouped[(tier, reasons, _local_signal_rank(section, category, tier))].append(
                category
            )
        for (tier, reasons, _signal), grouped_categories in grouped.items():
            for categories in _chunks(_ordered_categories(tuple(grouped_categories))):
                item = _make_item(section, categories, tier, reasons)
                breadth = max(depths[(tier, category)] for category in categories)
                for category in categories:
                    depths[(tier, category)] += 1
                records.append((item, breadth))

    records.sort(
        key=lambda record: (
            record[0].ranking.tier_rank,
            record[1],
            record[0].ranking.category_rank
            if record[0].ranking.category_rank is not None
            else len(Category),
            record[0].ranking.local_signal_rank,
            record[0].ranking.context_dependency_count,
            record[0].ranking.start_offset,
            record[0].section_id,
            record[0].item_id,
        )
    )
    items = tuple(item for item, _breadth in records)
    represented = {item.section_id for item in items}
    if represented != section_ids:
        raise ValueError("PLAN_SECTION_INVENTORY_INCOMPLETE")
    plan_payload = {
        "source_id": index.source_id,
        "source_revision": index.source_revision,
        "indexer_version": index.indexer_version,
        "routing_version": ROUTING_VERSION,
        "policy_name": "QUALOR_5F",
        "planning_calls_reserved": 2,
        "max_extraction_jobs": 7,
        "item_ids": [item.item_id for item in items],
    }
    return AcquisitionPlan(
        plan_id=_canonical_digest(plan_payload, "acquisition_plan_"),
        source_id=index.source_id,
        source_revision=index.source_revision,
        indexer_version=index.indexer_version,
        items=items,
    )


def _activation_key(activation: PlanActivation) -> tuple[str, tuple[Category, ...]]:
    return activation.item_id, activation.categories


def _activation_for(
    item: AcquisitionPlanItem,
    categories: tuple[Category, ...],
    reason: ConditionalActivationReason,
    caused_by_item_ids: tuple[str, ...],
    authority_revision: int,
) -> PlanActivation:
    return PlanActivation(
        item_id=item.item_id,
        categories=_ordered_categories(categories),
        reason=reason,
        caused_by_item_ids=caused_by_item_ids,
        authority_revision=authority_revision,
    )


def _close_context_activations(
    plan: AcquisitionPlan,
    activations: list[PlanActivation],
    *,
    authority_revision: int,
) -> None:
    by_section: defaultdict[str, list[AcquisitionPlanItem]] = defaultdict(list)
    by_id = {item.item_id: item for item in plan.items}
    for item in plan.items:
        by_section[item.section_id].append(item)
    active: dict[tuple[str, tuple[Category, ...]], PlanActivation] = {
        _activation_key(value): value for value in activations
    }
    active_items = [item for item in plan.items if item.tier is AcquisitionTier.MANDATORY_ANCHOR]
    active_items.extend(by_id[value.item_id] for value in activations)
    cursor = 0
    while cursor < len(active_items):
        causing = active_items[cursor]
        cursor += 1
        for context_id in causing.context_section_ids:
            for target in by_section[context_id]:
                if target.tier is AcquisitionTier.MANDATORY_ANCHOR:
                    continue
                if target.categories:
                    if not set(target.categories).intersection(causing.categories):
                        continue
                    categories = target.categories
                else:
                    categories = causing.categories
                if not categories:
                    continue
                if SectionRoutingReason.GLOBAL_SCOPE in target.routing_reason_codes:
                    reason = ConditionalActivationReason.GLOBAL_CONTEXT_REQUIRED
                elif SectionRoutingReason.STRUCTURAL_REFERENCE in causing.routing_reason_codes:
                    reason = ConditionalActivationReason.EXPLICIT_REFERENCE_REQUIRED
                else:
                    continue
                activation = _activation_for(
                    target,
                    categories,
                    reason,
                    (causing.item_id,),
                    authority_revision,
                )
                key = _activation_key(activation)
                if key in active:
                    continue
                active[key] = activation
                activations.append(activation)
                active_items.append(target)


def initial_plan_activations(
    plan: AcquisitionPlan, *, authority_revision: int
) -> tuple[PlanActivation, ...]:
    activations = []
    static_reasons = {
        ConditionalActivationReason.INCOMPLETE_GOVERNING_CONTEXT,
        ConditionalActivationReason.RULE_LIKE_FALLBACK,
        ConditionalActivationReason.ROUTING_UNCERTAIN,
    }
    mandatory_categories = {
        category
        for item in plan.items
        if item.tier is AcquisitionTier.MANDATORY_ANCHOR
        for category in item.categories
    }
    for item in plan.items:
        if item.tier is not AcquisitionTier.CONDITIONAL_DISCOVERY:
            continue
        eligible_static_reasons = set(static_reasons)
        if not mandatory_categories.intersection(item.categories):
            eligible_static_reasons.add(
                ConditionalActivationReason.NO_SUPPORTED_ANCHOR
            )
        reason = next(
            (
                value
                for value in _ACTIVATION_PRECEDENCE
                if value in item.activation_reasons
                and value in eligible_static_reasons
            ),
            None,
        )
        if reason is not None:
            activations.append(
                _activation_for(item, item.categories, reason, (), authority_revision)
            )
    _close_context_activations(
        plan, activations, authority_revision=authority_revision
    )
    return tuple(activations)


def activate_plan_items(
    plan: AcquisitionPlan,
    *,
    existing: tuple[PlanActivation, ...],
    reason: ConditionalActivationReason,
    categories: tuple[Category, ...],
    caused_by_item_ids: tuple[str, ...],
    authority_revision: int,
) -> tuple[PlanActivation, ...]:
    activations = list(existing)
    seen = {_activation_key(value) for value in activations}
    requested = set(categories)
    for item in plan.items:
        if (
            item.tier is AcquisitionTier.CONDITIONAL_DISCOVERY
            and reason in item.activation_reasons
            and requested.intersection(item.categories)
        ):
            activation = _activation_for(
                item,
                item.categories,
                reason,
                caused_by_item_ids,
                authority_revision,
            )
            if _activation_key(activation) not in seen:
                seen.add(_activation_key(activation))
                activations.append(activation)
    _close_context_activations(
        plan, activations, authority_revision=authority_revision
    )
    order = {item.item_id: position for position, item in enumerate(plan.items)}
    return tuple(
        sorted(
            activations,
            key=lambda value: (
                order[value.item_id],
                tuple(_category_rank(category) for category in value.categories),
            ),
        )
    )
