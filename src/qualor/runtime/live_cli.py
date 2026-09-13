"""Operator-only live runner. Reports are bounded and local, never agent-writable tools."""

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .budget import (
    QUALOR_03B3_INFERENCE_MAX_CALLS_PER_RUN,
    LiveBudgetGuard,
    LiveBudgetPolicy,
)
from .run_models import StudioInput


def diagnostic_policy() -> LiveBudgetPolicy:
    return LiveBudgetPolicy(
        inference_max_calls=6,
        search_max_calls=3,
        fetch_max_documents=5,
        cost_cap_usd=Decimal("0.15"),
        model_max_output_tokens=512,
        authorization="QUALOR_03B3",
    )


def live_budget(diagnostic: bool = False) -> LiveBudgetGuard:
    return LiveBudgetGuard(
        diagnostic_policy()
        if diagnostic
        else LiveBudgetPolicy(
            inference_max_calls=QUALOR_03B3_INFERENCE_MAX_CALLS_PER_RUN,
            cost_cap_usd=Decimal(".20"),
            authorization="QUALOR_03B3",
        )
    )


def workspace_run_capture(
    database_path: Path,
    *,
    inputs: StudioInput,
    budget=None,
    run_id: str | None = None,
):
    """Build the persistence sink only when workspace persistence is enabled."""
    from qualor.persistence import Database
    from qualor.workspace.run_capture import WorkspaceRunCapture

    return WorkspaceRunCapture(
        Database(database_path),
        run_id=run_id or uuid4().hex,
        mode="LIVE",
        budget=budget,
        inputs=inputs,
    )


def execute_live(inputs: StudioInput, gateway_id: str, *, diagnostic=False, sink=None, budget=None):
    from .agent import live_extractor, live_model, run_agent
    from .loop import OpportunityRun
    from .search import AgentCoreSearchProvider
    from .search_transport import open_gateway_transport
    from .sources import OfficialSourceFetcher

    budget = budget or live_budget(diagnostic)
    try:
        with open_gateway_transport(mode="LIVE", gateway_id=gateway_id) as transport:
            search = AgentCoreSearchProvider(mode="LIVE", transport=transport, budget=budget)
            fetcher = OfficialSourceFetcher(
                mode="LIVE", allowed_hosts=inputs.allowed_hosts, budget=budget
            )
            model = live_model(budget)
            run = OpportunityRun(
                inputs,
                mode="LIVE",
                search=search,
                fetcher=fetcher,
                extractor=live_extractor(model),
                budget=budget,
                sink=sink,
                opportunity_version_resolver=(
                    getattr(sink, "resolve_opportunity_version", None)
                    if sink is not None
                    else None
                ),
            )
            result, metrics = run_agent(run, model=model)
            metrics["gateway_mcp_calls"] = transport.http_calls
            metrics["budget"] = asdict(budget.snapshot())
        return result, metrics
    except (ValueError, RuntimeError, OSError):
        # A live provider that never connected is recorded as a degraded LIVE run, not a success.
        if sink is not None:
            sink.run_failed(
                termination_reason="PROVIDER_DISCONNECTED",
                provider_state="DISCONNECTED_LIVE_PROVIDER",
            )
        raise


def run_command(profile: Path, gateway_id: str, *, diagnostic=False, workspace_database=None):
    data = profile.read_bytes()
    if len(data) > 100_000:
        raise ValueError("Profile input too large")
    inputs = StudioInput.model_validate_json(data)
    report = Path(
        ".qualor/local/qualor-03b3d-live-run-2.json"
        if diagnostic
        else ".qualor/local/qualor-03b3-live-run.json"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive marker survives interruption. No silent repeated paid dogfood runs.
    with report.open("x", encoding="utf-8") as file:
        json.dump(
            {"status": "STARTED", "task_cost_reserved_usd": "0.15" if diagnostic else "0.20"}, file
        )
    budget = live_budget(diagnostic)
    sink = (
        workspace_run_capture(workspace_database, inputs=inputs, budget=budget)
        if workspace_database is not None
        else None
    )
    try:
        result, metrics = execute_live(
            inputs, gateway_id, diagnostic=diagnostic, sink=sink, budget=budget
        )
    except (ValueError, RuntimeError, OSError):
        if sink is not None:
            sink.require_persisted()
        raise
    if sink is not None:
        sink.require_persisted()
    report.write_text(
        json.dumps(
            {"result": result.model_dump(mode="json"), "metrics": metrics}, default=str, indent=2
        ),
        encoding="utf-8",
    )
    return result, metrics


def summary(result, metrics):
    decision = result.decision
    selected = decision.selected_decision
    return {
        "MODE": result.mode,
        "AGENT": "STRANDS",
        "MODEL": "global.anthropic.claude-sonnet-4-6",
        "SEARCH_CALLS": result.search_calls,
        "FETCHED_DOCUMENTS": result.fetched_documents,
        "EVIDENCE_RECORDS": len(result.claims),
        "ELIGIBILITY": decision.eligibility or "UNRESOLVED_PORTFOLIO",
        "BEST_PROJECT": decision.best_project_id or "UNRESOLVED",
        "STRATEGY_SCORE": selected.strategy_score
        if selected and selected.strategy_score is not None
        else "UNKNOWN",
        "CONFLICT": selected.conflict_status if selected else "REVIEW_REQUIRED",
        "EFFORT_RANGE": f"{selected.effort.min_total}-{selected.effort.max_total}"
        if selected and selected.effort.min_total is not None
        else "UNKNOWN",
        "READINESS": selected.readiness.state if selected else "UNKNOWN",
        "RECOMMENDATION": decision.recommendation,
        "OFFICIAL_SOURCE_COUNT": result.official_source_count,
        "CITATION_COUNT": len(result.citation_urls),
        "TERMINATION_REASON": result.termination_reason,
        "STRANDS_TOOL_CALLS": metrics["strands_tool_calls"],
        "BEDROCK_CALLS": metrics["budget"]["inference_calls"],
        "COST_RESERVED_OR_RECONCILED_USD": str(metrics["budget"]["reserved_cost_usd"]),
    }
