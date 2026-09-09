"""The loop offers a runtime-neutral sink. Persistence never reaches back into the runtime."""

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.run_models import StudioInput

LOOP_SOURCE = Path(__file__).parents[2] / "src/qualor/runtime/loop.py"


class RecordingSink:
    def __init__(self):
        self.events = []
        self.finished = []

    def trace_event(self, event, *, mode):
        self.events.append((event, mode))

    def run_finished(self, result):
        self.finished.append(result)


def studio_input():
    from qualor.decisions.fixture import ProjectDecisionInput
    from qualor.domain.base import Fact
    from qualor.domain.profiles import FounderProfile, ProjectProfile
    from qualor.effort import EffortAssumptions

    now = datetime.now(UTC)
    base = dict(
        schema_version="1",
        id="owned",
        version=1,
        created_at=now,
        updated_at=now,
        provenance="USER_ASSERTED",
    )
    project = ProjectProfile(
        **base,
        name="Owned",
        technology_stack=Fact(value=("Other SDK",), provenance="USER_ASSERTED"),
    )
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Find an owned synthetic opportunity",
        allowed_hosts=("example.org",),
        founder=FounderProfile(**base),
        projects=(ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),),
    )


def build_run(**kwargs):
    return OpportunityRun(
        studio_input(),
        mode="FIXTURE",
        search=object(),
        fetcher=object(),
        budget=LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal(".20"))),
        **kwargs,
    )


def test_loop_defaults_to_a_no_op_sink_so_deterministic_runs_stay_isolated():
    run = build_run()
    run.event("SEARCH_REQUESTED", "SEARCH_STARTED")
    assert len(run.trace) == 1


def test_loop_hands_each_bounded_event_to_the_sink_exactly_once_and_in_order():
    sink = RecordingSink()
    run = build_run(sink=sink)
    run.event("SEARCH_REQUESTED", "SEARCH_STARTED")
    run.event("SOURCE_FETCHED", "SOURCE_RETRIEVED", ("source-1",), 1)
    run.event("ELIGIBILITY_EVALUATED", "GATE_EVALUATED")
    assert [event.event for event, _ in sink.events] == [
        "SEARCH_REQUESTED",
        "SOURCE_FETCHED",
        "ELIGIBILITY_EVALUATED",
    ]
    assert [event.reason_code for event, _ in sink.events] == [
        "SEARCH_STARTED",
        "SOURCE_RETRIEVED",
        "GATE_EVALUATED",
    ]
    assert sink.events[1][0].source_ids == ("source-1",)
    assert sink.events[1][0].count == 1


def test_sink_receives_the_declared_run_mode_with_every_event():
    sink = RecordingSink()
    run = build_run(sink=sink)
    run.event("SEARCH_REQUESTED", "SEARCH_STARTED")
    assert {mode for _, mode in sink.events} == {"FIXTURE"}


def test_sink_events_carry_no_hidden_reasoning_or_raw_page_bodies():
    sink = RecordingSink()
    run = build_run(sink=sink)
    run.event("SOURCE_FETCHED", "SOURCE_RETRIEVED", ("source-1",), 1)
    published = set(sink.events[0][0].model_dump())
    assert published == {
        "event",
        "reason_code",
        "source_ids",
        "span_ids",
        "count",
        "normalized_field",
        "normalization_status",
        "normalizer_version",
    }


def test_sink_failure_never_breaks_the_runtime_or_the_recorded_trace():
    class FailingSink:
        def trace_event(self, event, *, mode):
            raise RuntimeError("sink unavailable")

        def run_finished(self, result):
            raise RuntimeError("sink unavailable")

    run = build_run(sink=FailingSink())
    run.event("SEARCH_REQUESTED", "SEARCH_STARTED")
    assert [event.event for event in run.trace] == ["SEARCH_REQUESTED"]


def test_loop_does_not_bound_the_sink_to_the_truncated_in_memory_trace():
    sink = RecordingSink()
    run = build_run(sink=sink)
    for _ in range(120):
        run.event("SEARCH_REQUESTED", "SEARCH_STARTED")
    assert len(run.trace) == 99
    assert len(sink.events) == 120


def test_loop_never_imports_persistence_or_workspace_modules():
    tree = ast.parse(LOOP_SOURCE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(
        name.startswith(("sqlite3", "qualor.workspace", "qualor.persistence")) for name in imported
    )
    assert not any("workspace" in name or "persistence" in name for name in imported)
