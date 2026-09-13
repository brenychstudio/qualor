"""Controlled hosted LIVE approval backend; no AWS transport or fixture/replay seeding."""

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import qualor.hosted.inputs as hosted_inputs
from qualor.api import create_app
from qualor.conflicts import ConflictRule
from qualor.decisions.engine import decide
from qualor.decisions.fixture import DecisionInput, ProjectDecisionInput
from qualor.domain.evidence import EvidenceRecord
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.domain.rules import RuleCandidate
from qualor.effort import EffortAssumptions, ParticipationCosts
from qualor.runtime.claims import ExtractedClaim
from qualor.runtime.extraction import BedrockClaimExtractor
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.providers import SearchCandidate
from qualor.runtime.run_models import (
    AgentRunResult,
    RuntimeDecisionBundle,
    SourceCitation,
    StudioInput,
)
from qualor.runtime.search import AgentCoreSearchProvider
from qualor.runtime.sources import OfficialSourceFetcher
from qualor.settings import Settings

URL = "https://example.org/official-rules"
DEADLINE = datetime(2030, 6, 1, 17, tzinfo=UTC)
MATERIALS = (
    "REPOSITORY",
    "LICENSE",
    "DEMO",
    "ARCHITECTURE_DIAGRAM",
    "TECHNICAL_INTEGRATION",
    "NARRATIVE",
    "PUBLIC_AVAILABILITY",
    "OTHER",
)
CLAUSES = {
    "DEADLINE": "Entries are open through 2030-06-01T17:00:00Z.",
    "ENTRANT_TYPE": "Teams must have at least one member.",
    "GEOGRAPHY": "Entrants must reside in Spain.",
    "LEGAL_ENTITY": "Entrants must be incorporated companies.",
    "PROJECT_POLICY": "Projects must be new.",
    "LICENSE": "Entries must declare an MIT license.",
    "REQUIRED_TECHNOLOGY": "Projects must use Python.",
    "FINANCIAL_SUPPORT": "Entries with zero sponsor support qualify.",
    "REWARD_CONDITIONS": "Reward conditions require an attendance commitment.",
    "conflict_NEW_PROJECT": "New projects are permitted.",
    "conflict_EXCLUSIVE_SUBMISSION": "Concurrent submissions are permitted.",
    "conflict_LICENSE": "MIT licensing is permitted.",
    "conflict_SPONSOR_SUPPORT": "Sponsor-supported projects are permitted.",
    "conflict_SAME_PROJECT": "Same-project entries are permitted.",
    "conflict_EXISTING_PROJECT": "Existing projects are permitted.",
    "conflict_DISCLOSURE": "Reuse disclosure satisfies the program rule.",
}
SOURCE_TEXT = "\n".join(
    (
        "Organizer: Northstar Foundation.",
        "Program: Open Builders Challenge.",
        "Edition: 2030.",
        *CLAUSES.values(),
    )
)


def fact(value, provenance="DOCUMENTED"):
    return {"value": value, "provenance": provenance}


