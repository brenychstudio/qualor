"""Bounded public LIVE controller contracts; internal runtime objects never serialize here."""

from typing import Literal

from pydantic import Field, StrictStr

from qualor.decisions.model import Recommendation
from qualor.domain.base import Contract, UtcInstant

LiveStatus = Literal[
    "STARTING", "RESEARCHING", "EVALUATING", "COMPLETED", "FAILED", "BUDGET_STOPPED"
]
LiveErrorCode = Literal[
    "LIVE_RUN_BUSY",
    "LIVE_RUN_LIMIT_REACHED",
    "LIVE_RUN_COOLDOWN",
    "LIVE_RUN_UNAVAILABLE",
    "LIVE_PERSISTENCE_FAILED",
    "LIVE_PROVIDER_FAILED",
    "INTERNAL_LIVE_RUN_FAILURE",
    "LIVE_RUN_INCOMPLETE",
    "BUDGET_STOPPED",
]


class LiveRunRequest(Contract):
    official_url: StrictStr = Field(min_length=1, max_length=2048)
    goal: StrictStr | None = Field(default=None, min_length=1, max_length=180)


class LiveRunAccepted(Contract):
    run_id: StrictStr
    status: Literal["STARTING"] = "STARTING"


class LiveRunStatus(Contract):
    run_id: StrictStr
    status: LiveStatus
    mode: Literal["LIVE"] = "LIVE"
    started_at: UtcInstant
    completed_at: UtcInstant | None = None
    opportunity_id: StrictStr | None = None
    recommendation: Recommendation | None = None
    termination_reason: (
        Literal[
            "SUFFICIENT_CRITICAL_EVIDENCE",
            "HARD_FAIL_CONFIRMED",
            "BUDGET_EXHAUSTED",
            "NO_PROGRESS",
            "TOOL_FAILURE_BOUND_REACHED",
            "MAX_STEPS",
            "PROVIDER_DISCONNECTED",
            "INTERNAL_LIVE_RUN_FAILURE",
        ]
        | None
    ) = None
    error_code: LiveErrorCode | None = None


class LiveRunError(Contract):
    code: LiveErrorCode
