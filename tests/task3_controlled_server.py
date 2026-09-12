"""Browser-only controlled LIVE backend; no AWS transport or fixture/replay seeding."""

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from qualor.api import create_app
from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.runtime.claims import ExtractedClaim
from qualor.runtime.extraction import BedrockClaimExtractor
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.providers import SearchCandidate
from qualor.runtime.run_models import StudioInput
from qualor.runtime.search import AgentCoreSearchProvider
from qualor.runtime.sources import OfficialSourceFetcher
from qualor.settings import Settings

TEXT = (
    "Organizer: Northstar Foundation. Program: Open Builders Challenge. "
    "Deadline: 2030-06-01T17:00:00Z. Projects must use Widget SDK."
)


def demo_profile(path: Path) -> Path:
    now = datetime.now(UTC)
    common = dict(
        schema_version="1",
        version=1,
        created_at=now,
        updated_at=now,
        provenance="USER_ASSERTED",
    )
    founder = FounderProfile(id="browser-demo-founder", **common)
    project = ProjectProfile.model_validate(
        {
            **common,
            "id": "browser-demo-qualor",
            "name": "QUALOR",
            "technology_stack": {"value": ["Python"], "provenance": "DOCUMENTED"},
        }
    )
    profile = StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Browser-controlled test profile",
        allowed_hosts=("example.invalid",),
        founder=founder,
        projects=(ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),),
    )
    path.write_text(profile.model_dump_json(), encoding="utf-8")
    return path


class ControlledLiveRunner:
    """Drive real OpportunityRun and Task 1 persistence with controlled provider boundaries."""

    def __call__(self, inputs, gateway_id, *, sink, budget):
        if gateway_id != "controlled-browser-gateway":
            raise RuntimeError("CONTROLLED_GATEWAY_REQUIRED")
        phase_seconds = float(os.environ.get("QUALOR_TASK3_E2E_PHASE_SECONDS", "1.5"))
        time.sleep(phase_seconds)

        class Search(AgentCoreSearchProvider):
            def search(self, request):
                return (SearchCandidate(str(inputs.official_url), "Official rules", "discovery"),)

        class Extract(BedrockClaimExtractor):
            def extract(self, source, focus):
                values = (
                    (
                        ("organizer", "Northstar Foundation", "Organizer: Northstar Foundation."),
                        ("program", "Open Builders Challenge", "Program: Open Builders Challenge."),
                    )
                    if focus == "metadata"
                    else (
                        ("deadline", "2030-06-01T17:00:00Z", "Deadline: 2030-06-01T17:00:00Z."),
                        ("required_technology", ("Widget SDK",), "Projects must use Widget SDK."),
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
                    TEXT.encode(),
                ),
            ),
            extractor=Extract(SimpleNamespace(budget=budget)),
            budget=budget,
            sink=sink,
            opportunity_version_resolver=sink.resolve_opportunity_version,
        )
        candidates = run.search_web("Open Builders Challenge official rules")
        fetched = run.fetch_official_source(candidates["results"][0]["candidate_id"])
        time.sleep(phase_seconds)
        run.extract_official_claims(fetched["source_id"], "metadata")
        run.extract_official_claims(fetched["source_id"], "requirements")
        run.evaluate_current_state()
        time.sleep(phase_seconds)
        return run.finish(), {}


runtime_dir = Path(os.environ["QUALOR_TASK3_E2E_DIR"])
runtime_dir.mkdir(parents=True, exist_ok=True)
settings = Settings(
    database_path=runtime_dir / "workspace.db",
    qualor_security_mode="HOSTED_DEMO",
    qualor_origin_auth=os.environ["QUALOR_TASK3_E2E_ORIGIN_AUTH"],
    qualor_hosted_live_enabled=True,
    qualor_demo_profile_path=demo_profile(runtime_dir / "profile.json"),
    qualor_gateway_id="controlled-browser-gateway",
    qualor_live_cooldown_seconds=0,
)
app = create_app(
    settings,
    live_runner=ControlledLiveRunner(),
    live_resolver=lambda host: ["93.184.216.34"],
)
