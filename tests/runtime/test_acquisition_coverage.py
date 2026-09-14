"""Plan-owned acquisition accounting is separate from semantic authority."""

import pytest

from qualor.domain.enums import Category
from qualor.runtime.acquisition_coverage import (
    AcquisitionOutcome,
    AcquisitionState,
    CategoryAccountingState,
    CoverageLedger,
    PlanItemState,
)
from qualor.runtime.acquisition_plan import AcquisitionTier, build_acquisition_plan
from qualor.runtime.sections import index_source
from qualor.runtime.spans import EvidenceSpanRegistry


def _planned(document, text):
    index = index_source(document(text), EvidenceSpanRegistry(secret=b"a" * 32))
    plan = build_acquisition_plan(index)
    return index, plan, CoverageLedger(index, plan)


def _outcome(status, *, rules=(), context_complete=True):
    return AcquisitionOutcome(
        normalization_status=status,
        supported_rule_ids=rules,
        conditional=False,
        context_complete=context_complete,
        reason_code="CONTROLLED_" + status,
    )


def _item(plan, category, tier=AcquisitionTier.MANDATORY_ANCHOR):
    return next(item for item in plan.items if item.tier is tier and category in item.categories)


def test_inactive_conditional_is_discoverable_but_not_an_unfinished_obligation(document):
    _index, plan, ledger = _planned(
        document, "License\nProjects must use an MIT license.\nLicense\nMIT details."
    )
    conditional = _item(plan, Category.LICENSE, AcquisitionTier.CONDITIONAL_DISCOVERY)

    assert (
        ledger.plan_item_states[(plan.plan_id, conditional.item_id, Category.LICENSE)]
        is PlanItemState.INACTIVE
    )
    assert conditional.item_id not in {item.item_id for item, _ in ledger.active_items()}
    assert ledger.accounting_state(Category.LICENSE) is CategoryAccountingState.PENDING


def test_reserve_section_is_not_multiplied_by_nine_categories(document):
    index, plan, ledger = _planned(document, "Ordinary background notes.")

    assert len(plan.items) == len(index.sections)
    assert all(item.categories == () for item in plan.items)
    assert ledger.unresolved_obligations() == ()
    assert all(ledger.state(category) is AcquisitionState.UNSEEN for category in Category)


def test_supported_needs_all_active_obligations_complete_context_and_authority(document):
    _index, plan, ledger = _planned(
        document,
        "License\nProjects must use an MIT license.\n"
        "License\nProjects must use Apache-2.0 license.",
    )
    mandatory = [
        item
        for item in plan.items
        if item.tier is AcquisitionTier.MANDATORY_ANCHOR and Category.LICENSE in item.categories
    ]
    assert len(mandatory) == 2
    first, second = mandatory
    ledger.begin_item(first.item_id, first.categories, 1)
    ledger.complete_item(
        first.item_id,
        first.categories,
        {Category.LICENSE: _outcome("SUPPORTED", rules=("rule_license",))},
        1,
    )
    assert ledger.state(Category.LICENSE) is AcquisitionState.SECTION_AVAILABLE
    ledger.begin_item(second.item_id, second.categories, 2)
    ledger.complete_item(
        second.item_id,
        second.categories,
        {Category.LICENSE: _outcome("SUPPORTED", rules=("rule_license_two",))},
        2,
    )
    assert ledger.state(Category.LICENSE) is AcquisitionState.SUPPORTED
    assert ledger.accounting_state(Category.LICENSE) is CategoryAccountingState.SUPPORTED


@pytest.mark.parametrize("status", ["UNKNOWN", "AMBIGUOUS", "UNSUPPORTED"])
def test_non_supported_outcomes_remain_non_supported(document, status):
    index, plan, ledger = _planned(document, "License\nProjects must use an MIT license.")
    item = _item(plan, Category.LICENSE)
    ledger.begin_item(item.item_id, item.categories, 3)
    ledger.complete_item(item.item_id, item.categories, {Category.LICENSE: _outcome(status)}, 3)

    key = (index.source_revision, item.section_id, Category.LICENSE)
    assert ledger.outcomes[key].normalization_status == status
    assert ledger.state(Category.LICENSE) is not AcquisitionState.SUPPORTED
    assert ledger.accounting_state(Category.LICENSE) is not CategoryAccountingState.SUPPORTED


def test_context_unresolved_and_overflow_remain_explicitly_unresolved(document):
    _index, plan, ledger = _planned(
        document, "License\nProjects must use an MIT license unless otherwise specified."
    )
    item = _item(plan, Category.LICENSE)
    ledger.mark_context_unresolved(item.item_id, item.categories, 4)
    assert ledger.accounting_state(Category.LICENSE) is CategoryAccountingState.CONTEXT_UNRESOLVED

    _index, plan, ledger = _planned(document, "License\nProjects must use an MIT license.")
    ledger.mark_plan_overflow(dispatches_used=7, authority_revision=17)
    assert ledger.accounting_state(Category.LICENSE) is CategoryAccountingState.OVERFLOW_UNRESOLVED
    overflow = [
        transition
        for transition in ledger.transitions
        if transition.cause == "EXTRACTION_CAPACITY_REACHED"
    ]
    assert overflow and {transition.authority_revision for transition in overflow} == {17}


def test_operational_failure_reconciles_activations_at_the_attempt_revision(document):
    _index, plan, ledger = _planned(
        document,
        "License\nProjects must use an MIT license.\nLicense\nMIT licensing details are available.",
    )
    item = _item(plan, Category.LICENSE)
    ledger.begin_item(item.item_id, item.categories, 19)
    ledger.operational_failure_item(item.item_id, item.categories, "EXTRACTION_PROVIDER_ERROR")

    activated = [
        transition for transition in ledger.transitions if transition.cause == "NO_SUPPORTED_ANCHOR"
    ]
    assert activated and 19 in {transition.authority_revision for transition in activated}


def test_revision_replacement_requires_new_plan_and_cannot_reuse_attempts(document):
    first_index, first_plan, ledger = _planned(
        document, "License\nProjects must use an MIT license."
    )
    item = _item(first_plan, Category.LICENSE)
    ledger.begin_item(item.item_id, item.categories, 0)
    ledger.complete_item(
        item.item_id, item.categories, {Category.LICENSE: _outcome("UNSUPPORTED")}, 0
    )
    second_index = index_source(
        document("License\nProjects must use an MIT license.", content_hash="b" * 64),
        EvidenceSpanRegistry(secret=b"b" * 32),
    )
    second_plan = build_acquisition_plan(second_index)

    ledger.replace_index(second_index, second_plan)

    assert all(key[0] == first_index.source_revision for key in ledger.attempts)
    assert ledger.active_items(AcquisitionTier.MANDATORY_ANCHOR)
