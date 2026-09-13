from types import MappingProxyType

import pytest
from pydantic import ValidationError

from qualor.domain.enums import Category
from qualor.runtime.acquisition_coverage import (
    AcquisitionOutcome,
    AcquisitionState,
    CoverageLedger,
)
from qualor.runtime.live_cli import live_budget
from qualor.runtime.section_scheduler import SectionScheduler
from qualor.runtime.sections import SectionIndex, index_source
from qualor.runtime.spans import EvidenceSpanRegistry


def _index(document, text: str, *, content_hash: str | None = None):
    return index_source(
        document(text, content_hash=content_hash),
        EvidenceSpanRegistry(secret=b"a" * 32),
    )


def _outcome(
    status: str,
    *,
    rule_ids: tuple[str, ...] = (),
    conditional: bool = False,
    context_complete: bool = True,
    reason_code: str | None = None,
) -> AcquisitionOutcome:
    return AcquisitionOutcome(
        normalization_status=status,
        supported_rule_ids=rule_ids,
        conditional=conditional,
        context_complete=context_complete,
        reason_code=reason_code or f"TEST_{status}",
    )


def _sections(index, category: Category):
    return tuple(section for section in index.sections if category in section.candidate_categories)


def _replace_categories(
    index: SectionIndex, categories: dict[str, tuple[Category, ...]]
) -> SectionIndex:
    return SectionIndex(
        source_id=index.source_id,
        source_revision=index.source_revision,
        indexer_version=index.indexer_version,
        sections=tuple(
            section.model_copy(
                update={"candidate_categories": categories.get(section.section_id, ())}
            )
            for section in index.sections
        ),
    )


def test_same_revision_fallback_cannot_become_explicit_retroactively(document):
    index = _index(document, "Ordinary background notes.\n" * 30)
    section = index.sections[0]
    ledger = CoverageLedger(index)
    key = (index.source_revision, section.section_id, Category.DEADLINE)

    ledger.begin(section.section_id, (Category.DEADLINE,), 0)
    ledger.operational_failure(section.section_id, (Category.DEADLINE,), "PROVIDER_ERROR")
    reclassified = _replace_categories(index, {section.section_id: (Category.DEADLINE,)})
    ledger.replace_index(reclassified)
    scheduler = SectionScheduler(reclassified, ledger, live_budget())

    assert ledger.attempt_tiers[key].value == "FALLBACK"
    assert scheduler._explicit_attempt_depth(Category.DEADLINE) == 0


def test_explicit_and_fallback_tiers_are_recorded_at_begin(document):
    explicit_index = _index(document, "License\nMIT is required.")
    explicit_section = _sections(explicit_index, Category.LICENSE)[0]
    explicit_ledger = CoverageLedger(explicit_index)
    explicit_ledger.begin(explicit_section.section_id, (Category.LICENSE,), 0)

    fallback_index = _index(document, "Ordinary background notes.\n" * 30)
    fallback_section = fallback_index.sections[0]
    fallback_ledger = CoverageLedger(fallback_index)
    fallback_ledger.begin(fallback_section.section_id, (Category.LICENSE,), 0)

    assert (
        explicit_ledger.attempt_tiers[
            (explicit_index.source_revision, explicit_section.section_id, Category.LICENSE)
        ].value
        == "EXPLICIT"
    )
    assert (
        fallback_ledger.attempt_tiers[
            (fallback_index.source_revision, fallback_section.section_id, Category.LICENSE)
        ].value
        == "FALLBACK"
    )


def test_explicit_tier_cannot_become_fallback_after_same_revision_refresh(document):
    index = _index(document, "License\nMIT is required.")
    section = _sections(index, Category.LICENSE)[0]
    ledger = CoverageLedger(index)
    key = (index.source_revision, section.section_id, Category.LICENSE)
    ledger.begin(section.section_id, (Category.LICENSE,), 0)
    ledger.complete(section.section_id, {Category.LICENSE: _outcome("UNKNOWN")}, 0)

    ledger.replace_index(_replace_categories(index, {section.section_id: ()}))

    assert ledger.attempt_tiers[key].value == "EXPLICIT"


def test_budget_blocked_unwinds_attempt_tier_provenance(document):
    index = _index(document, "License\nMIT is required.")
    section = _sections(index, Category.LICENSE)[0]
    ledger = CoverageLedger(index)
    key = (index.source_revision, section.section_id, Category.LICENSE)
    ledger.begin(section.section_id, (Category.LICENSE,), 0)

    ledger.budget_blocked(section.section_id, (Category.LICENSE,))

    assert key not in ledger.attempts
    assert key not in ledger.attempt_tiers


