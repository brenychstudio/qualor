"""Worst-case reservation simulation of the canonical LIVE request sequence, offline."""

import copy
import inspect
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from archived_compiler_support import (
    ArchiveInputError,
    run_archived_compiler,
    simulate_request_sequence,
)

from qualor.runtime.agent import estimate_model_reservation, model_request_metrics
from qualor.runtime.budget import (
    QUALOR_5F_COST_CAP_USD,
    BudgetLimitExceeded,
    LiveBudgetGuard,
    LiveCallKind,
)
from qualor.runtime.extraction import MODEL_ID
from qualor.runtime.live_cli import live_budget
from qualor.runtime.search import WEB_SEARCH_RESERVED_COST_USD

ARCHIVE_ROOT = Path(
    r"C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source"
    r"\.qualor\local\killer-demo-real-source"
)
EXPECTED_LIVE_CALLS = 9
PLANNING_REQUESTS = 2
EXTRACTION_REQUESTS = 7

FETCH_RESERVATION_DEFAULT = inspect.signature(LiveBudgetGuard.reserve).parameters[
    "estimated_cost_usd"
].default


@pytest.fixture(scope="module")
def archived_report():
    """One archive-bound canonical run; every simulation below starts from a fresh guard."""

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("QUALOR_REQUIRE_ARCHIVE", "1")
        patch.setenv("QUALOR_ARCHIVE_DIR", str(ARCHIVE_ROOT))
        return run_archived_compiler(ARCHIVE_ROOT)


def _altered(report, *, requests=None, events=None):
    """Build a test-only report variant; never mutate the shared canonical capture."""

    selected = report.model_requests if requests is None else requests
    return replace(
        report,
        model_requests=tuple(copy.deepcopy(selected)),
        budget_events=tuple(report.budget_events if events is None else events),
    )


def _drop_first(events, kind):
    remaining = list(events)
    remaining.remove(kind)
    return tuple(remaining)


@pytest.mark.archived_source
def test_canonical_sequence_fits_the_frozen_live_guard(archived_report):
    """The exact Task 11 sequence must be admitted by an unmodified production guard."""

    report = archived_report
    kinds = [model_request_metrics(item)["request_kind"] for item in report.model_requests]

    assert len(report.model_requests) == len(report.request_sequence) == EXPECTED_LIVE_CALLS
    for captured, metadata in zip(report.model_requests, report.request_sequence, strict=True):
        metrics = model_request_metrics(captured)
        assert metrics["request_kind"] == metadata["request_kind"]
        assert metrics["request_bytes"] == metadata["request_bytes"]
        assert metrics["message_count"] == metadata["message_count"]
        assert metrics["tool_result_bytes"] == metadata["tool_result_bytes"]
        assert metrics["fetched_source_bytes"] == metadata["fetched_source_bytes"]
        assert metrics["isolated_source_bytes"] == metadata["isolated_source_bytes"]
        assert captured["modelId"] == metadata["model_id"] == MODEL_ID
        assert captured["inferenceConfig"]["maxTokens"] == metadata["max_tokens"]
    assert kinds.count("PLANNING") == PLANNING_REQUESTS
    assert kinds.count("EXTRACTION") == EXTRACTION_REQUESTS
    assert report.budget_events.count(LiveCallKind.SEARCH.value) == 1
    assert report.budget_events.count(LiveCallKind.FETCH.value) == 1
    assert report.budget_events.count(LiveCallKind.INFERENCE.value) == EXPECTED_LIVE_CALLS
    # The archive's physical order, read from execution rather than asserted as a wish.
    assert report.budget_events == (
        "INFERENCE",
        "SEARCH",
        "INFERENCE",
        "FETCH",
        *("INFERENCE",) * EXTRACTION_REQUESTS,
    )

    costs = simulate_request_sequence(report)

    assert costs.expected_live_calls == len(report.request_sequence)
    assert costs.expected_live_calls == EXPECTED_LIVE_CALLS
    assert costs.admitted is True
    assert costs.blocked_slot is None
    assert costs.projected_reserved_cost == costs.projected_worst_case_cost
    assert costs.projected_worst_case_cost <= QUALOR_5F_COST_CAP_USD
    assert costs.remaining_headroom == QUALOR_5F_COST_CAP_USD - costs.projected_worst_case_cost
    assert costs.remaining_headroom >= 0


@pytest.mark.archived_source
def test_worst_case_does_not_use_favorable_controlled_usage(archived_report, monkeypatch):
    """Reservations, not the controlled responses' tiny token counts, decide admission."""

    report = archived_report
    expected = (
        sum(
            (estimate_model_reservation(item) for item in report.model_requests),
            Decimal("0"),
        )
        + WEB_SEARCH_RESERVED_COST_USD * report.budget_events.count("SEARCH")
        + FETCH_RESERVATION_DEFAULT * report.budget_events.count("FETCH")
    )
    reconciled = sum(
        (
            Decimal(str(receipt.cost_reconciled))
            for receipt in report.receipts
            if receipt.cost_reconciled is not None
        ),
        Decimal("0"),
    )

    reserved_by_production = sum(
        (
            Decimal(str(receipt.cost_reserved))
            for receipt in report.receipts
            if receipt.cost_reserved is not None
        ),
        Decimal("0"),
    )

    costs = simulate_request_sequence(report)

    # The replayed model reservations are the ones production itself recorded.
    assert (
        sum(
            (estimate_model_reservation(item) for item in report.model_requests),
            Decimal("0"),
        )
        == reserved_by_production
    )
    assert costs.projected_worst_case_cost == expected
    # Task 11's controlled responses report intentionally tiny usage; the projection
    # must sit far above it, proving no refund was assumed.
    assert reconciled > 0
    assert costs.projected_worst_case_cost > reconciled

    def refuse(*_args, **_kwargs):
        raise AssertionError("Canonical worst-case simulation may not reconcile")

    monkeypatch.setattr(LiveBudgetGuard, "reconcile", refuse)
    unreconciled = simulate_request_sequence(report)

    assert unreconciled == costs


