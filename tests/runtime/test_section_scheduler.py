import pytest

from qualor.domain.enums import Category
from qualor.runtime.acquisition_coverage import AcquisitionState, CoverageLedger
from qualor.runtime.budget import LiveCallKind
from qualor.runtime.live_cli import live_budget
from qualor.runtime.section_scheduler import (
    ExtractionJob,
    NoExtractionJob,
    SectionScheduler,
)
from qualor.runtime.sections import SectionIndex, index_source
from qualor.runtime.spans import EvidenceSpanRegistry


def _index(document, text: str) -> SectionIndex:
    return index_source(document(text), EvidenceSpanRegistry(secret=b"s" * 32))


def _replace_contexts(
    index: SectionIndex,
    contexts: dict[int, tuple[int, ...]],
    *,
    incomplete: tuple[int, ...] = (),
) -> SectionIndex:
    sections = tuple(
        section.model_copy(
            update={
                "context_section_ids": tuple(
                    index.sections[target].section_id for target in contexts.get(position, ())
                ),
                "context_complete": position not in incomplete,
            }
        )
        for position, section in enumerate(index.sections)
    )
    return SectionIndex(
        source_id=index.source_id,
        source_revision=index.source_revision,
        indexer_version=index.indexer_version,
        sections=sections,
    )


def test_category_enumeration_precedes_source_offsets(document):
    index = _index(
        document,
        "License\nAn MIT license is required.\nSubmission Deadline\nSubmit by September 30.",
    )
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    job = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(job, ExtractionJob)
    assert job.categories == (Category.DEADLINE,)
    assert job.section_id == index.sections[1].section_id


def test_source_offsets_break_category_ties(document):
    index = _index(
        document,
        "Geography\nResidents of Spain may enter.\nResidency\nLocal residents may enter.",
    )
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    job = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(job, ExtractionJob)
    assert job.categories == (Category.GEOGRAPHY,)
    assert job.section_id == index.sections[0].section_id


def test_scheduler_packs_at_most_two_categories(document):
    index = _index(
        document,
        "Eligibility\nResidents and incorporated companies may enter.",
    )
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    job = scheduler.next_job(authority_revision=4, steps_remaining=24, terminated=False)

    assert isinstance(job, ExtractionJob)
    assert job.categories == (Category.ENTRANT_TYPE, Category.GEOGRAPHY)
    assert len(job.categories) == 2


def test_scheduler_cannot_repeat_pair(document):
    index = _index(document, "License\nAn MIT license is required.")
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())
    job = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)
    assert isinstance(job, ExtractionJob)

    scheduler.begin(job)

    with pytest.raises(ValueError, match="DUPLICATE_SECTION_CATEGORY_ATTEMPT"):
        scheduler.begin(job)


def test_operational_failure_consumes_pair_and_advances_by_offset(document):
    index = _index(
        document,
        "Geography\nResidents of Spain may enter.\nResidency\nLocal residents may enter.",
    )
    ledger = CoverageLedger(index)
    scheduler = SectionScheduler(index, ledger, live_budget())
    first = scheduler.next_job(authority_revision=3, steps_remaining=24, terminated=False)
    assert isinstance(first, ExtractionJob)
    scheduler.begin(first)
    ledger.operational_failure(first.section_id, first.categories, "EXTRACTION_PROVIDER_ERROR")

    second = scheduler.next_job(authority_revision=4, steps_remaining=23, terminated=False)

    assert isinstance(second, ExtractionJob)
    assert second.section_id == index.sections[1].section_id
    assert second.categories == (Category.GEOGRAPHY,)


def test_unclassified_sections_have_deterministic_fallback(document):
    index = _index(
        document,
        "Ordinary background notes without a classified rule.\n" * 30,
    )
    ledger = CoverageLedger(index)
    scheduler = SectionScheduler(index, ledger, live_budget())

    first = scheduler.next_job(authority_revision=2, steps_remaining=24, terminated=False)
    repeated = scheduler.next_job(authority_revision=2, steps_remaining=24, terminated=False)

    assert first == repeated
    assert isinstance(first, ExtractionJob)
    assert first.section_id == index.sections[0].section_id
    assert first.categories == (Category.DEADLINE, Category.ENTRANT_TYPE)
    assert all(
        ledger.state(category) is AcquisitionState.SECTION_AVAILABLE for category in Category
    )


