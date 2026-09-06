"""Operator-only live runner. Reports are bounded and local, never agent-writable tools."""

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from .budget import LiveBudgetGuard, LiveBudgetPolicy
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


def execute_live(inputs: StudioInput, gateway_id: str, *, diagnostic=False):
    from .agent import live_extractor, live_model, run_agent
    from .loop import OpportunityRun
    from .search import AgentCoreSearchProvider
    from .search_transport import open_gateway_transport
    from .sources import OfficialSourceFetcher

    budget = LiveBudgetGuard(
        diagnostic_policy()
        if diagnostic
        else LiveBudgetPolicy(
            inference_max_calls=6, cost_cap_usd=Decimal(".20"), authorization="QUALOR_03B3"
        )
    )
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
        )
        result, metrics = run_agent(run, model=model)
        metrics["gateway_mcp_calls"] = transport.http_calls
        metrics["budget"] = asdict(budget.snapshot())
    return result, metrics


def run_command(profile: Path, gateway_id: str, *, diagnostic=False):
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
    result, metrics = execute_live(inputs, gateway_id, diagnostic=diagnostic)
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