def test_attempt_tier_history_is_revision_scoped_and_aba_stable(document):
    first_index = _index(document, "License\nMIT is required.")
    first_section = _sections(first_index, Category.LICENSE)[0]
    ledger = CoverageLedger(first_index)
    first_key = (first_index.source_revision, first_section.section_id, Category.LICENSE)
    ledger.begin(first_section.section_id, (Category.LICENSE,), 0)
    ledger.operational_failure(first_section.section_id, (Category.LICENSE,), "PROVIDER_ERROR")

    second_index = _index(
        document,
        "Ordinary background notes.\n" * 30,
        content_hash="b" * 64,
    )
    second_section = second_index.sections[0]
    second_key = (second_index.source_revision, second_section.section_id, Category.LICENSE)
    ledger.replace_index(second_index)
    ledger.begin(second_section.section_id, (Category.LICENSE,), 1)
    ledger.operational_failure(second_section.section_id, (Category.LICENSE,), "PROVIDER_ERROR")
    ledger.replace_index(first_index)

    assert ledger.attempt_tiers[first_key].value == "EXPLICIT"
    assert ledger.attempt_tiers[second_key].value == "FALLBACK"
    assert all(
        key[0] in {first_index.source_revision, second_index.source_revision}
        for key in ledger.attempt_tiers
    )


def test_attempt_tier_snapshot_is_read_only(document):
    index = _index(document, "License\nMIT is required.")
    section = _sections(index, Category.LICENSE)[0]
    ledger = CoverageLedger(index)
    key = (index.source_revision, section.section_id, Category.LICENSE)
    ledger.begin(section.section_id, (Category.LICENSE,), 0)

    snapshot = ledger.attempt_tiers
    with pytest.raises(TypeError):
        snapshot[key] = "FALLBACK"
    assert ledger.attempt_tiers[key].value == "EXPLICIT"


def test_spec_states_and_ambiguous_unsupported_transitions(document):
    index = _index(
        document,
        "Geography\nResidents of Spain may enter.\nResidency\nLocal residence rules may apply.",
    )
    first, second = _sections(index, Category.GEOGRAPHY)
    ledger = CoverageLedger(index)

    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.SECTION_AVAILABLE
    assert ledger.state(Category.LICENSE) is AcquisitionState.UNSEEN

    ledger.begin(first.section_id, (Category.GEOGRAPHY,), 4)
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.EXTRACTION_ATTEMPTED
    ledger.complete(
        first.section_id,
        {Category.GEOGRAPHY: _outcome("AMBIGUOUS")},
        4,
    )
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.SECTION_AVAILABLE

    ledger.begin(second.section_id, (Category.GEOGRAPHY,), 5)
    ledger.complete(
        second.section_id,
        {Category.GEOGRAPHY: _outcome("UNSUPPORTED")},
        5,
    )

    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.EXHAUSTED
    assert [transition.after for transition in ledger.transitions] == [
        AcquisitionState.EXTRACTION_ATTEMPTED,
        AcquisitionState.AMBIGUOUS,
        AcquisitionState.SECTION_AVAILABLE,
        AcquisitionState.EXTRACTION_ATTEMPTED,
        AcquisitionState.UNSUPPORTED,
        AcquisitionState.EXHAUSTED,
    ]
    assert [transition.authority_revision for transition in ledger.transitions] == [
        4,
        4,
        4,
        5,
        5,
        5,
    ]


def test_three_ambiguous_outcomes_are_not_operational_failures(document):
    index = _index(
        document,
        "Geography\nResidents may enter.\n"
        "Residency\nLocal law may apply.\n"
        "Eligibility\nGeographic restrictions are unclear.",
    )
    sections = _sections(index, Category.GEOGRAPHY)
    ledger = CoverageLedger(index)

    for authority_revision, section in enumerate(sections, start=1):
        ledger.begin(section.section_id, (Category.GEOGRAPHY,), authority_revision)
        ledger.complete(
            section.section_id,
            {Category.GEOGRAPHY: _outcome("AMBIGUOUS", reason_code="SOURCE_LANGUAGE_AMBIGUOUS")},
            authority_revision,
        )

    assert len(sections) == 3
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.EXHAUSTED
    assert len(ledger.outcomes) == 3
    assert all(outcome.normalization_status == "AMBIGUOUS" for outcome in ledger.outcomes.values())
    assert (
        sum(transition.after is AcquisitionState.AMBIGUOUS for transition in ledger.transitions)
        == 3
    )