def test_scheduler_attempts_all_relevant_source_sections_before_pivot(document):
    index = _index(
        document,
        "License\nAn MIT license is required.\nGeography\nResidents of Spain may enter.",
    )
    ledger = CoverageLedger(index)
    scheduler = SectionScheduler(index, ledger, live_budget())

    scheduled = []
    for authority_revision in range(2):
        job = scheduler.next_job(
            authority_revision=authority_revision,
            steps_remaining=24 - authority_revision,
            terminated=False,
        )
        assert isinstance(job, ExtractionJob)
        scheduled.append((job.section_id, job.categories))
        scheduler.begin(job)
        ledger.operational_failure(job.section_id, job.categories, "EXTRACTION_PROVIDER_ERROR")

    exhausted = scheduler.next_job(authority_revision=2, steps_remaining=22, terminated=False)

    assert scheduled == [
        (index.sections[1].section_id, (Category.GEOGRAPHY,)),
        (index.sections[0].section_id, (Category.LICENSE,)),
    ]
    assert isinstance(exhausted, NoExtractionJob)
    assert exhausted.reason_code == "SOURCE_EXHAUSTED"
    assert exhausted.pivot_eligible is True


def test_source_exhaustion_reconciles_categories_absent_from_index(document):
    index = _index(document, "Geography\nResidents of Spain may enter.")
    ledger = CoverageLedger(index)
    scheduler = SectionScheduler(index, ledger, live_budget())

    job = scheduler.next_job(authority_revision=7, steps_remaining=24, terminated=False)
    assert isinstance(job, ExtractionJob)
    scheduler.begin(job)
    ledger.operational_failure(job.section_id, job.categories, "EXTRACTION_PROVIDER_ERROR")

    exhausted = scheduler.next_job(authority_revision=8, steps_remaining=23, terminated=False)

    assert isinstance(exhausted, NoExtractionJob)
    assert exhausted.reason_code == "SOURCE_EXHAUSTED"
    assert all(ledger.state(category) is AcquisitionState.EXHAUSTED for category in Category)
    license_transition = next(
        transition for transition in ledger.transitions if transition.category is Category.LICENSE
    )
    assert license_transition.key is None
    assert license_transition.source_revision == index.source_revision
    assert license_transition.before is AcquisitionState.UNSEEN
    assert license_transition.after is AcquisitionState.EXHAUSTED
    assert license_transition.outcome is None
    assert license_transition.authority_revision == 7
    assert license_transition.cause == "NO_RELEVANT_SECTION_INDEXED"
    assert dict(ledger.outcomes) == {}


def test_absence_exhaustion_survives_source_revision_aba(document):
    geography = _index(document, "Geography\nResidents of Spain may enter.")
    ledger = CoverageLedger(geography)
    first_scheduler = SectionScheduler(geography, ledger, live_budget())
    first = first_scheduler.next_job(authority_revision=3, steps_remaining=24, terminated=False)
    assert isinstance(first, ExtractionJob)
    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED

    license_index = _index(document, "License\nAn MIT license is required.")
    ledger.replace_index(license_index)
    second_scheduler = SectionScheduler(license_index, ledger, live_budget())
    second = second_scheduler.next_job(authority_revision=4, steps_remaining=24, terminated=False)
    assert isinstance(second, ExtractionJob)
    assert ledger.state(Category.LICENSE) is AcquisitionState.SECTION_AVAILABLE

    ledger.replace_index(geography)

    assert ledger.state(Category.LICENSE) is AcquisitionState.EXHAUSTED
    restored = [
        transition
        for transition in ledger.transitions
        if transition.category is Category.LICENSE
        and transition.source_revision == geography.source_revision
    ][-1]
    assert restored.after is AcquisitionState.EXHAUSTED
    assert restored.cause == "SOURCE_REVISION_RESTORED"


