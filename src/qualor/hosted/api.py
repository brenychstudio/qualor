"""Hosted controller routes; shared middleware authenticates the proxy before parsing."""

from fastapi import APIRouter, Request

from .contracts import LiveRunAccepted, LiveRunRequest, LiveRunStatus
from .coordinator import LiveRunDenied


def live_run_router():
    router = APIRouter(prefix="/api/v1/live-runs")

    @router.post("", response_model=LiveRunAccepted, status_code=202)
    def start(body: LiveRunRequest, request: Request):
        coordinator = request.app.state.live_runs
        if coordinator is None:
            raise LiveRunDenied("LIVE_RUN_UNAVAILABLE", 503)
        return coordinator.start(body)

    @router.get("/{run_id}", response_model=LiveRunStatus)
    def status(run_id: str, request: Request):
        if len(run_id) > 128:
            raise LiveRunDenied("LIVE_RUN_UNAVAILABLE", 404)
        coordinator = request.app.state.live_runs
        if coordinator is None:
            raise LiveRunDenied("LIVE_RUN_UNAVAILABLE", 503)
        return coordinator.get(run_id)

    return router