def controlled_profile(path: Path) -> StudioInput:
    now = datetime.now(UTC)
    common = {
        "schema_version": "1",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "provenance": "DOCUMENTED",
    }
    founder = FounderProfile.model_validate(
        {
            **common,
            "id": "browser-demo-founder",
            "country_of_residence": fact("Spain"),
            "legal_form": fact("INCORPORATED_COMPANY"),
            "team_size": fact(2),
            "available_hours": fact("80", "USER_ASSERTED"),
            "max_cash_commitment": fact({"currency": "USD", "amount": "100"}, "USER_ASSERTED"),
            "strategic_goals": fact(("learning",), "USER_ASSERTED"),
            "verified_at": now,
        }
    )
    project = ProjectProfile.model_validate(
        {
            **common,
            "id": "browser-demo-qualor",
            "name": "QUALOR",
            "problem": fact("climate", "USER_ASSERTED"),
            "audience": fact("founders", "USER_ASSERTED"),
            "stage": fact("PROTOTYPE"),
            "available_features": fact(("search",), "USER_ASSERTED"),
            "technology_stack": fact(("Python", "TypeScript")),
            "code_provenance": fact("ORIGINAL"),
            "is_new_project": fact(True),
            "license_intent": fact("MIT"),
            "estimated_adaptation_hours": fact("2", "USER_ASSERTED"),
            "has_sponsor_support": fact(False),
            "reward_conditions_met": fact(True),
            "facts_verified_at": now,
            "project_lineage": fact((), "USER_ASSERTED"),
            "reused_components": fact((), "USER_ASSERTED"),
            "reuse_disclosed": fact(True, "USER_ASSERTED"),
            "material_readiness": tuple(
                {"kind": kind, "ready": fact(True, "USER_ASSERTED")} for kind in MATERIALS
            ),
        }
    )
    effort = EffortAssumptions.model_validate(
        {
            "items": tuple(
                {
                    "category": category,
                    "hours": {"min_hours": "1", "max_hours": "2"},
                    "confidence": "MEDIUM",
                    "reason": "Controlled preparation assumption",
                }
                for category in (
                    "INTEGRATION",
                    "EVIDENCE",
                    "REPO_LICENSE_CLEANUP",
                    "DEMO",
                    "NARRATIVE",
                    "SUBMISSION",
                )
            )
        }
    )
    profile = StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Controlled hosted LIVE approval",
        allowed_hosts=("example.org",),
        founder=founder,
        projects=(ProjectDecisionInput(project=project, effort=effort),),
    )
    path.write_text(profile.model_dump_json(), encoding="utf-8")
    return profile


def _official_evidence(source, now) -> tuple[EvidenceRecord, ...]:
    categories = {
        **{name: name for name in tuple(CLAUSES)[:9]},
        "conflict_NEW_PROJECT": "PROJECT_POLICY",
        "conflict_EXCLUSIVE_SUBMISSION": "PROJECT_POLICY",
        "conflict_LICENSE": "LICENSE",
        "conflict_SPONSOR_SUPPORT": "FINANCIAL_SUPPORT",
        "conflict_SAME_PROJECT": "PROJECT_POLICY",
        "conflict_EXISTING_PROJECT": "PROJECT_POLICY",
        "conflict_DISCLOSURE": "PROJECT_POLICY",
    }
    return tuple(
        EvidenceRecord.model_validate(
            {
                "schema_version": "1",
                "id": "official_" + name.lower(),
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "provenance": "DOCUMENTED",
                "source_id": source.id,
                "original_url": source.original_url,
                "final_url": source.final_url,
                "retrieved_at": source.retrieved_at,
                "source_type": source.authority,
                "content_hash": source.content_hash,
                "supporting_excerpt": excerpt,
                "normalized_field": categories[name],
                "extraction_state": "REVIEWED",
            }
        )
        for name, excerpt in CLAUSES.items()
    )


def _eligibility_rules(now) -> tuple[RuleCandidate, ...]:
    specs = (
        (
            "DEADLINE",
            "DATE_BETWEEN",
            (
                {"kind": "instant", "value": "2026-01-01T00:00:00Z"},
                {"kind": "instant", "value": DEADLINE},
            ),
            "context.evaluated_at",
        ),
        ("ENTRANT_TYPE", "GTE", ({"kind": "number", "value": "1"},), "founder.team_size"),
        (
            "GEOGRAPHY",
            "IN",
            ({"kind": "text", "value": "Spain"},),
            "founder.country_of_residence",
        ),
        (
            "LEGAL_ENTITY",
            "EQ",
            ({"kind": "text", "value": "INCORPORATED_COMPANY"},),
            "founder.legal_form",
        ),
        (
            "PROJECT_POLICY",
            "BOOL_IS",
            ({"kind": "bool", "value": True},),
            "project.is_new_project",
        ),
        ("LICENSE", "EQ", ({"kind": "text", "value": "MIT"},), "project.license_intent"),
        (
            "REQUIRED_TECHNOLOGY",
            "IN",
            ({"kind": "text", "value": "Python"},),
            "project.technology_stack",
        ),
        (
            "FINANCIAL_SUPPORT",
            "BOOL_IS",
            ({"kind": "bool", "value": False},),
            "project.has_sponsor_support",
        ),
        (
            "REWARD_CONDITIONS",
            "BOOL_IS",
            ({"kind": "bool", "value": True},),
            "project.reward_conditions_met",
        ),
    )
    return tuple(
        RuleCandidate.model_validate(
            {
                "schema_version": "1",
                "id": "rule_" + category.lower(),
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "provenance": "DOCUMENTED",
                "rule_type": category,
                "operator": operator,
                "operands": operands,
                "subject_reference": subject,
                "criticality": "CRITICAL",
                "evidence_ids": ("official_" + category.lower(),),
                "supported": True,
                "source_text_summary": CLAUSES[category],
            }
        )
        for category, operator, operands, subject in specs
    )