def test_partial_supported_rule_ids_survive_category_exhaustion(document):
    index = _index(
        document,
        "Geography\nResidents of listed countries may enter.\n"
        "Eligibility\nEligibility also depends on local law.",
    )
    first, second = _sections(index, Category.GEOGRAPHY)
    ledger = CoverageLedger(index)

    ledger.begin(first.section_id, (Category.GEOGRAPHY,), 0)
    ledger.complete(
        first.section_id,
        {Category.GEOGRAPHY: _outcome("SUPPORTED", rule_ids=("rule_geography_residence",))},
        0,
    )
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.SECTION_AVAILABLE

    ledger.begin(second.section_id, (Category.GEOGRAPHY,), 0)
    ledger.complete(
        second.section_id,
        {Category.GEOGRAPHY: _outcome("UNKNOWN", reason_code="SOURCE_UNRESOLVED")},
        0,
    )

    first_key = (index.source_revision, first.section_id, Category.GEOGRAPHY)
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.EXHAUSTED
    assert ledger.outcomes[first_key].supported_rule_ids == ("rule_geography_residence",)


def test_unknown_survives_exhaustion(document):
    index = _index(document, "Geography\nEligibility depends on local law.")
    ledger = CoverageLedger(index)
    section = next(
        section for section in index.sections if Category.GEOGRAPHY in section.candidate_categories
    )
    ledger.begin(section.section_id, (Category.GEOGRAPHY,), 0)
    result = AcquisitionOutcome(
        normalization_status="UNKNOWN",
        supported_rule_ids=(),
        conditional=False,
        context_complete=True,
        reason_code="SOURCE_UNRESOLVED",
    )
    ledger.complete(section.section_id, {Category.GEOGRAPHY: result}, 0)

    key = (index.source_revision, section.section_id, Category.GEOGRAPHY)
    assert ledger.outcomes[key].normalization_status == "UNKNOWN"
    assert ledger.state(Category.GEOGRAPHY).value != "PASS"
    assert [transition.after for transition in ledger.transitions[-2:]] == [
        AcquisitionState.UNSUPPORTED,
        AcquisitionState.EXHAUSTED,
    ]


def test_new_source_revision_reopens_but_same_revision_does_not(document):
    text = "License\nAn MIT license is required."
    index = _index(document, text)
    section = _sections(index, Category.LICENSE)[0]
    ledger = CoverageLedger(index)
    ledger.begin(section.section_id, (Category.LICENSE,), 0)
    ledger.complete(
        section.section_id,
        {Category.LICENSE: _outcome("UNSUPPORTED")},
        0,
    )
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED
    transition_snapshot = ledger.transitions

    regenerated = index_source(document(text), EvidenceSpanRegistry(secret=b"b" * 32))
    ledger.replace_index(regenerated)
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED
    with pytest.raises(ValueError, match="DUPLICATE_SECTION_CATEGORY_ATTEMPT"):
        ledger.begin(section.section_id, (Category.LICENSE,), 1)

    revised = _index(document, text, content_hash="b" * 64)
    revised_section = _sections(revised, Category.LICENSE)[0]
    ledger.replace_index(revised)
    assert ledger.state(Category.LICENSE) is AcquisitionState.SECTION_AVAILABLE
    assert ledger.transitions[-1].key == (
        revised.source_revision,
        revised_section.section_id,
        Category.LICENSE,
    )
    assert ledger.transitions[-1].before is AcquisitionState.EXHAUSTED
    assert ledger.transitions[-1].after is AcquisitionState.SECTION_AVAILABLE
    assert ledger.transitions[-1].cause == "SOURCE_REVISION_REOPENED"
    assert ledger.transitions[-1].authority_revision == 0
    assert ledger.transitions[: len(transition_snapshot)] == transition_snapshot
    ledger.begin(revised_section.section_id, (Category.LICENSE,), 1)
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXTRACTION_ATTEMPTED
    ledger.complete(
        revised_section.section_id,
        {Category.LICENSE: _outcome("UNSUPPORTED")},
        1,
    )

    ledger.replace_index(regenerated)
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED
    assert ledger.transitions[-1].key == (
        regenerated.source_revision,
        section.section_id,
        Category.LICENSE,
    )
    assert ledger.transitions[-1].before is AcquisitionState.EXHAUSTED
    assert ledger.transitions[-1].after is AcquisitionState.EXHAUSTED
    assert ledger.transitions[-1].cause == "SOURCE_REVISION_RESTORED"
    with pytest.raises(ValueError, match="DUPLICATE_SECTION_CATEGORY_ATTEMPT"):
        ledger.begin(section.section_id, (Category.LICENSE,), 2)
    assert len(ledger.attempts) == 2


