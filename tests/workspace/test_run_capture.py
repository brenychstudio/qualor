"""The persistence adapter maps bounded runtime facts. It never authors new ones."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.persistence import Database
from qualor.runtime.run_models import AgentRunResult, TraceEvent
from qualor.workspace import WorkspaceStore
from qualor.workspace.run_capture import WorkspaceRunCapture

FIXED = datetime(2026, 9, 9, 12, 41, tzinfo=UTC)
FIXTURE = Path(__file__).parents[1] / "fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json"


def decision_output():
    fixture = DecisionFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    return decide_fixture(fixture)


def clock():
    moment = {"value": FIXED}

    def now():
        current = moment["value"]
        moment["value"] = current.replace(second=(current.second + 1) % 60)
        return current

    return now


def capture(tmp_path, *, mode="FIXTURE", run_id="run-1"):
    database = Database(tmp_path / "workspace.db")
    return database, WorkspaceRunCapture(database, run_id=run_id, mode=mode, clock=clock())


def result(termination_reason="SUFFICIENT_CRITICAL_EVIDENCE", *, mode="FIXTURE", trace=()):
    return AgentRunResult.model_validate(
        {
            "mode": mode,
            "decision": decision_output(),
            "claims": (),
            "trace": trace,
            "termination_reason": termination_reason,
            "agent_steps": 3,
            "search_calls": 2,
            "fetched_documents": 1,
            "official_source_count": 1,
            "citation_urls": (),
            "contradictions": (),
        }
    )


def trace(sink, event, reason, mode="FIXTURE", **kwargs):
    sink.trace_event(TraceEvent(event=event, reason_code=reason, **kwargs), mode=mode)


def events(database, run_id="run-1"):
    with database.transaction() as connection:
        return WorkspaceStore(connection).runs.list_run_events(run_id)


def run_record(database, run_id="run-1"):
    with database.transaction() as connection:
        return WorkspaceStore(connection).runs.current(run_id)


def test_capture_maps_each_bounded_event_exactly_once_in_order(tmp_path):
    database, sink = capture(tmp_path)
    trace(sink, "SEARCH_REQUESTED", "SEARCH_STARTED")
    trace(sink, "SOURCE_FETCHED", "SOURCE_RETRIEVED", source_ids=("source-1",), count=1)
    trace(sink, "DECISION_EVALUATED", "DECISION_RECORDED")
    sink.run_finished(result())

    persisted = events(database)
    assert [event.event_type for event in persisted] == [
        "SEARCH_REQUESTED",
        "SOURCE_FETCHED",
        "DECISION_EVALUATED",
    ]
    assert [event.sequence for event in persisted] == [1, 2, 3]
    assert persisted[1].payload.source_ids == ("source-1",)
    assert persisted[1].payload.count == 1
    assert persisted[1].payload.reason_code == "SOURCE_RETRIEVED"


def test_capture_labels_every_event_with_the_declared_run_mode(tmp_path):
    database, sink = capture(tmp_path, mode="REPLAY")
    trace(sink, "SEARCH_REQUESTED", "SEARCH_STARTED", mode="REPLAY")
    sink.run_finished(result(mode="REPLAY"))
    assert {event.mode.value for event in events(database)} == {"REPLAY"}
    assert run_record(database).mode.value == "REPLAY"


def test_capture_assigns_canonical_phases_to_public_event_types(tmp_path):
    database, sink = capture(tmp_path)
    for event, reason in [
        ("SEARCH_REQUESTED", "SEARCH_STARTED"),
        ("SOURCE_FETCHED", "SOURCE_RETRIEVED"),
        ("ELIGIBILITY_EVALUATED", "GATE_EVALUATED"),
        ("DECISION_EVALUATED", "DECISION_RECORDED"),
    ]:
        trace(sink, event, reason)
    sink.run_finished(result())
    assert [event.payload.phase for event in events(database)] == [
        "DISCOVERING",
        "VERIFYING",
        "EVALUATING",
        "DECISION_UPDATED",
    ]


def test_capture_omits_hidden_reasoning_and_raw_page_bodies(tmp_path):
    database, sink = capture(tmp_path)
    trace(sink, "SOURCE_FETCHED", "SOURCE_RETRIEVED", source_ids=("source-1",))
    sink.run_finished(result())
    payload = events(database)[0].payload.model_dump_json()
    for forbidden in ("prompt", "reasoning", "body", "content", "excerpt", "raw"):
        assert forbidden not in payload.lower()


def test_capture_retains_terminal_counters_from_the_runtime_result(tmp_path):
    database, sink = capture(tmp_path)
    sink.run_finished(
        result(), reserved_cost_usd=Decimal("0.021"), reported_cost_usd=Decimal("0.019")
    )
    record = run_record(database)
    assert record.state.value == "COMPLETED"
    assert record.search_calls == 2
    assert record.fetched_documents == 1
    assert record.official_source_count == 1
    assert record.reserved_cost_usd == Decimal("0.021")
    assert record.reported_cost_usd == Decimal("0.019")
    assert record.termination_reason == "SUFFICIENT_CRITICAL_EVIDENCE"


@pytest.mark.parametrize(
    ("termination_reason", "state"),
    [
        ("SUFFICIENT_CRITICAL_EVIDENCE", "COMPLETED"),
        ("HARD_FAIL_CONFIRMED", "COMPLETED"),
        ("BUDGET_EXHAUSTED", "BUDGET_STOPPED"),
        ("NO_PROGRESS", "PARTIAL"),
        ("TOOL_FAILURE_BOUND_REACHED", "PARTIAL"),
        ("MAX_STEPS", "PARTIAL"),
    ],
)
def test_capture_persists_each_terminal_state_exactly_as_the_runtime_reported_it(
    tmp_path, termination_reason, state
):
    database, sink = capture(tmp_path)
    sink.run_finished(result(termination_reason))
    record = run_record(database)
    assert record.state.value == state
    assert record.termination_reason == termination_reason


def test_capture_persists_a_disconnected_live_provider_as_a_degraded_live_run(tmp_path):
    database, sink = capture(tmp_path, mode="LIVE")
    trace(sink, "SEARCH_REQUESTED", "SEARCH_STARTED", mode="LIVE")
    sink.run_failed(
        termination_reason="PROVIDER_DISCONNECTED", provider_state="DISCONNECTED_LIVE_PROVIDER"
    )
    record = run_record(database)
    assert record.mode.value == "LIVE"
    assert record.state.value == "FAILED"
    assert record.provider_state == "DISCONNECTED_LIVE_PROVIDER"
    assert record.termination_reason == "PROVIDER_DISCONNECTED"
    assert [event.event_type for event in events(database)] == ["SEARCH_REQUESTED"]


def test_capture_writes_nothing_until_the_run_reaches_a_terminal_state(tmp_path):
    database, sink = capture(tmp_path)
    trace(sink, "SEARCH_REQUESTED", "SEARCH_STARTED")
    assert run_record(database) is None
    assert events(database) == ()


def test_capture_refuses_to_persist_one_run_twice(tmp_path):
    database, sink = capture(tmp_path)
    sink.run_finished(result())
    with pytest.raises(RuntimeError, match="already persisted"):
        sink.run_finished(result())


def test_capture_rejects_an_event_whose_mode_contradicts_the_run(tmp_path):
    _, sink = capture(tmp_path, mode="FIXTURE")
    with pytest.raises(ValueError, match="mode"):
        trace(sink, "SEARCH_REQUESTED", "SEARCH_STARTED", mode="LIVE")


def test_capture_records_the_run_timestamps_it_observed(tmp_path):
    database, sink = capture(tmp_path)
    trace(sink, "SEARCH_REQUESTED", "SEARCH_STARTED")
    sink.run_finished(result())
    record = run_record(database)
    assert record.started_at is not None
    assert record.completed_at is not None
    assert record.completed_at >= record.started_at
    assert events(database)[0].occurred_at == FIXED