@pytest.mark.archived_source
def test_tenth_inference_request_is_refused(archived_report):
    """A tenth model request cannot be admitted without changing a frozen production limit."""

    canonical = simulate_request_sequence(archived_report)
    assert canonical.admitted is True, (
        f"canonical sequence already blocked at slot {canonical.blocked_slot}"
    )

    extra = copy.deepcopy(archived_report.model_requests[-1])
    guard = live_budget()
    for item in archived_report.model_requests:
        guard.commit(
            guard.reserve(
                LiveCallKind.INFERENCE, estimated_cost_usd=estimate_model_reservation(item)
            )
        )
    assert guard.snapshot().inference_calls == guard.policy.inference_max_calls == 9
    tenth = estimate_model_reservation(extra)
    # The raised USD ceiling does not authorize a tenth call: cost still fits,
    # so only the frozen inference call cap can be what refuses it.
    assert guard.snapshot().reserved_cost_usd + tenth <= guard.policy.cost_cap_usd

    with pytest.raises(BudgetLimitExceeded) as refused:
        guard.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=tenth)

    assert str(refused.value) == "INFERENCE call cap reached"
    assert refused.value.cost_cap_usd is None
    assert refused.value.attempted_cost_usd is None


@pytest.mark.archived_source
def test_eighth_extraction_request_invalidates_the_canonical_sequence(archived_report):
    """A canonical replay may not contain more than seven extraction requests."""

    extra = copy.deepcopy(archived_report.model_requests[-1])
    overflowing = _altered(
        archived_report,
        requests=(*archived_report.model_requests, extra),
        events=(*archived_report.budget_events, "INFERENCE"),
    )

    with pytest.raises(ArchiveInputError) as refused:
        simulate_request_sequence(overflowing)
    assert str(refused.value) == "COMPILER_COST_SEQUENCE_INCOMPLETE"


@pytest.mark.archived_source
def test_oversized_reservation_is_refused(archived_report):
    """An inflated request must fail the USD guard under the production estimator."""

    planning = next(
        item
        for item in archived_report.model_requests
        if model_request_metrics(item)["request_kind"] == "PLANNING"
    )
    oversized = copy.deepcopy(planning)
    oversized["messages"] = [
        *oversized["messages"],
        {"role": "user", "content": [{"text": "P" * 200_000}]},
    ]
    reservation = estimate_model_reservation(oversized)

    assert oversized["modelId"] == MODEL_ID
    assert reservation > QUALOR_5F_COST_CAP_USD

    guard = live_budget()
    with pytest.raises(BudgetLimitExceeded) as exceeded:
        guard.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=reservation)
    assert exceeded.value.cost_cap_usd == guard.policy.cost_cap_usd

    requests = list(copy.deepcopy(archived_report.model_requests))
    requests[0] = oversized
    costs = simulate_request_sequence(_altered(archived_report, requests=requests))

    assert costs.admitted is False
    assert costs.blocked_slot == 1


@pytest.mark.archived_source
def test_missing_planning_request_invalidates_the_sequence(archived_report):
    """A partial capture may not yield a cheaper admitted projection."""

    index = next(
        position
        for position, item in enumerate(archived_report.model_requests)
        if model_request_metrics(item)["request_kind"] == "PLANNING"
    )
    requests = [
        item for position, item in enumerate(archived_report.model_requests) if position != index
    ]
    partial = _altered(
        archived_report,
        requests=requests,
        events=_drop_first(archived_report.budget_events, "INFERENCE"),
    )

    with pytest.raises(ArchiveInputError) as refused:
        simulate_request_sequence(partial)
    assert str(refused.value) == "COMPILER_COST_SEQUENCE_INCOMPLETE"


@pytest.mark.archived_source
def test_search_reservation_is_the_production_authority(archived_report, monkeypatch):
    """Search cost must be read from the production constant, not a duplicated literal."""

    baseline = simulate_request_sequence(archived_report)
    delta = Decimal("0.001")
    monkeypatch.setattr(
        "qualor.runtime.search.WEB_SEARCH_RESERVED_COST_USD",
        WEB_SEARCH_RESERVED_COST_USD + delta,
    )

    shifted = simulate_request_sequence(archived_report)

    assert WEB_SEARCH_RESERVED_COST_USD > 0
    assert archived_report.budget_events.count("SEARCH") == 1
    assert shifted.projected_worst_case_cost - baseline.projected_worst_case_cost == delta


@pytest.mark.archived_source
def test_noncanonical_extra_non_model_event_invalidates_the_sequence(archived_report):
    """A canonical replay has exactly one SEARCH and one FETCH event."""

    assert archived_report.budget_events.count("FETCH") == 1

    guard = live_budget()
    before = guard.snapshot()
    guard.commit(guard.reserve(LiveCallKind.FETCH))
    after = guard.snapshot()

    assert after.fetched_documents - before.fetched_documents == 1
    assert after.reserved_cost_usd - before.reserved_cost_usd == FETCH_RESERVATION_DEFAULT

    for event in ("SEARCH", "FETCH"):
        noncanonical = _altered(
            archived_report,
            events=(event, *archived_report.budget_events),
        )
        with pytest.raises(ArchiveInputError) as refused:
            simulate_request_sequence(noncanonical)
        assert str(refused.value) == "COMPILER_COST_SEQUENCE_INCOMPLETE"
