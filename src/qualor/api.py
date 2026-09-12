"""Explicit local/hosted API boundaries; provider execution requires hosted admission."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from qualor.decisions import DecisionFixture, DecisionResult, decide_fixture
from qualor.domain.base import Contract
from qualor.domain.enums import GateState
from qualor.domain.fixture import FixtureInput
from qualor.domain.rules import CoverageEntry, RuleEvaluation
from qualor.eligibility import aggregate_eligibility
from qualor.settings import Settings

fixture_router = APIRouter()


@fixture_router.get("/health")
def health() -> dict[str, str]:
    return {"service": "qualor", "status": "ok", "phase": "bootstrap"}


class FixtureResponse(Contract):
    mode: Literal["FIXTURE"] = "FIXTURE"
    eligibility: GateState
    evaluations: tuple[RuleEvaluation, ...]
    coverage: tuple[CoverageEntry, ...]
    missing_information: tuple[str, ...]


@fixture_router.post("/dev/evaluate-fixture", response_model=FixtureResponse)
def evaluate_fixture(fixture: FixtureInput) -> FixtureResponse:
    if Settings().qualor_env != "development":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        gate = aggregate_eligibility(fixture.rules, fixture.context)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid fixture rule structure") from None
    return FixtureResponse(
        eligibility=gate.state,
        evaluations=gate.evaluations,
        coverage=gate.critical_coverage,
        missing_information=gate.missing_information,
    )


@fixture_router.post("/dev/decide-fixture", response_model=DecisionResult)
def decide_fixture_json(fixture: DecisionFixture) -> DecisionResult:
    """Development-only explicit JSON facts; no server path or external action."""
    if Settings().qualor_env != "development":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return decide_fixture(fixture)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid decision fixture structure") from None


def create_app(
    settings: Settings | None = None,
    *,
    actor_id="local-owner",
    policy_versions=None,
    mode="FIXTURE",
    clock=lambda: datetime.now(UTC),
    live_runner=None,
    live_resolver=None,
) -> FastAPI:
    """Construct routes without creating a database or initializing a provider."""
    from qualor.api_security import require_action, require_hosted_proxy
    from qualor.decisions.model import PolicyVersions
    from qualor.persistence import Database
    from qualor.workspace.api import workspace_router
    from qualor.workspace.approval import ApprovalDenied, ApprovalService
    from qualor.workspace.drafting import DraftingDenied
    from qualor.workspace.read_models import ProductError
    from qualor.workspace.service import ProductFailure, WorkspaceService

    config = settings or Settings()
    hosted = config.qualor_security_mode == "HOSTED_DEMO"

    @asynccontextmanager
    async def lifespan(application):
        database = Database(config.database_path)
        # Explicit startup initialization; individual service transactions own and
        # close their connections. No connection spans offline author execution.
        with database.transaction():
            pass
        application.state.live_runs = None
        if hosted:
            from qualor.hosted.coordinator import LiveRunCoordinator
            from qualor.hosted.inputs import load_demo_profile
            from qualor.workspace import WorkspaceStore

            profile = load_demo_profile(config.qualor_demo_profile_path)
            # A hosted process must never serve an owner's local database by accident.
            with database.transaction() as connection:
                store = WorkspaceStore(connection)
                # This demo has one immutable founder/project snapshot. Checking only
                # latest versions would leave historical decision-bound private facts
                # readable through the existing Evidence API.
                if (
                    connection.execute("SELECT COUNT(*) FROM founder_profiles").fetchone()[0] > 1
                    or connection.execute("SELECT COUNT(*) FROM project_profiles").fetchone()[0] > 1
                    or any(item != profile.founder for item in store.profiles.list_current())
                    or any(
                        item != profile.projects[0].project
                        for item in store.projects.list_current()
                    )
                ):
                    raise RuntimeError("HOSTED_DEMO_DATABASE_REQUIRES_SANITIZED_PROFILE")
            application.state.live_runs = LiveRunCoordinator(
                database, profile, config, runner=live_runner, resolver=live_resolver, clock=clock
            )
        policies = policy_versions or PolicyVersions(
            eligibility=1, matching=1, effort=1, conflicts=1, strategy=1, decisions=1
        )
        approvals = ApprovalService(
            database,
            actor_id=profile.founder.id if hosted else actor_id,
            policy_versions=policies,
            mode="LIVE" if hosted else mode,
        )
        application.state.workspace = WorkspaceService(database, approvals=approvals, clock=clock)
        try:
            yield
        finally:
            if application.state.live_runs is not None:
                from starlette.concurrency import run_in_threadpool

                await run_in_threadpool(application.state.live_runs.close)

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    application.state.settings = config
    application.state.action_token = (
        None if hosted or config.qualor_read_only_demo else config.new_action_token()
    )

    def bounded(code, status):
        try:
            error = ProductError(code=code)
        except ValueError:
            error = ProductError(code="INTERNAL_ERROR")
            status = 500
        return JSONResponse(
            error.model_dump(mode="json"), status_code=status, headers={"Cache-Control": "no-store"}
        )

    @application.middleware("http")
    async def product_boundary(request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        try:
            if hosted:
                require_hosted_proxy(request)
                segments = request.url.path.strip("/").split("/")
                if segments[2:3] in (
                    ["session"],
                    ["portfolio"],
                    ["approvals"],
                    ["draft-packs"],
                ) or (
                    request.method not in {"GET", "HEAD", "OPTIONS"}
                    and request.url.path != "/api/v1/live-runs"
                ):
                    return bounded("NOT_FOUND", 404)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                if config.qualor_read_only_demo:
                    return bounded("NOT_FOUND", 404)
                if not hosted:
                    require_action(request)
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        except ProductFailure as exc:
            return bounded(exc.code, exc.status)
        except ValidationError as exc:
            if any(error["type"] == "too_long" for error in exc.errors(include_input=False)):
                return bounded("READ_LIMIT_EXCEEDED", 409)
            return bounded("INTERNAL_ERROR", 500)
        except Exception:
            return bounded("INTERNAL_ERROR", 500)

    @application.exception_handler(ProductFailure)
    async def product_failure(request, exc):
        return bounded(exc.code, exc.status)

    @application.exception_handler(ApprovalDenied)
    async def approval_failure(request, exc):
        return bounded(exc.reason.value, 404 if exc.reason == "NOT_FOUND" else 409)

    @application.exception_handler(DraftingDenied)
    async def drafting_failure(request, exc):
        return bounded(exc.reason, 409)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path.startswith("/api/"):
            return bounded("INVALID_REQUEST", 422)
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, exc)

    @application.exception_handler(StarletteHTTPException)
    async def http_failure(request, exc):
        if request.url.path.startswith("/api/"):
            return bounded(
                "NOT_FOUND" if exc.status_code == 404 else "INVALID_REQUEST", exc.status_code
            )
        from fastapi.exception_handlers import http_exception_handler

        return await http_exception_handler(request, exc)

    if hosted:
        from qualor.hosted.api import live_run_router
        from qualor.hosted.coordinator import LiveRunDenied

        @application.exception_handler(LiveRunDenied)
        async def live_denied(request, exc):
            return JSONResponse(
                {"code": exc.code}, status_code=exc.status, headers={"Cache-Control": "no-store"}
            )

        application.add_api_route("/health", health, methods=["GET"])
        application.include_router(live_run_router())
    else:
        application.include_router(fixture_router)
    application.include_router(workspace_router(read_only=hosted or config.qualor_read_only_demo))
    # Last installed middleware wraps guard errors as well as successful responses.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[] if hosted else list(config.qualor_allowed_origins),
        allow_methods=["GET", "PUT", "POST"],
        allow_headers=["Content-Type", "X-QUALOR-Action-Token"],
    )
    return application


app = create_app()
