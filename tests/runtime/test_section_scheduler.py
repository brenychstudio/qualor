"""Plan-driven section scheduling contracts."""

from qualor.runtime.acquisition_coverage import AcquisitionOutcome, CoverageLedger
from qualor.runtime.acquisition_plan import AcquisitionTier, build_acquisition_plan
from qualor.runtime.budget import LiveCallKind
from qualor.runtime.live_cli import live_budget
from qualor.runtime.section_scheduler import ExtractionJob, NoExtractionJob, SectionScheduler
from qualor.runtime.sections import index_source
from qualor.runtime.spans import EvidenceSpanRegistry


def _scheduled(document, text):
    index = index_source(document(text), EvidenceSpanRegistry(secret=b"s" * 32))
    plan = build_acquisition_plan(index)
    ledger = CoverageLedger(index, plan)
    return index, plan, ledger, SectionScheduler(index, plan, ledger, live_budget())


def _unknown():
    return AcquisitionOutcome(
        normalization_status="UNKNOWN",
        supported_rule_ids=(),
        conditional=False,
        context_complete=False,
        reason_code="CONTROLLED_UNKNOWN",
    )


def test_scheduler_uses_real_plan_identity_and_mandatory_rank(document):
    index, plan, ledger, scheduler = _scheduled(
        document,
        "Ordinary background.\n"
        "License\nProjects must use an MIT license.\n"
        "Technology\nProjects must use Widget SDK.",
    )

    job = scheduler.next_job(authority_revision=3, steps_remaining=24, terminated=False)

    assert isinstance(job, ExtractionJob)
    item = next(item for item in plan.items if item.item_id == job.plan_item_id)
    assert job.plan_id == plan.plan_id
    assert job.tier is AcquisitionTier.MANDATORY_ANCHOR
    assert item.section_id == job.section_id
    assert job.categories == item.categories
    assert ledger.active_items()[0][0].item_id == item.item_id
    assert index.source_revision == job.source_revision


def test_scheduler_never_multiplies_reserve_sections_by_category(document):
    _index, plan, ledger, scheduler = _scheduled(document, "Ordinary background notes.")

    assert all(item.tier is AcquisitionTier.RESERVE_FALLBACK for item in plan.items)
    assert all(item.categories == () for item in plan.items)
    assert ledger.unresolved_obligations() == ()
    assert (
        scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False).reason_code
        == "PLAN_EXHAUSTED"
    )


def test_scheduler_marks_eighth_slot_as_plan_exhausted_before_budget_reservation(document):
    _index, plan, ledger, scheduler = _scheduled(
        document,
        "Deadline\nSubmit by September 1.\n"
        "License\nProjects must use an MIT license.\n"
        "Technology\nProjects must use Widget SDK.\n"
        "Financial Support\nProjects may not accept sponsor support.\n"
        "Prize\nWinners must satisfy judging rules.\n"
        "Entrants\nEntrants must be individuals.\n"
        "Geography\nResidents must be eligible.\n"
        "Project\nProjects must be new.\n"
        "Entity\nCompanies may not enter.",
    )

    for revision in range(7):
        job = scheduler.next_job(
            authority_revision=revision, steps_remaining=24 - revision, terminated=False
        )
        assert isinstance(job, ExtractionJob)
        scheduler.begin(job)
        ledger.complete_item(
            job.plan_item_id,
            job.categories,
            {category: _unknown() for category in job.categories},
            revision,
        )
        scheduler._budget.reserve(  # noqa: SLF001 - mirrors the real request boundary
            LiveCallKind.INFERENCE,
            estimated_cost_usd=scheduler._budget.policy.cost_cap_usd / 10,
        )

    stopped = scheduler.next_job(authority_revision=7, steps_remaining=17, terminated=False)
    assert isinstance(stopped, NoExtractionJob)
    assert stopped.reason_code == "PLAN_EXHAUSTED"
    assert len({key[1] for key in ledger.attempts}) <= 7
    assert all(overflow.dispatches_used == 7 for overflow in ledger.overflows)


def test_scheduler_capacity_uses_real_inference_reservations_not_logical_begins(document):
    _index, _plan, ledger, scheduler = _scheduled(
        document, "License\nProjects must use an MIT license."
    )

    for revision in range(7):
        job = scheduler.next_job(
            authority_revision=revision, steps_remaining=24 - revision, terminated=False
        )
        assert isinstance(job, ExtractionJob)
        scheduler.begin(job)
        ledger.budget_blocked_item(job.plan_item_id, job.categories)

    next_job = scheduler.next_job(authority_revision=7, steps_remaining=17, terminated=False)

    assert isinstance(next_job, ExtractionJob)


def test_physical_budget_refusal_precedes_first_permitted_plan_job(document):
    _index, _plan, ledger, scheduler = _scheduled(
        document, "License\nProjects must use an MIT license."
    )
    for _ in range(scheduler._budget.policy.inference_max_calls):
        scheduler._budget.reserve(  # noqa: SLF001 - controlled real budget boundary
            LiveCallKind.INFERENCE,
            estimated_cost_usd=scheduler._budget.policy.cost_cap_usd / 10,
        )

    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "BUDGET_BLOCKED"
    assert not ledger.attempts


def test_context_incomplete_plan_item_is_not_dispatched(document):
    _index, _plan, ledger, scheduler = _scheduled(
        document, "License\nProjects must use an MIT license unless otherwise specified."
    )

    result = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)

    assert isinstance(result, NoExtractionJob)
    assert result.reason_code == "CONTEXT_UNRESOLVED"
    assert not ledger.attempts
