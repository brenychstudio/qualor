"""Maps bounded runtime facts onto persisted run history.

The runtime owns what happened. This adapter only records it. It never recomputes a
decision, invents an event, or reports a state the runtime did not reach.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from qualor.persistence import Database
from qualor.runtime.run_models import AgentRunResult, TraceEvent

from .models import RunEventPayload, RunRecord, RunState
from .store import WorkspaceStore

# Canonical user-facing phases. A new public runtime event must be mapped here explicitly.
PHASES: dict[str, str | None] = {
    "SEARCH_REQUESTED": "DISCOVERING",
    "SEARCH_RESULTS_RECEIVED": "DISCOVERING",
    "CANDIDATE_SELECTED": "DISCOVERING",
    "SOURCE_SELECTED": "DISCOVERING",
    "SOURCE_FETCHED": "VERIFYING",
    "SOURCE_REFERENCE_CREATED": "VERIFYING",
    "EVIDENCE_SPANS_CREATED": "VERIFYING",
    "STRUCTURED_EXTRACTION": "VERIFYING",
    "SOURCE_SPAN_SELECTED": "VERIFYING",
    "CLAIM_EXTRACTED": "VERIFYING",
    "CLAIM_NORMALIZATION_RESULT": "VERIFYING",
    "EVIDENCE_RECORDED": "VERIFYING",
    "ELIGIBILITY_EVALUATED": "EVALUATING",
    "HUMAN_REVIEW_NEEDED": "EVALUATING",
    "DECISION_EVALUATED": "DECISION_UPDATED",
    "RUN_TERMINATED": None,
}

TERMINAL_STATES: dict[str, RunState] = {
    "SUFFICIENT_CRITICAL_EVIDENCE": RunState.COMPLETED,
    "HARD_FAIL_CONFIRMED": RunState.COMPLETED,
    "BUDGET_EXHAUSTED": RunState.BUDGET_STOPPED,
    "NO_PROGRESS": RunState.PARTIAL,
    "TOOL_FAILURE_BOUND_REACHED": RunState.PARTIAL,
    "MAX_STEPS": RunState.PARTIAL,
}


class RunEventSink(Protocol):
    """Runtime-neutral observer. The runtime depends on this shape, never on persistence."""

    def trace_event(self, event: TraceEvent, *, mode: str) -> None: ...

    def run_finished(self, result: AgentRunResult) -> None: ...

    def run_failed(self, *, termination_reason: str, provider_state: str | None = None) -> None: ...


class WorkspaceRunCapture:
    """Buffers bounded events and writes one immutable run record at its terminal state.

    Run rows are unique per run id and are never updated, so the record is written once,
    already carrying the state the runtime actually reached.
    """

    def __init__(
        self,
        database: Database,
        *,
        run_id: str,
        mode: str,
        clock=lambda: datetime.now(UTC),
        budget=None,
        opportunity_id: str | None = None,
        opportunity_version: int | None = None,
    ):
        self.database = database
        self.budget = budget
        self.run_id = run_id
        self.mode = str(mode)
        self.clock = clock
        self.opportunity_id = opportunity_id
        self.opportunity_version = opportunity_version
        self._events: list[tuple[str, RunEventPayload, datetime]] = []
        self._started_at: datetime | None = None
        self._persisted = False

    def trace_event(self, event: TraceEvent, *, mode: str) -> None:
        if str(mode) != self.mode:
            raise ValueError("Run event mode does not match the captured run mode")
        occurred_at = self.clock()
        if self._started_at is None:
            self._started_at = occurred_at
        self._events.append((event.event, self._payload(event), occurred_at))

    @staticmethod
    def _payload(event: TraceEvent) -> RunEventPayload:
        """Only bounded, already-public runtime fields cross into persistence."""
        return RunEventPayload(
            reason_code=event.reason_code,
            phase=PHASES.get(event.event),
            source_ids=event.source_ids,
            evidence_ids=event.span_ids,
            count=event.count,
            normalized_field=event.normalized_field,
            normalization_status=event.normalization_status,
        )

    def run_finished(
        self,
        result: AgentRunResult,
        *,
        reserved_cost_usd: Decimal | None = None,
        reported_cost_usd: Decimal | None = None,
    ) -> None:
        self._commit(
            state=TERMINAL_STATES[result.termination_reason],
            termination_reason=result.termination_reason,
            search_calls=result.search_calls,
            fetched_documents=result.fetched_documents,
            official_source_count=result.official_source_count,
            verified_claim_count=len(result.claims),
            reserved_cost_usd=reserved_cost_usd,
            reported_cost_usd=reported_cost_usd,
        )

    def run_failed(
        self,
        *,
        termination_reason: str,
        provider_state: str | None = None,
        state: RunState = RunState.FAILED,
    ) -> None:
        self._commit(
            state=state, termination_reason=termination_reason, provider_state=provider_state
        )

    def _commit(
        self,
        *,
        state: RunState,
        termination_reason: str,
        provider_state: str | None = None,
        search_calls: int = 0,
        fetched_documents: int = 0,
        official_source_count: int = 0,
        verified_claim_count: int = 0,
        reserved_cost_usd: Decimal | None = None,
        reported_cost_usd: Decimal | None = None,
    ) -> None:
        if self._persisted:
            raise RuntimeError("This run is already persisted; run records are immutable")
        if reserved_cost_usd is None and self.budget is not None:
            reserved_cost_usd = self.budget.snapshot().reserved_cost_usd
        completed_at = self.clock()
        started_at = self._started_at or completed_at
        record = RunRecord(
            schema_version="1",
            id=self.run_id,
            version=1,
            created_at=started_at,
            updated_at=completed_at,
            provenance="DOCUMENTED",
            mode=self.mode,
            state=state,
            provider_state=provider_state,
            opportunity_id=self.opportunity_id,
            opportunity_version=self.opportunity_version,
            search_calls=search_calls,
            fetched_documents=fetched_documents,
            official_source_count=official_source_count,
            verified_claim_count=verified_claim_count,
            reserved_cost_usd=reserved_cost_usd or Decimal(0),
            reported_cost_usd=reported_cost_usd or Decimal(0),
            termination_reason=termination_reason,
            started_at=started_at,
            completed_at=completed_at,
        )
        with self.database.transaction() as connection:
            runs = WorkspaceStore(connection).runs
            runs.create_run(record)
            for event_type, payload, occurred_at in self._events:
                runs.append_run_event(
                    self.run_id,
                    event_type=event_type,
                    payload=payload,
                    mode=self.mode,
                    occurred_at=occurred_at,
                )
        self._persisted = True
