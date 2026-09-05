"""Local development API; fixture evaluation has no provider or agent initialization."""

from typing import Literal

from fastapi import FastAPI, HTTPException

from qualor.decisions import DecisionFixture, DecisionResult, decide_fixture
from qualor.domain.base import Contract
from qualor.domain.enums import GateState
from qualor.domain.fixture import FixtureInput
from qualor.domain.rules import CoverageEntry, RuleEvaluation
from qualor.eligibility import aggregate_eligibility
from qualor.settings import Settings

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "qualor", "status": "ok", "phase": "bootstrap"}


class FixtureResponse(Contract):
    mode: Literal["FIXTURE"] = "FIXTURE"
    eligibility: GateState
    evaluations: tuple[RuleEvaluation, ...]
    coverage: tuple[CoverageEntry, ...]
    missing_information: tuple[str, ...]


@app.post("/dev/evaluate-fixture", response_model=FixtureResponse)
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


@app.post("/dev/decide-fixture", response_model=DecisionResult)
def decide_fixture_json(fixture: DecisionFixture) -> DecisionResult:
    """Development-only explicit JSON facts; no server path or external action."""
    if Settings().qualor_env != "development":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return decide_fixture(fixture)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid decision fixture structure") from None
