"""Offline repository doctor and synthetic deterministic evaluation."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from qualor.decisions import DecisionFixture, decide_fixture
from qualor.domain.fixture import FixtureInput
from qualor.eligibility import aggregate_eligibility
from qualor.settings import Settings

app = typer.Typer(help="QUALOR bootstrap utilities.", add_completion=False)
CANONICAL_SHA256 = "440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829"


@app.command("run-live-opportunity")
def run_live_opportunity(
    profile: Annotated[Path, typer.Option()],
    mode: str = typer.Option("FIXTURE"),
    gateway_id: str = typer.Option("", envvar="QUALOR_GATEWAY_ID"),
) -> None:
    """One explicitly authorized live run; no submission or model-authored verdict."""
    if mode != "LIVE":
        typer.echo("LIVE_REQUIRES_EXPLICIT_MODE", err=True)
        raise typer.Exit(2)
    from qualor.runtime.live_cli import run_command, summary

    try:
        result, metrics = run_command(profile, gateway_id)
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
