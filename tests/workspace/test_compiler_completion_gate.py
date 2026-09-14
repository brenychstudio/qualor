"""Audit the real archived compiler result against existing completion policy."""

from __future__ import annotations

import importlib.util
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

import qualor.runtime.handoff as handoff
import qualor.runtime.live_cli as live_cli
from qualor.persistence import Database
from qualor.workspace import WorkspaceStore
from qualor.workspace.run_capture import TERMINAL_STATES, WorkspaceRunCapture

ARCHIVE_ROOT = Path(
    r"C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source"
    r"\.qualor\local\killer-demo-real-source"
)
SUCCESS_TERMINATIONS = frozenset(
    {"SUFFICIENT_CRITICAL_EVIDENCE", "HARD_FAIL_CONFIRMED"}
)
ALLOWED_CASES = frozenset({"CASE_A", "CASE_B", "OTHER_BLOCKER"})
ARCHIVE_SUPPORT_MODULE = "_qualor_task14_archived_compiler_support"


@dataclass(frozen=True)
class CompletionDiagnostic:
    case: str
    existing_completion_policy_can_persist_truthful_graph: bool
    fourth_paid_run_candidate: bool
    next_action: str
    blocker: str | None = None

    def __post_init__(self) -> None:
        if self.case not in ALLOWED_CASES:
            raise ValueError(f"Unsupported completion diagnostic case: {self.case}")