def _conflict_rules() -> tuple[ConflictRule, ...]:
    return tuple(
        ConflictRule.model_validate(
            {
                "id": "rule_" + name.lower(),
                "category": name.removeprefix("conflict_"),
                "applies": fact(False),
                "supported": True,
                "evidence_ids": ("official_" + name.lower(),),
                "allowed_licenses": fact(("MIT",)),
            }
        )
        for name in CLAUSES
        if name.startswith("conflict_")
    )


def _opportunity(source, now) -> OpportunityRecord:
    return OpportunityRecord.model_validate(
        {
            "schema_version": "1",
            "id": "normalized-by-domain",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "provenance": "DOCUMENTED",
            "organizer": "Northstar Foundation",
            "program_name": "Open Builders Challenge",
            "edition": "2030",
            "canonical_rules_url": source.final_url,
            "deadlines": (DEADLINE,),
            "status": "OPEN",
            "source_versions": (source.content_hash,),
            "strategic_benefits": fact(("learning",), "USER_ASSERTED"),
            "matching_requirements": {
                "problem_labels": fact(("climate",), "USER_ASSERTED"),
                "audience_labels": fact(("founders",), "USER_ASSERTED"),
                "technologies": fact(("Python", "TypeScript"), "USER_ASSERTED"),
                "features": fact(("search",), "USER_ASSERTED"),
                "stages": fact(("PROTOTYPE",), "USER_ASSERTED"),
                "licenses": fact(("MIT",), "USER_ASSERTED"),
                "original_code_required": fact(True, "USER_ASSERTED"),
                "max_adaptation_hours": fact("10", "USER_ASSERTED"),
                "materials": tuple(
                    {"kind": kind, "required": fact(True, "USER_ASSERTED")} for kind in MATERIALS
                ),
            },
        }
    )


