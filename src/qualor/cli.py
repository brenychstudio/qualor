"""Offline repository doctor and synthetic deterministic evaluation."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from qualor.decisions import DecisionFixture, WorkspaceSeedInput, decide_fixture
from qualor.decisions.engine import decide
from qualor.domain.fixture import FixtureInput
from qualor.eligibility import aggregate_eligibility
from qualor.settings import Settings

app = typer.Typer(help="QUALOR bootstrap utilities.", add_completion=False)
CANONICAL_SHA256 = "440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829"


@app.command()
def serve(port: int = typer.Option(8000, min=1, max=65535)) -> None:
    """Serve the local product controller on loopback only."""
    import uvicorn

    from qualor.api import create_app

    typer.echo(f"http://127.0.0.1:{port}")
    uvicorn.run(create_app(), host="127.0.0.1", port=port, access_log=False, log_level="error")


@app.command("run-live-opportunity")
def run_live_opportunity(
    profile: Annotated[Path, typer.Option()],
    mode: str = typer.Option("FIXTURE"),
    gateway_id: str = typer.Option("", envvar="QUALOR_GATEWAY_ID"),
    diagnostic_run_2: bool = typer.Option(
        False, help="Explicit QUALOR-03B3D one-run authorization."
    ),
    workspace_database: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """One explicitly authorized live run; no submission or model-authored verdict."""
    if mode != "LIVE":
        typer.echo("LIVE_REQUIRES_EXPLICIT_MODE", err=True)
        raise typer.Exit(2)
    from qualor.runtime.live_cli import run_command, summary

    try:
        result, metrics = run_command(
            profile,
            gateway_id,
            diagnostic=diagnostic_run_2,
            workspace_database=workspace_database,
        )
    except (ValueError, RuntimeError, OSError):
        typer.echo("LIVE_RUN_FAILED_CLOSED", err=True)
        raise typer.Exit(1) from None
    for key, value in summary(result, metrics).items():
        typer.echo(f"{key}={value}")
    for url in result.citation_urls:
        typer.echo("CITATION=" + json.dumps(url))
    for candidate in result.decision.candidates:
        typer.echo(
            "PROJECT_RESULT="
            + json.dumps(
                {
                    "project_id": candidate.project_id,
                    "eligibility": candidate.eligibility_gate.state,
                    "recommendation": candidate.recommendation,
                    "reason_codes": candidate.reason_codes,
                }
            )
        )


@app.callback()
def main() -> None:
    """QUALOR — Autonomous Opportunity Intelligence."""


@app.command()
def doctor() -> None:
    """Verify this development checkout without contacting external services."""
    python_ok = sys.version_info[:2] == (3, 12)
    canonical = Path(__file__).resolve().parents[2] / "docs" / "00_CANONICAL_BRIEF_UA.md"
    try:
        canonical_ok = hashlib.sha256(canonical.read_bytes()).hexdigest() == CANONICAL_SHA256
    except OSError:
        canonical_ok = False

    configuration_ok = True
    try:
        Settings()
    except ValidationError:
        configuration_ok = False

    typer.echo("QUALOR")
    typer.echo("PHASE=bootstrap")
    typer.echo(f"PYTHON={'PASS' if python_ok else 'BLOCKED'}")
    typer.echo(f"CANONICAL={'PASS' if canonical_ok else 'BLOCKED'}")
    typer.echo("LIVE_MODE=DISABLED")
    typer.echo("PAID_AWS_CALLS=DISABLED")
    if not configuration_ok:
        typer.echo("CONFIGURATION=BLOCKED")
    if not (python_ok and canonical_ok and configuration_ok):
        raise typer.Exit(1)


@app.command("evaluate-fixture")
def evaluate_fixture(fixture_path: Path) -> None:
    """Validate and evaluate an owned synthetic JSON fixture without network access."""
    try:
        fixture = FixtureInput.model_validate_json(fixture_path.read_text(encoding="utf-8"))
        gate = aggregate_eligibility(fixture.rules, fixture.context)
    except (OSError, ValueError):
        typer.echo("INVALID_FIXTURE", err=True)
        raise typer.Exit(2) from None
    typer.echo("MODE=FIXTURE")
    typer.echo(f"ELIGIBILITY={gate.state.value}")
    typer.echo(gate.model_dump_json(indent=2))


@app.command("decide-fixture")
def decide_fixture_file(fixture_path: Path) -> None:
    """Compose an owned synthetic fixture and print a bounded eight-field summary."""
    try:
        fixture = DecisionFixture.model_validate_json(fixture_path.read_text(encoding="utf-8"))
        result = decide_fixture(fixture)
    except (OSError, ValueError):
        typer.echo("INVALID_FIXTURE", err=True)
        raise typer.Exit(2) from None
    selected = result.selected_decision
    # JSON escaping keeps arbitrary project identifiers within one output field.
    best = json.dumps(result.best_project_id, ensure_ascii=True)[1:-1] if selected else "UNRESOLVED"
    fields = (
        ("MODE", "FIXTURE"),
        ("ELIGIBILITY", selected.eligibility_gate.state.value if selected else "UNKNOWN"),
        ("BEST_PROJECT", best),
        (
            "STRATEGY_SCORE",
            selected.strategy_score
            if selected and selected.strategy_score is not None
            else "UNKNOWN",
        ),
        ("CONFLICT", selected.conflict_status.value if selected else "UNKNOWN"),
        ("READINESS", selected.readiness.state.value if selected else "UNKNOWN"),
        ("CAPACITY", selected.capacity.state.value if selected else "UNKNOWN"),
        ("RECOMMENDATION", result.recommendation.value),
    )
    for key, value in fields:
        typer.echo(f"{key}={value}")


# Field names the fixture contract declares temporal. Read from the typed model rather than
# guessed from string shape, so a text operand that merely looks like a date is never moved.
_INSTANT_KEYS = frozenset(
    {
        "created_at",
        "updated_at",
        "evaluated_at",
        "retrieved_at",
        "verified_at",
        "facts_verified_at",
        "last_refresh_failed_at",
    }
)
# Scenario dates that the contract types as date-or-instant.
_SCENARIO_DATE_KEYS = frozenset({"deadlines", "expiry", "submission_dates"})
# Asserted facts whose wrapped `value` is temporal.
_TEMPORAL_FACT_KEYS = frozenset({"incorporation_date"})
# Discriminated scalar operands that carry time.
_TEMPORAL_OPERAND_KINDS = frozenset({"instant", "date"})


def _rebased_observations(payload: dict, now) -> dict:
    """Slide a scenario fixture onto the current clock, preserving every interval.

    A fixture describes a situation, not a moment in history. Left at its authored instants
    the scenario decays: its evidence reads as stale and its evaluation eventually falls
    outside the very eligibility window it was authored inside, so the deterministic verdict
    changes with the calendar. One delta moves every temporal fact the scenario owns, at any
    nesting depth, so ages, ordering, the distance to the deadline and each rule window are
    exactly as authored.

    Only temporal facts move. No eligibility, decision, approval or drafting value is
    touched: those remain the deterministic engines' to produce.
    """
    from datetime import datetime as _datetime

    def parse(value: str) -> "_datetime":
        return _datetime.fromisoformat(value.replace("Z", "+00:00"))

    delta = now - parse(payload["evaluated_at"])

    def shift(value):
        """Move one temporal value, keeping the precision it was authored with."""
        if not isinstance(value, str) or not value:
            return value
        moved = parse(value) + delta
        # A calendar date stays a calendar date; an instant stays an instant.
        return moved.date().isoformat() if len(value) == 10 else (
            moved.isoformat().replace("+00:00", "Z")
        )

    def shift_each(value):
        return [shift(item) for item in value] if isinstance(value, list) else shift(value)

    def rebase(node, key=None):
        if isinstance(node, dict):
            temporal_operand = node.get("kind") in _TEMPORAL_OPERAND_KINDS
            rebased = {}
            for name, value in node.items():
                temporal = name in _INSTANT_KEYS or name in _SCENARIO_DATE_KEYS or (
                    name == "value" and (temporal_operand or key in _TEMPORAL_FACT_KEYS)
                )
                rebased[name] = shift_each(value) if temporal else rebase(value, name)
            return rebased
        if isinstance(node, list):
            return [rebase(item, key) for item in node]
        return node

    return rebase(json.loads(json.dumps(payload)))


@app.command("seed-workspace-fixture")
def seed_workspace_fixture(fixture_path: Path) -> None:
    """Persist one owned FIXTURE scenario or one captured REPLAY source.

    Development tooling for acceptance runs, not a product execution path. It reads a single
    explicit local file, never a URL, and it supplies inputs only: the deterministic engines
    produce the decision, and approval and drafting keep their own authority.

    The two modes differ in exactly one respect, and it is the clock. A FIXTURE describes a
    situation rather than a moment, so it is slid onto the current clock and keeps deciding
    the way it was authored to. A REPLAY is a record of a real source as it actually read at
    a real instant; the product quotes the excerpt that states those instants, so moving them
    would make a displayed deadline disagree with its own citation. REPLAY is therefore
    persisted exactly as captured. LIVE is refused: a local file cannot have been fetched by
    the run reading it.
    """
    from datetime import UTC, datetime

    from qualor.persistence import Database
    from qualor.workspace import WorkspaceStore
    from qualor.workspace.models import RunEventPayload, RunRecord
    from qualor.workspace.versioning import opportunity_semantic_digest

    settings = Settings()
    if settings.qualor_env != "development":
        typer.echo("SEED_REQUIRES_DEVELOPMENT_ENVIRONMENT", err=True)
        raise typer.Exit(2)
    now = datetime.now(UTC)
    try:
        # An explicit local file only. A URL is not a path this command will read.
        text = Path(fixture_path).read_text(encoding="utf-8")
        payload = json.loads(text)
        # Read before rebasing, because the declared mode is what decides whether to rebase
        # at all. An unusable declaration falls through to the same refusal as any other
        # malformed envelope rather than defaulting to a mode the file did not claim.
        if not isinstance(payload, dict) or payload.get("mode") not in {"FIXTURE", "REPLAY"}:
            raise ValueError("SEED_MODE_NOT_ACCEPTED")
        if payload["mode"] == "FIXTURE":
            payload = _rebased_observations(payload, now)
        # WorkspaceSeedInput admits FIXTURE and REPLAY only, so a LIVE claim fails here too.
        fixture = WorkspaceSeedInput.model_validate(payload)
    except (OSError, ValueError, KeyError, TypeError):
        typer.echo("INVALID_FIXTURE", err=True)
        raise typer.Exit(2) from None

    mode = fixture.mode
    result = decide(fixture)
    decision = result.selected_decision
    database = Database(settings.database_path)
    database.path.parent.mkdir(parents=True, exist_ok=True)
    with database.transaction() as connection:
        store = WorkspaceStore(connection)
        store.profiles.put_founder(fixture.founder)
        for entry in fixture.projects:
            store.projects.put_project(entry.project)
        store.opportunities.put_opportunity_version(
            fixture.opportunity, content_hash=opportunity_semantic_digest(fixture.opportunity)
        )
        for evidence in fixture.evidence:
            store.evidence.put_evidence(
                evidence, fixture.opportunity.id, fixture.opportunity.version
            )
        if decision is not None:
            store.decisions.put_decision(decision, founder_profile_id=fixture.founder.id)
        store.runs.create_run(
            RunRecord(
                schema_version="1",
                id=f"seed-{fixture.opportunity.id}",
                version=1,
                created_at=now,
                updated_at=now,
                provenance="DOCUMENTED",
                mode=mode,
                state="COMPLETED",
                opportunity_id=fixture.opportunity.id,
                opportunity_version=fixture.opportunity.version,
                decision_id=decision.id if decision else None,
                decision_version=decision.version if decision else None,
                started_at=now,
                completed_at=now,
                termination_reason="SUFFICIENT_CRITICAL_EVIDENCE",
            )
        )
        for event in ("OPPORTUNITY_DISCOVERED", "EVIDENCE_RECORDED", "DECISION_UPDATED"):
            store.runs.append_run_event(
                f"seed-{fixture.opportunity.id}",
                event_type=event,
                payload=RunEventPayload(count=1),
                mode=mode,
                occurred_at=now,
            )
    typer.echo(f"MODE={mode}")
    typer.echo(f"OBSERVED_AT={fixture.evaluated_at.isoformat()}")
    typer.echo(f"OPPORTUNITY={fixture.opportunity.id}")
    typer.echo(f"EVIDENCE_RECORDS={len(fixture.evidence)}")
    typer.echo(f"ELIGIBILITY={decision.eligibility_gate.state.value if decision else 'UNKNOWN'}")
    typer.echo(f"RECOMMENDATION={result.recommendation.value}")


@app.command("search-live")
def search_live(
    query: str,
    mode: str = typer.Option("FIXTURE"),
    gateway_id: str = typer.Option("", envvar="QUALOR_GATEWAY_ID"),
    max_results: int = typer.Option(5),
    include_domain: Annotated[list[str] | None, typer.Option()] = None,
) -> None:
    """Explicit bounded live discovery; preserves citations, never evaluates eligibility."""
    if mode != "LIVE":
        typer.echo("LIVE_REQUIRES_EXPLICIT_MODE", err=True)
        raise typer.Exit(2)
    from dataclasses import asdict

    from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
    from qualor.runtime.providers import SearchRequest
    from qualor.runtime.search import WEB_SEARCH_TASK_COST_CAP_USD, AgentCoreSearchProvider
    from qualor.runtime.search_transport import open_gateway_transport

    try:
        request = SearchRequest(
            query,
            max_results=max_results,
            filters={"domainFilter": {"include": include_domain}} if include_domain else None,
        )
        budget = LiveBudgetGuard(
            LiveBudgetPolicy(search_max_calls=2, cost_cap_usd=WEB_SEARCH_TASK_COST_CAP_USD)
        )
        with open_gateway_transport(mode=mode, gateway_id=gateway_id) as transport:
            provider = AgentCoreSearchProvider(mode=mode, transport=transport, budget=budget)
            results = provider.search(request)
    except (ValueError, RuntimeError, OSError):
        # SDK/HTTP errors may contain private endpoint or credential details.
        typer.echo("LIVE_SEARCH_FAILED_CLOSED", err=True)
        raise typer.Exit(1) from None
    typer.echo("MODE=LIVE")
    typer.echo("PROVIDER=AGENTCORE_WEB_SEARCH")
    typer.echo("QUERY=" + json.dumps(query, ensure_ascii=True))
    typer.echo(f"RESULT_COUNT={len(results)}")
    typer.echo(f"CITATION_COUNT={sum(c.citable_for_user_output for c in results)}")
    for candidate in results:
        # Surface uncited rows only as unavailable, not as attributed search content.
        if candidate.citable_for_user_output:
            typer.echo(json.dumps(asdict(candidate), default=str, ensure_ascii=True))
        else:
            typer.echo("CITABLE_FOR_USER_OUTPUT=NO; HARD_EVIDENCE_ELIGIBLE=NO")