def test_budget_refusal_records_zero_inspections(document):
    index = _index(document, "License\nAn MIT license is required.")
    ledger = CoverageLedger(index)
    budget = live_budget()
    for _ in range(budget.policy.inference_max_calls):
        budget.reserve(LiveCallKind.INFERENCE)
    scheduler = SectionScheduler(index, ledger, budget)

    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "BUDGET_BLOCKED"
    assert result.pivot_eligible is False
    assert ledger.attempts == frozenset()
    assert dict(ledger.outcomes) == {}
    assert ledger.transitions == ()


@pytest.mark.parametrize(
    ("terminated", "steps_remaining", "reason_code"),
    [(True, 24, "RUN_TERMINATED"), (False, 0, "STEP_BOUND")],
)
def test_terminal_bounds_precede_selection(
    document, terminated: bool, steps_remaining: int, reason_code: str
):
    index = _index(document, "License\nAn MIT license is required.")
    ledger = CoverageLedger(index)
    scheduler = SectionScheduler(index, ledger, live_budget())

    result = scheduler.next_job(
        authority_revision=0,
        steps_remaining=steps_remaining,
        terminated=terminated,
    )

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == reason_code
    assert result.pivot_eligible is False
    assert ledger.attempts == frozenset()


def test_context_closure_is_transitive_cycle_safe_and_span_bounded(document):
    index = _index(
        document,
        "License A\nMIT applies.\nLicense B\nApache applies.\nLicense C\nBSD applies.",
    )
    index = _replace_contexts(index, {0: (1,), 1: (2,), 2: (0,)})
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    job = scheduler.next_job(authority_revision=7, steps_remaining=24, terminated=False)

    assert isinstance(job, ExtractionJob)
    assert job.context_section_ids == (
        index.sections[1].section_id,
        index.sections[2].section_id,
    )
    assert job.span_ids == (
        *index.sections[0].span_ids,
        *index.sections[1].span_ids,
        *index.sections[2].span_ids,
    )
    assert len(job.span_ids) <= 12


def test_incomplete_transitive_context_fails_closed(document):
    index = _index(
        document,
        "License A\nMIT applies.\nLicense B\nApache applies.\nLicense C\nBSD applies.",
    )
    index = _replace_contexts(index, {0: (1,), 1: (2,)}, incomplete=(2,))
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "CONTEXT_UNRESOLVED"
    assert result.pivot_eligible is True


def test_safe_current_source_section_is_scheduled_before_context_pivot(document):
    index = _index(
        document,
        "License A\nMIT applies.\nLicense B\nApache applies.",
    )
    index = _replace_contexts(index, {}, incomplete=(0,))
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    job = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(job, ExtractionJob)
    assert job.section_id == index.sections[1].section_id


def test_context_that_exceeds_job_span_bound_fails_closed(document):
    text = "".join(f"License {position}\nMIT applies.\n" for position in range(13))
    index = _index(document, text)
    contexts = {
        position: tuple(target for target in range(13) if target != position)
        for position in range(13)
    }
    index = _replace_contexts(index, contexts)
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "CONTEXT_UNRESOLVED"
    assert result.pivot_eligible is True


def test_context_without_an_exact_span_capability_fails_closed(document):
    index = _index(
        document,
        "License A\nMIT applies.\nLicense B\nApache applies.",
    )
    sections = (
        index.sections[0].model_copy(
            update={"context_section_ids": (index.sections[1].section_id,)}
        ),
        index.sections[1].model_copy(update={"span_ids": ()}),
    )
    index = SectionIndex(
        source_id=index.source_id,
        source_revision=index.source_revision,
        indexer_version=index.indexer_version,
        sections=sections,
    )
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())

    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "CONTEXT_UNRESOLVED"