class ControlledActionableRunner:
    """Drive real LIVE operations, then persist one source-grounded deterministic graph."""

    def __call__(self, inputs, gateway_id, *, sink, budget):
        if gateway_id != "controlled-browser-gateway":
            raise RuntimeError("CONTROLLED_GATEWAY_REQUIRED")
        phase = float(os.environ.get("QUALOR_TASK4_E2E_PHASE_SECONDS", ".2"))

        class Search(AgentCoreSearchProvider):
            def search(self, request):
                return (SearchCandidate(str(inputs.official_url), "Official rules", "discovery"),)

        class Extract(BedrockClaimExtractor):
            def extract(self, source, focus):
                values = (
                    (
                        ("organizer", "Northstar Foundation", "Organizer: Northstar Foundation."),
                        ("program", "Open Builders Challenge", "Program: Open Builders Challenge."),
                        ("edition", "2030", "Edition: 2030."),
                    )
                    if focus == "metadata"
                    else (
                        ("deadline", "2030-06-01T17:00:00Z", CLAUSES["DEADLINE"]),
                        ("project_policy", "NEW_ONLY", CLAUSES["PROJECT_POLICY"]),
                        ("required_technology", ("Python",), CLAUSES["REQUIRED_TECHNOLOGY"]),
                    )
                )
                return tuple(
                    ExtractedClaim(
                        source_id=source.id,
                        source_url=source.final_url,
                        field=field,
                        value=value,
                        excerpt=excerpt,
                        state="CANDIDATE",
                        confidence="HIGH",
                    )
                    for field, value, excerpt in values
                )

        run = OpportunityRun(
            inputs,
            mode="LIVE",
            search=Search(mode="LIVE", transport=object(), budget=budget),
            fetcher=OfficialSourceFetcher(
                mode="LIVE",
                allowed_hosts=inputs.allowed_hosts,
                budget=budget,
                resolver=lambda host: ["93.184.216.34"],
                request=lambda url, address: (
                    200,
                    {"content-type": "text/plain"},
                    SOURCE_TEXT.encode(),
                ),
            ),
            extractor=Extract(SimpleNamespace(budget=budget)),
            budget=budget,
            sink=sink,
            opportunity_version_resolver=sink.resolve_opportunity_version,
        )
        time.sleep(phase)
        candidates = run.search_web("Open Builders Challenge official rules")
        fetched = run.fetch_official_source(candidates["results"][0]["candidate_id"])
        source = run.sources[fetched["source_id"]]
        run.extract_official_claims(source.id, "metadata")
        run.extract_official_claims(source.id, "requirements")
        time.sleep(phase)

        now = datetime.now(UTC)
        opportunity = sink.resolve_opportunity_version(_opportunity(source, now))
        reviewed = _official_evidence(source, now)
        diagnostic = tuple(claim.evidence for claim in run.claims.values())
        evidence = (*reviewed, *diagnostic)
        decision_input = DecisionInput(
            schema_version="1",
            mode="LIVE",
            founder=inputs.founder,
            opportunity=opportunity,
            projects=inputs.projects,
            eligibility_rules=_eligibility_rules(now),
            evidence=evidence,
            conflict_rules=_conflict_rules(),
            active_submissions=(),
            participation_costs=ParticipationCosts(complete=fact(True, "USER_ASSERTED"), items=()),
            evaluated_at=now,
        )
        decision = decide(decision_input)
        if decision.selected_decision is None or decision.recommendation not in {
            "APPLY",
            "PREPARE",
        }:
            raise RuntimeError("CONTROLLED_ACTIONABLE_DECISION_REQUIRED")
        bundle = RuntimeDecisionBundle(
            opportunity=opportunity,
            evidence=evidence,
            decision_input=decision_input,
            decision=decision,
        )
        run.event("ELIGIBILITY_EVALUATED", "DETERMINISTIC_ENGINE", count=1)
        run.event("DECISION_EVALUATED", "DETERMINISTIC_ENGINE")
        run.stop("SUFFICIENT_CRITICAL_EVIDENCE")
        run.event("RUN_TERMINATED", run.termination_reason)
        result = AgentRunResult(
            mode="LIVE",
            decision=decision,
            claims=tuple(run.claims.values()),
            trace=tuple(run.trace),
            termination_reason=run.termination_reason,
            agent_steps=run.steps,
            search_calls=run.search_calls,
            fetched_documents=len(run.sources),
            official_source_count=1,
            citation_urls=(source.final_url,),
            contradictions=(),
            sources=(
                SourceCitation(
                    id=source.id,
                    final_url=source.final_url,
                    retrieved_at=source.retrieved_at,
                    content_hash=source.content_hash,
                    authority=source.authority,
                    truncated=source.truncated,
                ),
            ),
            boundary_events=tuple(run.boundary_events),
            bundle=bundle,
        )
        sink.run_finished(result)
        return result, {}


runtime_dir = Path(os.environ["QUALOR_TASK4_E2E_DIR"])
runtime_dir.mkdir(parents=True, exist_ok=True)
profile = controlled_profile(runtime_dir / "profile.json")
# Test-only fixed profile injection; production retains the narrow hosted profile loader.
hosted_inputs.load_demo_profile = lambda path: profile
settings = Settings(
    database_path=runtime_dir / "workspace.db",
    qualor_security_mode="HOSTED_DEMO",
    qualor_origin_auth=os.environ["QUALOR_TASK4_E2E_ORIGIN_AUTH"],
    qualor_hosted_live_enabled=True,
    qualor_demo_profile_path=runtime_dir / "profile.json",
    qualor_gateway_id="controlled-browser-gateway",
    qualor_live_cooldown_seconds=0,
)
app = create_app(
    settings,
    live_runner=ControlledActionableRunner(),
    live_resolver=lambda host: ["93.184.216.34"],
)
