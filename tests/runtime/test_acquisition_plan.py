import inspect

import pytest
from pydantic import ValidationError

from qualor.domain.enums import Category
from qualor.runtime.acquisition_plan import (
    AcquisitionPlanItem,
    AcquisitionTier,
    ConditionalActivationReason,
    PlanActivation,
    PlanOverflow,
    activate_plan_items,
    build_acquisition_plan,
    initial_plan_activations,
)
from qualor.runtime.sections import index_source
from qualor.runtime.spans import EvidenceSpanRegistry


def _index(document, text: str, *, secret: bytes = b"p" * 32):
    return index_source(document(text), EvidenceSpanRegistry(secret=secret))


def test_plan_binds_the_frozen_qualor_5f_capacity(document):
    plan = build_acquisition_plan(_index(document, "License\nAn MIT license is required."))

    assert plan.policy_name == "QUALOR_5F"
    assert plan.planning_calls_reserved == 2
    assert plan.max_extraction_jobs == 7


def test_all_sections_are_represented_without_reserve_cartesian_product(document):
    index = _index(document, "Background\nOrdinary descriptive text.\n")
    plan = build_acquisition_plan(index)
    reserve = [item for item in plan.items if item.tier is AcquisitionTier.RESERVE_FALLBACK]

    assert {item.section_id for item in plan.items} == {
        section.section_id for section in index.sections
    }
    assert len(reserve) == len(index.sections)
    assert all(item.categories == () for item in reserve)


def test_heading_only_signal_is_conditional_not_mandatory(document):
    index = _index(document, "License\nGeneral descriptive background.")
    item = next(
        item
        for item in build_acquisition_plan(index).items
        if Category.LICENSE in item.categories
    )

    assert item.tier is AcquisitionTier.CONDITIONAL_DISCOVERY


def test_local_governing_body_signal_is_mandatory(document):
    index = _index(document, "Rules\nProjects must use Widget SDK.")
    item = next(
        item
        for item in build_acquisition_plan(index).items
        if Category.REQUIRED_TECHNOLOGY in item.categories
    )

    assert item.tier is AcquisitionTier.MANDATORY_ANCHOR


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Widget SDK documentation is available.", Category.REQUIRED_TECHNOLOGY),
        ("Eligible teams participate in the event.", Category.ENTRANT_TYPE),
        ("Prize judging criteria are described below.", Category.REWARD_CONDITIONS),
    ],
)
def test_broad_discovery_without_local_governing_predicate_is_conditional(
    document, text, category
):
    index = _index(document, text)
    section = index.sections[0]
    item = next(
        item
        for item in build_acquisition_plan(index).items
        if category in item.categories
    )

    assert section.routing.rule_like
    assert category in section.routing.body_categories
    assert item.tier is AcquisitionTier.CONDITIONAL_DISCOVERY


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Projects must use Widget SDK.", Category.REQUIRED_TECHNOLOGY),
        ("Applicants may not be incorporated companies.", Category.LEGAL_ENTITY),
        ("Only residents of Spain may enter.", Category.GEOGRAPHY),
        ("Technology\n- Widget SDK integration details.", Category.REQUIRED_TECHNOLOGY),
        ("License: MIT.", Category.LICENSE),
    ],
)
def test_exact_local_governing_predicates_are_mandatory(document, text, category):
    plan = build_acquisition_plan(_index(document, text))
    item = next(item for item in plan.items if category in item.categories)

    assert item.tier is AcquisitionTier.MANDATORY_ANCHOR


def test_no_category_is_derived_from_a_sibling_body(document):
    index = _index(
        document,
        "Rules\n"
        + ("General explanation. " * 60)
        + "An MIT license is required.\n"
        + ("Neutral material. " * 60)
        + "Projects must use Widget SDK.",
    )
    license_section = next(
        section
        for section in index.sections
        if Category.LICENSE in section.routing.body_categories
    )
    items = [
        item
        for item in build_acquisition_plan(index).items
        if item.section_id == license_section.section_id
    ]

    assert all(Category.REQUIRED_TECHNOLOGY not in item.categories for item in items)


def test_plan_and_item_identity_ignore_run_scoped_span_capabilities(document):
    first = build_acquisition_plan(_index(document, "License\nMIT is required.", secret=b"a" * 32))
    second = build_acquisition_plan(_index(document, "License\nMIT is required.", secret=b"b" * 32))

    assert first.plan_id == second.plan_id
    assert [item.item_id for item in first.items] == [item.item_id for item in second.items]


