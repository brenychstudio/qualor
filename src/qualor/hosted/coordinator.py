"""One owned worker, bounded process-local admission, persisted terminal authority."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from uuid import uuid4

from qualor.runtime.budget import BudgetLimitExceeded
from qualor.runtime.live_cli import execute_live, live_budget
from qualor.runtime.mode import ProviderBoundaryError
from qualor.runtime.run_models import StudioInput
from qualor.workspace import WorkspaceStore
from qualor.workspace.run_capture import WorkspaceRunCapture

from .contracts import LiveRunAccepted, LiveRunStatus
from .inputs import DEFAULT_GOAL, admit_url


class LiveRunDenied(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.code, self.status = code, status


class _ProgressCapture(WorkspaceRunCapture):
    def __init__(self, *args, progress, **kwargs):
        super().__init__(*args, **kwargs)
        self._progress = progress

    def trace_event(self, event, *, mode):
        super().trace_event(event, mode=mode)
        if event.event in {"SEARCH_REQUESTED", "SOURCE_FETCHED", "STRUCTURED_EXTRACTION"}:
            self._progress("RESEARCHING")
        elif event.event in {"ELIGIBILITY_EVALUATED", "DECISION_EVALUATED"}:
            self._progress("EVALUATING")


class LiveRunCoordinator:
    def __init__(
        self,
        database,
        profile,
        settings,
        *,
        runner=None,
        resolver=None,
        clock=lambda: datetime.now(UTC),
        monotonic_clock=monotonic,
    ):
        self.database, self.profile, self.settings = database, profile, settings
        self._runner = runner or execute_live
        self._resolver = resolver
        self._clock, self._monotonic = clock, monotonic_clock
        self._lock = Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qualor-live")
        self._active = None
        self._jobs = {}
        self._accepted = 0
        self._last_finished = None
        self._closed = False

    def close(self):
        # Do not release the slot while a running physical provider call still exists.
        with self._lock:
            self._closed = True
        self._worker.shutdown(wait=True, cancel_futures=False)

    def start(self, request):
        with self._lock:
            self._require_capacity()
        # URL/DNS admission performs no paid call. Physical fetch retains its pinned-IP
        # revalidation, including every redirect; this precheck grants no source authority.
        try:
            kwargs = {} if self._resolver is None else {"resolver": self._resolver}
            url, host = admit_url(request.official_url, **kwargs)
        except (ValueError, OSError, UnicodeError):
            raise LiveRunDenied("INVALID_REQUEST", 422) from None
        inputs = StudioInput(
            schema_version="1",
            sanitized=True,
            goal=DEFAULT_GOAL + (" Context: " + request.goal if request.goal else ""),
            official_url=url,
            allowed_hosts=(host,),
            founder=self.profile.founder,
            projects=self.profile.projects,
        )
        with self._lock:
            self._require_capacity()
            run_id = uuid4().hex
            self._jobs[run_id] = LiveRunStatus(
                run_id=run_id, status="STARTING", started_at=self._clock()
            )
            self._active = run_id
            self._accepted += 1
            try:
                self._worker.submit(self._execute, run_id, inputs)
            except RuntimeError:
                self._active = None
                self._jobs.pop(run_id)
                raise LiveRunDenied("LIVE_RUN_UNAVAILABLE", 503) from None
        # Always return admission state, even if a controlled run finishes immediately.
        return LiveRunAccepted(run_id=run_id)

    def _require_capacity(self):
        if self._closed or not self.settings.qualor_hosted_live_enabled:
            raise LiveRunDenied("LIVE_RUN_UNAVAILABLE", 503)
        if self._active is not None:
            raise LiveRunDenied("LIVE_RUN_BUSY", 409)
        if self._accepted >= self.settings.qualor_live_max_runs:
            raise LiveRunDenied("LIVE_RUN_LIMIT_REACHED", 429)
        if (
            self._last_finished is not None
            and self._monotonic() - self._last_finished < self.settings.qualor_live_cooldown_seconds
        ):
            raise LiveRunDenied("LIVE_RUN_COOLDOWN", 429)

    def _progress(self, run_id, status):
        with self._lock:
            if self._active == run_id:
                self._jobs[run_id] = self._jobs[run_id].model_copy(update={"status": status})

    def _failure(self, run_id, code, *, budget=False):
        with self._lock:
            self._jobs[run_id] = self._jobs[run_id].model_copy(
                update={
                    "status": "BUDGET_STOPPED" if budget else "FAILED",
                    "completed_at": self._clock(),
                    "error_code": code,
                }
            )

    def _execute(self, run_id, inputs):
        capture = None
        try:
            budget = live_budget()
            capture = _ProgressCapture(
                self.database,
                run_id=run_id,
                mode="LIVE",
                inputs=inputs,
                budget=budget,
                clock=self._clock,
                progress=lambda status: self._progress(run_id, status),
            )
            execution_error = None
            try:
                self._runner(inputs, self.settings.qualor_gateway_id, sink=capture, budget=budget)
            except Exception as exc:  # noqa: BLE001 - no provider text crosses the public boundary
                execution_error = exc
                # execute_live can already have captured a setup failure. Never write twice.
                if capture.persistence_error is None:
                    with self.database.transaction() as connection:
                        recorded = WorkspaceStore(connection).runs.current(run_id)
                    if recorded is None:
                        is_budget = isinstance(exc, BudgetLimitExceeded)
                        capture.run_failed(
                            termination_reason="BUDGET_EXHAUSTED"
                            if is_budget
                            else (
                                "PROVIDER_DISCONNECTED"
                                if isinstance(exc, ProviderBoundaryError)
                                else "INTERNAL_LIVE_RUN_FAILURE"
                            ),
                            state="BUDGET_STOPPED" if is_budget else "FAILED",
                        )
            capture.require_persisted()
            if execution_error is not None:
                self._failure(
                    run_id,
                    "BUDGET_STOPPED"
                    if isinstance(execution_error, BudgetLimitExceeded)
                    else "LIVE_PROVIDER_FAILED"
                    if isinstance(execution_error, ProviderBoundaryError)
                    else "INTERNAL_LIVE_RUN_FAILURE",
                    budget=isinstance(execution_error, BudgetLimitExceeded),
                )
            else:
                terminal = self._persisted_status(run_id)
                if terminal is None:
                    raise RuntimeError("Persisted terminal authority is unavailable")
                with self._lock:
                    self._jobs[run_id] = terminal
        except Exception:  # noqa: BLE001 - persistence failure is deliberately bounded
            self._failure(
                run_id,
                "INTERNAL_LIVE_RUN_FAILURE" if capture is None else "LIVE_PERSISTENCE_FAILED",
            )
        finally:
            with self._lock:
                self._active = None
                self._last_finished = self._monotonic()

    def _persisted_status(self, run_id):
        with self.database.transaction() as connection:
            store = WorkspaceStore(connection)
            run = store.runs.current(run_id)
            if run is None or run.mode != "LIVE":
                return None
            base = dict(
                run_id=run_id,
                started_at=run.started_at or run.created_at,
                completed_at=run.completed_at,
            )
            if run.state == "COMPLETED":
                if run.opportunity_id is None or run.decision_id is None:
                    raise RuntimeError("Completed run lacks graph authority")
                opportunity = store.opportunities.get_opportunity_version(
                    run.opportunity_id, run.opportunity_version
                )
                decision = store.decisions.get_decision(run.decision_id, run.decision_version)
                if (
                    opportunity is None
                    or decision is None
                    or (decision.opportunity_id, decision.opportunity_version)
                    != (opportunity.id, opportunity.version)
                    or not store.evidence.list_for_opportunity(opportunity.id, opportunity.version)
                ):
                    raise RuntimeError("Completed graph authority is unavailable")
                return LiveRunStatus(
                    **base,
                    status="COMPLETED",
                    opportunity_id=opportunity.id,
                    recommendation=decision.recommendation,
                    termination_reason=run.termination_reason,
                )
            if run.state == "BUDGET_STOPPED":
                return LiveRunStatus(
                    **base,
                    status="BUDGET_STOPPED",
                    error_code="BUDGET_STOPPED",
                    termination_reason="BUDGET_EXHAUSTED",
                )
            code = (
                "LIVE_PROVIDER_FAILED"
                if run.termination_reason in {"PROVIDER_DISCONNECTED", "TOOL_FAILURE_BOUND_REACHED"}
                else "INTERNAL_LIVE_RUN_FAILURE"
                if run.state == "FAILED"
                else "LIVE_RUN_INCOMPLETE"
            )
            return LiveRunStatus(**base, status="FAILED", error_code=code)

    def get(self, run_id):
        with self._lock:
            transient = self._jobs.get(run_id)
            if transient is not None and transient.status != "COMPLETED":
                return transient
        try:
            persisted = self._persisted_status(run_id)
        except Exception:  # noqa: BLE001 - no database details in API
            raise LiveRunDenied("LIVE_PERSISTENCE_FAILED", 503) from None
        if persisted is None:
            raise LiveRunDenied("LIVE_RUN_UNAVAILABLE", 404)
        return persisted