def test_unclassified_sections_are_fallbacks_through_category_exhaustion(document):
    index = _index(document, "Ordinary background notes.\n" * 50)
    assert len(index.sections) > 1
    assert all(section.candidate_categories == () for section in index.sections)
    ledger = CoverageLedger(index)

    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.SECTION_AVAILABLE
    for position, section in enumerate(index.sections):
        ledger.begin(section.section_id, (Category.GEOGRAPHY,), position)
        ledger.complete(
            section.section_id,
            {Category.GEOGRAPHY: _outcome("UNSUPPORTED")},
            position,
        )
        expected = (
            AcquisitionState.EXHAUSTED
            if position == len(index.sections) - 1
            else AcquisitionState.SECTION_AVAILABLE
        )
        assert ledger.state(Category.GEOGRAPHY) is expected

    assert len(ledger.attempts) == len(index.sections)
    assert len(ledger.outcomes) == len(index.sections)


def test_revision_transition_records_changed_category_without_relevant_section(document):
    license_index = _index(document, "License\nAn MIT license is required.")
    license_section = _sections(license_index, Category.LICENSE)[0]
    ledger = CoverageLedger(license_index)
    ledger.begin(license_section.section_id, (Category.LICENSE,), 0)
    ledger.complete(
        license_section.section_id,
        {Category.LICENSE: _outcome("UNSUPPORTED")},
        0,
    )
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED

    deadline_index = _index(
        document,
        "Submission Deadline\nDeadline is 2026-09-30T12:00:00Z.",
        content_hash="c" * 64,
    )
    transition_count = len(ledger.transitions)
    ledger.replace_index(deadline_index)

    revision_events = ledger.transitions[transition_count:]
    license_events = [
        transition
        for transition in revision_events
        if getattr(transition, "category", None) is Category.LICENSE
    ]
    assert len(license_events) == 1
    event = license_events[0]
    assert event.key is None
    assert event.source_revision == deadline_index.source_revision
    assert event.before is AcquisitionState.EXHAUSTED
    assert event.after is AcquisitionState.UNSEEN
    assert event.cause == "SOURCE_REVISION_REOPENED"


def test_supported_conditional_rule_does_not_claim_applicant_compliance(document):
    index = _index(document, "Eligibility\nIndividuals may enter if resident locally.")
    section = _sections(index, Category.ENTRANT_TYPE)[0]
    ledger = CoverageLedger(index)
    ledger.begin(section.section_id, (Category.ENTRANT_TYPE,), 7)
    ledger.complete(
        section.section_id,
        {
            Category.ENTRANT_TYPE: _outcome(
                "SUPPORTED",
                rule_ids=("rule_conditional_entrant",),
                conditional=True,
            )
        },
        7,
    )

    outcome = ledger.outcomes[(index.source_revision, section.section_id, Category.ENTRANT_TYPE)]
    assert ledger.state(Category.ENTRANT_TYPE) is AcquisitionState.SUPPORTED
    assert outcome.conditional is True
    assert not hasattr(outcome, "applicant_compliance")
    assert not hasattr(outcome, "eligibility")
    assert not hasattr(ledger, "eligibility")


def test_incomplete_supported_context_exhausts_without_losing_support(document):
    index = _index(document, "License\nMIT is required unless otherwise specified.")
    section = _sections(index, Category.LICENSE)[0]
    ledger = CoverageLedger(index)
    ledger.begin(section.section_id, (Category.LICENSE,), 2)
    ledger.complete(
        section.section_id,
        {
            Category.LICENSE: _outcome(
                "SUPPORTED",
                rule_ids=("rule_license",),
                context_complete=True,
            )
        },
        2,
    )

    key = (index.source_revision, section.section_id, Category.LICENSE)
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED
    assert ledger.outcomes[key].supported_rule_ids == ("rule_license",)