def test_plan_identity_changes_with_source_revision_routing_and_context(document):
    plain = build_acquisition_plan(_index(document, "License\nMIT is required."))
    revised = build_acquisition_plan(
        index_source(
            document("License\nMIT is required.", content_hash="a" * 64),
            EvidenceSpanRegistry(secret=b"p" * 32),
        )
    )
    contextual = build_acquisition_plan(
        _index(document, "1. Rules\nConditions apply.\n1.1 License\nMIT is required.")
    )

    assert len({plain.plan_id, revised.plan_id, contextual.plan_id}) == 3


def test_plan_builder_has_no_run_clock_profile_model_or_verdict_inputs():
    assert tuple(inspect.signature(build_acquisition_plan).parameters) == ("index",)


def test_items_are_stably_ordered_mandatory_before_conditional_before_reserve(document):
    plan = build_acquisition_plan(
        _index(
            document,
            "License\nGeneral background.\n"
            "Rules\nProjects must use Widget SDK.\n"
            "Notes\nOrdinary text.",
        )
    )
    tier_values = [item.tier for item in plan.items]

    assert tier_values == sorted(tier_values, key=list(AcquisitionTier).index)
    assert build_acquisition_plan(
        _index(
            document,
            "License\nGeneral background.\n"
            "Rules\nProjects must use Widget SDK.\n"
            "Notes\nOrdinary text.",
        )
    ).items == plan.items


def test_category_coalescing_never_exceeds_two(document):
    plan = build_acquisition_plan(
        _index(document, "Eligibility\nEligible resident individuals and teams must enter.")
    )

    assert all(len(item.categories) <= 2 for item in plan.items)
    assert all(
        tuple(sorted(item.categories, key=list(Category).index)) == item.categories
        for item in plan.items
    )


def test_initial_rule_like_and_no_anchor_conditionals_activate(document):
    plan = build_acquisition_plan(
        _index(document, "License\nGeneral background.\nNotes\nCopyright terms apply.")
    )
    activations = initial_plan_activations(plan, authority_revision=0)

    assert activations
    assert all(activation.authority_revision == 0 for activation in activations)
    assert any(
        activation.reason
        in {
            ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
            ConditionalActivationReason.RULE_LIKE_FALLBACK,
            ConditionalActivationReason.ROUTING_UNCERTAIN,
        }
        for activation in activations
    )


def test_no_supported_anchor_reason_waits_while_a_mandatory_anchor_exists(document):
    plan = build_acquisition_plan(
        _index(
            document,
            "License\nGeneral background.\n"
            "Project Requirements\nAn MIT license is required.",
        )
    )
    conditional = next(
        item
        for item in plan.items
        if item.tier is AcquisitionTier.CONDITIONAL_DISCOVERY
        and Category.LICENSE in item.categories
    )

    assert all(
        activation.item_id != conditional.item_id
        for activation in initial_plan_activations(plan, authority_revision=0)
    )


def test_activation_is_idempotent_and_reaches_a_finite_fixed_point(document):
    plan = build_acquisition_plan(_index(document, "License\nGeneral background."))
    initial = initial_plan_activations(plan, authority_revision=0)
    first = activate_plan_items(
        plan,
        existing=initial,
        reason=ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
        categories=(Category.LICENSE,),
        caused_by_item_ids=(),
        authority_revision=0,
    )
    second = activate_plan_items(
        plan,
        existing=first,
        reason=ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
        categories=(Category.LICENSE,),
        caused_by_item_ids=(),
        authority_revision=0,
    )

    assert second == first
    assert len(first) <= sum(max(1, len(item.categories)) for item in plan.items)


def test_contracts_reject_invalid_tier_shapes_and_overflow_capacity(document):
    plan = build_acquisition_plan(_index(document, "License\nGeneral background."))
    item = plan.items[0]
    payload = item.model_dump()
    payload.update(tier=AcquisitionTier.RESERVE_FALLBACK, categories=[Category.LICENSE])

    with pytest.raises(ValidationError):
        AcquisitionPlanItem.model_validate(payload)
    with pytest.raises(ValidationError):
        PlanOverflow(
            item_id=item.item_id,
            categories=(Category.LICENSE,),
            reason_code="EXTRACTION_CAPACITY_REACHED",
            dispatches_used=6,
        )


def test_activation_rejects_duplicate_or_more_than_two_categories(document):
    item = build_acquisition_plan(_index(document, "License\nGeneral background.")).items[0]

    with pytest.raises(ValidationError):
        PlanActivation(
            item_id=item.item_id,
            categories=(Category.LICENSE, Category.LICENSE),
            reason=ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
            caused_by_item_ids=(),
            authority_revision=0,
        )
    with pytest.raises(ValidationError):
        PlanActivation(
            item_id=item.item_id,
            categories=(
                Category.DEADLINE,
                Category.LICENSE,
                Category.REQUIRED_TECHNOLOGY,
            ),
            reason=ConditionalActivationReason.NO_SUPPORTED_ANCHOR,
            caused_by_item_ids=(),
            authority_revision=0,
        )
