"""Offline repository doctor and synthetic deterministic evaluation."""

import hashlib
import sys
from pathlib import Path

import typer
from pydantic import ValidationError

from qualor.domain.fixture import FixtureInput
from qualor.eligibility import aggregate_eligibility
from qualor.settings import Settings

app = typer.Typer(help="QUALOR bootstrap utilities.", add_completion=False)
CANONICAL_SHA256 = "440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829"


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