def test_budget_refusal_unwinds_active_attempt_but_not_dispatched_pairs(document):
    index = _index(
        document,
        "Geography\nResidents may enter.\n"
        "Residency\nLocal rules may apply.\n"
        "Eligibility\nGeographic terms are listed.",
    )
    first, second, third = _sections(index, Category.GEOGRAPHY)
    ledger = CoverageLedger(index)

    ledger.begin(first.section_id, (Category.GEOGRAPHY,), 3)
    ledger.operational_failure(
        first.section_id,
        (Category.GEOGRAPHY,),
        "EXTRACTION_PROVIDER_ERROR",
    )
    first_key = (index.source_revision, first.section_id, Category.GEOGRAPHY)
    second_key = (index.source_revision, second.section_id, Category.GEOGRAPHY)
    assert first_key in ledger.attempts
    assert first_key not in ledger.outcomes
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.SECTION_AVAILABLE
    assert ledger.transitions[-1].before is AcquisitionState.EXTRACTION_ATTEMPTED
    assert ledger.transitions[-1].after is AcquisitionState.SECTION_AVAILABLE
    assert ledger.transitions[-1].outcome is not None
    assert ledger.transitions[-1].outcome.reason_code == "EXTRACTION_PROVIDER_ERROR"
    with pytest.raises(ValueError, match="ATTEMPT_ALREADY_DISPATCHED"):
        ledger.budget_blocked(first.section_id, (Category.GEOGRAPHY,))

    ledger.begin(second.section_id, (Category.GEOGRAPHY,), 4)
    ledger.complete(
        second.section_id,
        {Category.GEOGRAPHY: _outcome("AMBIGUOUS")},
        4,
    )
    with pytest.raises(ValueError, match="ATTEMPT_ALREADY_DISPATCHED"):
        ledger.budget_blocked(second.section_id, (Category.GEOGRAPHY,))

    ledger.begin(third.section_id, (Category.GEOGRAPHY,), 5)
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.EXTRACTION_ATTEMPTED
    assert (
        index.source_revision,
        third.section_id,
        Category.GEOGRAPHY,
    ) in ledger.attempts
    ledger.budget_blocked(third.section_id, (Category.GEOGRAPHY,))
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.SECTION_AVAILABLE
    assert ledger.transitions[-1].before is AcquisitionState.EXTRACTION_ATTEMPTED
    assert ledger.transitions[-1].after is AcquisitionState.SECTION_AVAILABLE
    assert ledger.transitions[-1].cause == "BUDGET_BLOCKED_UNDISPATCHED"
    assert ledger.transitions[-1].outcome is None
    third_key = (
        index.source_revision,
        third.section_id,
        Category.GEOGRAPHY,
    )
    assert third_key not in ledger.attempts
    assert third_key not in ledger.outcomes

    ledger.begin(third.section_id, (Category.GEOGRAPHY,), 6)
    assert ledger.state(Category.GEOGRAPHY) is AcquisitionState.EXTRACTION_ATTEMPTED
    assert second_key in ledger.attempts
    assert third_key in ledger.attempts


def test_diagnostic_snapshots_are_immutable_and_do_not_change_later(document):
    index = _index(document, "Geography\nResidents may enter.")
    section = _sections(index, Category.GEOGRAPHY)[0]
    ledger = CoverageLedger(index)

    transitions_snapshot = ledger.transitions
    attempts_snapshot = ledger.attempts
    outcomes_snapshot = ledger.outcomes
    assert isinstance(transitions_snapshot, tuple)
    assert isinstance(attempts_snapshot, frozenset)
    assert isinstance(outcomes_snapshot, MappingProxyType)
    with pytest.raises(TypeError):
        outcomes_snapshot[(index.source_revision, section.section_id, Category.GEOGRAPHY)] = (  # type: ignore[index]
            _outcome("UNKNOWN")
        )

    ledger.begin(section.section_id, (Category.GEOGRAPHY,), 0)
    ledger.complete(
        section.section_id,
        {Category.GEOGRAPHY: _outcome("UNSUPPORTED")},
        0,
    )

    assert transitions_snapshot == ()
    assert attempts_snapshot == frozenset()
    assert dict(outcomes_snapshot) == {}


def test_outcomes_reject_unsafe_reason_codes():
    with pytest.raises(ValidationError):
        _outcome("UNKNOWN", reason_code="raw provider error: secret=value")