def _load_archive_support() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "runtime"
        / "archived_compiler_support.py"
    )
    spec = importlib.util.spec_from_file_location(ARCHIVE_SUPPORT_MODULE, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ARCHIVED_COMPILER_SUPPORT_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[ARCHIVE_SUPPORT_MODULE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(ARCHIVE_SUPPORT_MODULE, None)
        raise
    return module


def _deny_external_io_with_loopback_runtime(support, monkeypatch):
    """Keep the archive guard while allowing asyncio's local Windows self-pipe."""

    loopback_sockets = socket.socketpair()
    support.deny_external_io(monkeypatch)
    supplied = False

    def asyncio_socketpair(*args, **kwargs):
        nonlocal supplied
        if supplied or args or kwargs:
            raise support.ArchiveInputError("ARCHIVE_EXTERNAL_IO_DENIED")
        supplied = True
        return loopback_sockets

    monkeypatch.setattr(socket, "socketpair", asyncio_socketpair)
    return loopback_sockets


def _compiler_correctness_blocker(report) -> str | None:
    gates = report.gate_values
    checks = (
        (
            gates["RAW_AUTHORITATIVE_CANONICAL_FACTS"] > 0,
            "MISSING_RAW_AUTHORITATIVE_CANONICAL_FACTS",
        ),
        (gates["RAW_EXECUTABLE_RULES"] > 0, "MISSING_RAW_EXECUTABLE_RULES"),
        (
            gates["COVERAGE_GUARDED_SUPPORTED_CLAIMS"] > 0,
            "MISSING_COVERAGE_GUARDED_SUPPORTED_CLAIMS",
        ),
        (gates["sourceless_rules"] == 0, "SOURCELESS_RULES"),
        (gates["quote_fabrication"] == 0, "QUOTE_FABRICATION"),
        (
            gates["qualifier_or_exception_drops"] == 0,
            "QUALIFIER_OR_EXCEPTION_DROPS",
        ),
        (
            gates["owner_facts_inferred_from_rules"] == 0,
            "OWNER_FACTS_INFERRED_FROM_RULES",
        ),
        (
            gates["project_facts_inferred_from_rules"] == 0,
            "PROJECT_FACTS_INFERRED_FROM_RULES",
        ),
        (
            gates["decision_derived_from_canonical_authority"] is True,
            "DECISION_NOT_DERIVED_FROM_CANONICAL_AUTHORITY",
        ),
        (
            gates["DEFAULT_9KB_WINDOW_ONLY"] is False,
            "DEFAULT_9KB_WINDOW_ONLY",
        ),
        (
            gates["REPEATED_IDENTICAL_WINDOW"] is False,
            "REPEATED_IDENTICAL_WINDOW",
        ),
        (
            gates["duplicate_section_category_attempts"] == 0,
            "DUPLICATE_SECTION_CATEGORY_ATTEMPTS",
        ),
        (
            gates["extraction_after_exhaustion"] == 0,
            "EXTRACTION_AFTER_EXHAUSTION",
        ),
        (
            gates["planner_rediscovery_calls"] == 0,
            "PLANNER_REDISCOVERY_CALLS",
        ),
        (
            gates["unresolved_remains_unresolved"] is True,
            "UNRESOLVED_AUTHORITY_WAS_PROMOTED",
        ),
        (len(report.request_sequence) == 9, "MODEL_REQUEST_SEQUENCE_NOT_NINE"),
        (len(report.receipts) == 9, "MODEL_RECEIPT_SEQUENCE_NOT_NINE"),
        (
            sum(
                item["request_kind"] == "PLANNING"
                for item in report.request_sequence
            )
            == 2,
            "PLANNING_REQUEST_SEQUENCE_NOT_TWO",
        ),
        (
            sum(
                item["request_kind"] == "EXTRACTION"
                for item in report.request_sequence
            )
            == 7,
            "EXTRACTION_REQUEST_SEQUENCE_NOT_SEVEN",
        ),
    )
    return next((code for passed, code in checks if not passed), None)


def _operational_blocker(report) -> str | None:
    termination = report.result.termination_reason
    if termination in {
        "BUDGET_EXHAUSTED",
        "MAX_STEPS",
        "TOOL_FAILURE_BOUND_REACHED",
    }:
        return termination
    incomplete_receipt = next(
        (
            receipt
            for receipt in report.receipts
            if receipt.execution_state != "COMPLETED"
        ),
        None,
    )
    if incomplete_receipt is not None:
        return f"MODEL_RECEIPT_{incomplete_receipt.execution_state}"
    if report.result.official_source_count == 0 or not report.result.bundle.evidence:
        return "MISSING_CANONICAL_EVIDENCE"
    return None


def _classify(
    report,
    persisted_run,
    opportunity_count: int,
    decision_count: int,
) -> CompletionDiagnostic:
    blocker = _compiler_correctness_blocker(report) or _operational_blocker(report)
    if blocker is not None:
        return CompletionDiagnostic(
            case="OTHER_BLOCKER",
            existing_completion_policy_can_persist_truthful_graph=False,
            fourth_paid_run_candidate=False,
            blocker=blocker,
            next_action=f"CONTROLLER_REVIEW_{blocker}",
        )

    termination = report.result.termination_reason
    selected = report.result.decision.selected_decision
    if termination in SUCCESS_TERMINATIONS:
        linked = (
            selected is not None
            and persisted_run.opportunity_id is not None
            and persisted_run.decision_id == selected.id
            and opportunity_count == 1
            and decision_count == len(report.result.bundle.decision.candidates)
        )
        if not linked:
            return CompletionDiagnostic(
                case="OTHER_BLOCKER",
                existing_completion_policy_can_persist_truthful_graph=False,
                fourth_paid_run_candidate=False,
                blocker="SUCCESS_GRAPH_PERSISTENCE_LINKAGE",
                next_action="CONTROLLER_REVIEW_SUCCESS_GRAPH_PERSISTENCE_LINKAGE",
            )
        return CompletionDiagnostic(
            case="CASE_A",
            existing_completion_policy_can_persist_truthful_graph=True,
            fourth_paid_run_candidate=True,
            next_action="OWNER_REVIEW_FOR_FOURTH_PAID_RUN",
        )

    graph_absent = (
        persisted_run.opportunity_id is None
        and persisted_run.decision_id is None
        and opportunity_count == 0
        and decision_count == 0
    )
    if (
        termination == "NO_PROGRESS"
        and report.result.decision.eligibility == "REVIEW_REQUIRED"
        and graph_absent
    ):
        return CompletionDiagnostic(
            case="CASE_B",
            existing_completion_policy_can_persist_truthful_graph=False,
            fourth_paid_run_candidate=False,
            next_action=(
                "QUALOR-LIVE-PRODUCTION-TASK-5G-COMPLETION-SEMANTICS-DESIGN"
            ),
        )

    blocker = (
        "NON_SUCCESS_GRAPH_PERSISTED"
        if not graph_absent
        else f"UNCLASSIFIED_TERMINATION_{termination}"
    )
    return CompletionDiagnostic(
        case="OTHER_BLOCKER",
        existing_completion_policy_can_persist_truthful_graph=False,
        fourth_paid_run_candidate=False,
        blocker=blocker,
        next_action=f"CONTROLLER_REVIEW_{blocker}",
    )


def _assert_case_a_graph_identity(store, report, persisted_run, inputs) -> None:
    bundle = report.result.bundle
    selected = report.result.decision.selected_decision
    assert selected is not None
    assert (persisted_run.opportunity_id, persisted_run.opportunity_version) == (
        bundle.opportunity.id,
        bundle.opportunity.version,
    )
    assert (persisted_run.decision_id, persisted_run.decision_version) == (
        selected.id,
        selected.version,
    )

    workspace = store.load_opportunity_workspace(
        bundle.opportunity.id, bundle.opportunity.version
    )
    assert workspace is not None
    assert workspace.opportunity == bundle.opportunity
    persisted_evidence = {(item.id, item.version): item for item in workspace.evidence}
    runtime_evidence = {(item.id, item.version): item for item in bundle.evidence}
    assert persisted_evidence == runtime_evidence
    assert {
        key: item.clause_context for key, item in persisted_evidence.items()
    } == {key: item.clause_context for key, item in runtime_evidence.items()}
    assert {
        (item.id, item.version): item for item in workspace.decisions
    } == {
        (item.id, item.version): item for item in bundle.decision.candidates
    }

    input_projects = {item.project.id: item.project for item in inputs.projects}
    selected_snapshot = next(
        item
        for item in workspace.decision_snapshots
        if (item.decision.id, item.decision.version) == (selected.id, selected.version)
    )
    assert selected_snapshot.founder_profile == inputs.founder
    assert selected_snapshot.project_profile == input_projects[selected.project_id]


@pytest.mark.archived_source
def test_archived_compiler_result_obeys_existing_completion_and_persistence_policy(
    tmp_path, monkeypatch
):
    support = _load_archive_support()
    monkeypatch.setenv("QUALOR_REQUIRE_ARCHIVE", "1")
    monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(ARCHIVE_ROOT))
    loopback_sockets = _deny_external_io_with_loopback_runtime(
        support, monkeypatch
    )

    source = support.load_archived_rules(ARCHIVE_ROOT)
    database = Database(tmp_path / "compiler.db")
    inputs = support.archived_studio_input()
    budget = live_cli.live_budget()
    sink = WorkspaceRunCapture(
        database,
        mode="LIVE",
        run_id="compiler-completion",
        inputs=inputs,
        budget=budget,
        clock=lambda: source.retrieved_at,
    )
    monkeypatch.setattr(live_cli, "live_budget", lambda: budget)
    decide_spy = Mock(wraps=handoff.decide)
    monkeypatch.setattr(handoff, "decide", decide_spy)
    persistence_decide_calls = []
    persist_runtime_result = sink.run_finished

    def observe_persistence(result, **kwargs):
        before = decide_spy.call_count
        try:
            return persist_runtime_result(result, **kwargs)
        finally:
            persistence_decide_calls.append((before, decide_spy.call_count))

    monkeypatch.setattr(sink, "run_finished", observe_persistence)

    try:
        report = support.run_archived_compiler(ARCHIVE_ROOT, sink=sink)
    finally:
        for loopback_socket in loopback_sockets:
            loopback_socket.close()

    assert sink.budget is budget
    budget_snapshot = budget.snapshot()
    assert budget_snapshot.inference_calls == report.gate_values[
        "dispatched_model_requests"
    ]
    assert budget_snapshot.inference_calls == 9
    assert budget_snapshot.reserved_cost_usd <= budget.policy.cost_cap_usd
    sink.require_persisted()
    decide_calls_after_runtime = decide_spy.call_count
    assert decide_calls_after_runtime >= 1
    assert persistence_decide_calls
    assert all(before == after for before, after in persistence_decide_calls)

    reopened = Database(database.path)
    with reopened.transaction() as connection:
        store = WorkspaceStore(connection)
        persisted_run = store.runs.current("compiler-completion")
        assert persisted_run is not None
        assert persisted_run.mode.value == report.result.mode
        assert persisted_run.state == TERMINAL_STATES[report.result.termination_reason]
        assert persisted_run.termination_reason == report.result.termination_reason
        opportunity_count = connection.execute(
            "SELECT COUNT(*) FROM opportunity_versions"
        ).fetchone()[0]
        decision_count = connection.execute(
            "SELECT COUNT(*) FROM decisions"
        ).fetchone()[0]
        events = store.runs.list_run_events("compiler-completion")
        receipt_events = tuple(
            event for event in events if event.event_type == "MODEL_CALL_RECEIPT"
        )

        diagnostic = _classify(
            report, persisted_run, opportunity_count, decision_count
        )

        if diagnostic.case in {"CASE_A", "CASE_B"}:
            assert _compiler_correctness_blocker(report) is None
        if diagnostic.case == "CASE_A":
            assert report.result.termination_reason in SUCCESS_TERMINATIONS
            assert persisted_run.opportunity_id is not None
            assert (
                persisted_run.decision_id
                == report.result.decision.selected_decision.id
            )
            assert diagnostic.fourth_paid_run_candidate is True
            _assert_case_a_graph_identity(store, report, persisted_run, inputs)
        elif diagnostic.case == "CASE_B":
            assert report.result.decision.eligibility == "REVIEW_REQUIRED"
            assert persisted_run.opportunity_id is None
            assert persisted_run.decision_id is None
            assert opportunity_count == decision_count == 0
            assert diagnostic.fourth_paid_run_candidate is False
        else:
            assert diagnostic.blocker is not None
            assert diagnostic.fourth_paid_run_candidate is False

    if report.result.termination_reason not in SUCCESS_TERMINATIONS:
        assert persisted_run.opportunity_id is None
        assert persisted_run.decision_id is None
        assert opportunity_count == decision_count == 0
    assert events
    assert events[-1].event_type == "RUN_TERMINATED"
    assert events[-1].mode.value == report.result.mode
    assert events[-1].payload.reason_code == report.result.termination_reason
    assert tuple(event.payload.receipt for event in receipt_events) == report.receipts
    assert decide_spy.call_count == decide_calls_after_runtime
