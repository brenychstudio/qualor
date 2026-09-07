"""Internal durable workspace contracts."""

from .models import (
    ApprovalAction,
    ApprovalRecord,
    ApprovalState,
    DraftJobRecord,
    DraftJobState,
    DraftPack,
    DraftPackSection,
    RunEvent,
    RunRecord,
    RunState,
)

__all__ = [
    "ApprovalAction",
    "ApprovalRecord",
    "ApprovalState",
    "DraftJobRecord",
    "DraftJobState",
    "DraftPack",
    "DraftPackSection",
    "OpportunityWorkspace",
    "RunEvent",
    "RunRecord",
    "RunState",
    "WorkspaceStore",
]


def __getattr__(name: str):
    if name in {"OpportunityWorkspace", "WorkspaceStore"}:
        from .store import OpportunityWorkspace, WorkspaceStore

        return {"OpportunityWorkspace": OpportunityWorkspace, "WorkspaceStore": WorkspaceStore}[
            name
        ]
    raise AttributeError(name)
