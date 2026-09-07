"""Small task-oriented local routes; all authority is delegated to application services."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from qualor.api_security import require_local_origin

from .read_models import (
    ActivityResponse,
    ApprovalConfirmRequest,
    ApprovalRequest,
    ApprovalView,
    DraftPackView,
    EvidenceSheetView,
    InboxResponse,
    OpportunityWorkspaceResponse,
    PortfolioView,
    ProductError,
    ProfileUpdateRequest,
    ProjectUpdateRequest,
    SessionView,
)

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def workspace_router(*, read_only=False) -> APIRouter:
    router = APIRouter(
        prefix="/api/v1",
        responses={status: {"model": ProductError} for status in (403, 404, 409, 422, 500)},
    )

    @router.get("/inbox", response_model=InboxResponse)
    def inbox(request: Request, limit: Limit = 50, offset: Offset = 0):
        return request.app.state.workspace.inbox(limit=limit, offset=offset)

    @router.get("/portfolio", response_model=PortfolioView)
    def portfolio(request: Request):
        return request.app.state.workspace.portfolio()

    @router.get(
        "/opportunities/{opportunity_id}/workspace", response_model=OpportunityWorkspaceResponse
    )
    def workspace(
        opportunity_id: str,
        request: Request,
        limit: Limit = 50,
        run_offset: Offset = 0,
        approval_offset: Offset = 0,
    ):
        return request.app.state.workspace.workspace(
            opportunity_id, limit=limit, run_offset=run_offset, approval_offset=approval_offset
        )

    @router.get("/opportunities/{opportunity_id}/evidence", response_model=EvidenceSheetView)
    def evidence(
        opportunity_id: str,
        request: Request,
        technical: bool = False,
        limit: Limit = 50,
        proof_offset: Offset = 0,
        claim_offset: Offset = 0,
    ):
        return request.app.state.workspace.evidence(
            opportunity_id,
            technical=technical,
            limit=limit,
            proof_offset=proof_offset,
            claim_offset=claim_offset,
        )

    @router.get("/runs", response_model=ActivityResponse)
    def runs(request: Request, limit: Limit = 50, offset: Offset = 0, event_offset: Offset = 0):
        return request.app.state.workspace.activity(
            limit=limit, offset=offset, event_offset=event_offset
        )

    @router.get("/runs/{run_id}/events", response_model=ActivityResponse)
    def events(run_id: str, request: Request, limit: Limit = 50, offset: Offset = 0):
        return request.app.state.workspace.activity(run_id, limit=limit, offset=offset)

    @router.get("/session", response_model=SessionView)
    def session(request: Request):
        require_local_origin(request)
        return SessionView(read_only=read_only, action_token=request.app.state.action_token)

    @router.get("/approvals/{approval_id}", response_model=ApprovalView)
    def approval(approval_id: str, request: Request):
        return request.app.state.workspace.approval(approval_id)

    @router.get("/draft-packs/{pack_id}", response_model=DraftPackView)
    def pack(pack_id: str, request: Request):
        return request.app.state.workspace.draft_pack(pack_id)

    if not read_only:

        @router.put("/profile", response_model=PortfolioView)
        def update_profile(body: ProfileUpdateRequest, request: Request):
            return request.app.state.workspace.update_profile(body)

        @router.put("/projects/{project_id}", response_model=PortfolioView)
        def update_project(project_id: str, body: ProjectUpdateRequest, request: Request):
            return request.app.state.workspace.update_project(project_id, body)

        @router.post("/opportunities/{opportunity_id}/approvals", response_model=ApprovalView)
        def request_approval(opportunity_id: str, body: ApprovalRequest, request: Request):
            return request.app.state.workspace.request_approval(opportunity_id, body)

        @router.post("/approvals/{approval_id}/confirm", response_model=ApprovalView)
        def confirm(approval_id: str, body: ApprovalConfirmRequest, request: Request):
            return request.app.state.workspace.confirm_approval(approval_id, body)

    return router
