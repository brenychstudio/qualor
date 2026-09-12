from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.runtime.budget import LiveBudgetGuard, LiveBudgetPolicy
from qualor.runtime.claims import ExtractedClaim, validate_claim
from qualor.runtime.loop import OpportunityRun
from qualor.runtime.normalization import ClaimNormalizationError
from qualor.runtime.providers import SearchCandidate
from qualor.runtime.run_models import StudioInput
from qualor.runtime.sources import SourceDocument

OBSERVED_AT = datetime(2026, 9, 12, 16, 30, tzinfo=UTC)
RULES_URL = "https://example.org/rules"


def studio_input() -> StudioInput:
    base = {
        "schema_version": "1",
        "id": "profile-live",
        "version": 1,
        "created_at": OBSERVED_AT,
        "updated_at": OBSERVED_AT,
        "provenance": "USER_ASSERTED",
    }
    # Keep the expected match hand-derived: the project explicitly carries Widget SDK.
    founder = FounderProfile.model_validate(base)
    project = ProjectProfile.model_validate(
        {
            **base,
            "id": "project-live",
            "name": "Controlled project",
            "technology_stack": {
                "value": ["Widget SDK"],
                "provenance": "USER_ASSERTED",
            },
        }
    )
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Assess the controlled official opportunity",
        allowed_hosts=("example.org",),
        founder=founder,
        projects=(
            ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),
        ),
    )


def source(text: str, *, authority="OFFICIAL_RULES", digest="a" * 64) -> SourceDocument:
    return SourceDocument(
        id="source-live",
        original_url=RULES_URL,
        final_url=RULES_URL,
        retrieved_at=OBSERVED_AT,
        content_hash=digest,
        authority=authority,
        text=text,
    )


def claim(field: str, value, excerpt: str) -> ExtractedClaim:
    return ExtractedClaim.model_validate(
        {
            "source_id": "source-live",
            "source_url": RULES_URL,
            "field": field,
            "value": value,
            "excerpt": excerpt,
            "state": "CANDIDATE",
            "confidence": "HIGH",
        }
    )


def compiled_run(
    text: str,
    claims: tuple[ExtractedClaim, ...],
    *,
    authority="OFFICIAL_RULES",
):
    fetched = source(text, authority=authority)
    admitted = tuple(validate_claim(item, {fetched.id: fetched}) for item in claims)
    return SimpleNamespace(
        inputs=studio_input(),
        mode="LIVE",
        sources={fetched.id: fetched},
        candidates={},
        claims={item.evidence.id: item for item in admitted},
        contradictions=(),
        opportunity_version_resolver=lambda opportunity: opportunity,
    )


def test_compiler_creates_source_grounded_canonical_opportunity_and_absolute_deadline():
    from qualor.runtime.handoff import compile_decision_bundle

    text = (
        "Organizer: Example Foundation. "
        "Program: Open Builders Challenge. "
        "Deadline: 2030-06-01T17:00:00-07:00. "
        "Deliverables: Public repository and demonstration video. "
        "Projects must use Widget SDK."
    )
    run = compiled_run(
        text,
        (
            claim("organizer", "Example Foundation", "Organizer: Example Foundation."),
            claim("program", "Open Builders Challenge", "Program: Open Builders Challenge."),
            claim("deadline", "2030-06-01T17:00:00-07:00", "Deadline: 2030-06-01T17:00:00-07:00."),
            claim(
                "deliverables",
                ("Public repository", "demonstration video"),
                "Deliverables: Public repository and demonstration video.",
            ),
            claim(
                "required_technology",
                ("Widget SDK",),
                "Projects must use Widget SDK.",
            ),
        ),
    )

    bundle = compile_decision_bundle(run)

    assert bundle.opportunity.id != "unknown"
    assert bundle.opportunity.id.startswith("opp_")
    assert bundle.opportunity.organizer == "Example Foundation"
    assert bundle.opportunity.program_name == "Open Builders Challenge"
    assert bundle.opportunity.edition == "UNKNOWN"
    assert bundle.opportunity.deadlines == (
        datetime(2030, 6, 2, 0, 0, tzinfo=UTC),
    )
    assert bundle.opportunity.deliverables == (
        "Public repository",
        "demonstration video",
    )
    assert bundle.opportunity.canonical_rules_url == RULES_URL
    assert bundle.opportunity.source_versions == ("a" * 64,)
    assert bundle.decision.mode == "LIVE"
    assert bundle.decision.selected_decision is not None
    assert bundle.decision.recommendation == "WATCH"
    assert all(
        candidate.opportunity_id == bundle.opportunity.id
        and candidate.opportunity_version == bundle.opportunity.version
        for candidate in bundle.decision.candidates
    )

    deadline_evidence = next(
        item for item in bundle.evidence if item.normalized_field == "DEADLINE"
    )
    assert deadline_evidence.supporting_excerpt == "Deadline: 2030-06-01T17:00:00-07:00."
    assert deadline_evidence.original_url == RULES_URL
    assert deadline_evidence.final_url == RULES_URL
    assert deadline_evidence.content_hash == "a" * 64
    assert deadline_evidence.retrieved_at == OBSERVED_AT


@pytest.mark.parametrize(
    "value",
    (
        "2030-06-01",
        "2030-06-01T17:00:00",
        "June 1, 2030 at 5 PM Pacific",
    ),
)
def test_naive_or_ambiguous_deadline_remains_unknown(value):
    from qualor.runtime.handoff import compile_decision_bundle

    excerpt = f"Deadline: {value}."
    run = compiled_run(excerpt, (claim("deadline", value, excerpt),))

    bundle = compile_decision_bundle(run)

    assert bundle.opportunity.deadlines == ()
    assert bundle.evidence[0].supporting_excerpt == excerpt
    assert next(iter(run.claims.values())).normalized_value is None


def test_third_party_metadata_is_not_promoted_even_when_literal():
    from qualor.runtime.handoff import compile_decision_bundle

    excerpt = "Organizer: Unverified Publisher."
    run = compiled_run(
        excerpt,
        (claim("organizer", "Unverified Publisher", excerpt),),
        authority="THIRD_PARTY",
    )

    bundle = compile_decision_bundle(run)

    assert bundle.opportunity.organizer == "UNKNOWN"
    assert bundle.opportunity.provenance == "UNKNOWN"


def test_conflicting_supported_metadata_remains_unknown():
    from qualor.runtime.handoff import compile_decision_bundle

    first = source("Organizer: First Foundation.", digest="a" * 64)
    second = source("Organizer: Second Foundation.", digest="b" * 64).model_copy(
        update={
            "id": "source-second",
            "original_url": "https://example.org/faq",
            "final_url": "https://example.org/faq",
        }
    )
    claims = (
        claim("organizer", "First Foundation", "Organizer: First Foundation."),
        ExtractedClaim.model_validate(
            {
                "source_id": second.id,
                "source_url": second.final_url,
                "field": "organizer",
                "value": "Second Foundation",
                "excerpt": "Organizer: Second Foundation.",
                "state": "CANDIDATE",
                "confidence": "HIGH",
            }
        ),
    )
    admitted = (
        validate_claim(claims[0], {first.id: first}),
        validate_claim(claims[1], {second.id: second}),
    )
    run = SimpleNamespace(
        inputs=studio_input(),
        mode="LIVE",
        sources={first.id: first, second.id: second},
        candidates={},
        claims={item.evidence.id: item for item in admitted},
        contradictions=(),
        opportunity_version_resolver=lambda opportunity: opportunity,
    )

    bundle = compile_decision_bundle(run)

    assert bundle.opportunity.organizer == "UNKNOWN"
    assert "organizer" in run.contradictions


@pytest.mark.parametrize(
    ("field", "value", "excerpt"),
    (
        ("organizer", "Builders Challenge", "Program: Builders Challenge."),
        ("organizer", "Foundation", "Organizer: Northstar Foundation."),
    ),
)
def test_promoted_metadata_requires_an_exact_unqualified_field_clause(
    field, value, excerpt
):
    fetched = source(excerpt)

    with pytest.raises(ClaimNormalizationError):
        validate_claim(claim(field, value, excerpt), {fetched.id: fetched})


def test_qualified_metadata_is_retained_as_unknown_not_promoted():
    from qualor.runtime.handoff import compile_decision_bundle

    excerpt = "Program: Builders Challenge unless extended."
    fetched = source(excerpt)
    admitted = validate_claim(
        claim("program", "Builders Challenge unless extended", excerpt),
        {fetched.id: fetched},
    )
    run = SimpleNamespace(
        inputs=studio_input(),
        mode="LIVE",
        sources={fetched.id: fetched},
        candidates={},
        claims={admitted.evidence.id: admitted},
        contradictions=(),
        opportunity_version_resolver=lambda opportunity: opportunity,
    )

    bundle = compile_decision_bundle(run)

    assert admitted.normalized_value is None
    assert bundle.opportunity.program_name == "UNKNOWN"


@pytest.mark.parametrize(
    "qualifier",
    ("unless extended", "if the organizer approves", "or later by notice"),
)
def test_trimmed_deadline_quote_cannot_hide_a_qualifier(qualifier):
    from qualor.runtime.handoff import compile_decision_bundle

    value = "2030-06-01T17:00:00Z"
    excerpt = f"Deadline: {value}"
    fetched = source(f"{excerpt} {qualifier}.")
    admitted = validate_claim(claim("deadline", value, excerpt), {fetched.id: fetched})
    run = SimpleNamespace(
        inputs=studio_input(),
        mode="LIVE",
        sources={fetched.id: fetched},
        candidates={},
        claims={admitted.evidence.id: admitted},
        contradictions=(),
        opportunity_version_resolver=lambda opportunity: opportunity,
    )

    bundle = compile_decision_bundle(run)

    assert admitted.normalized_value is None
    assert bundle.opportunity.deadlines == ()


def test_canonical_rules_source_and_versions_are_deterministic_from_admitted_evidence():
    from qualor.runtime.handoff import compile_decision_bundle

    source_a = source("Program: Builders Challenge.", digest="b" * 64).model_copy(
        update={
            "id": "source-z-id",
            "original_url": "https://example.org/a-rules",
            "final_url": "https://example.org/a-rules",
        }
    )
    source_z = source("Organizer: Northstar Foundation.", digest="a" * 64).model_copy(
        update={
            "id": "source-a-id",
            "original_url": "https://example.org/z-rules",
            "final_url": "https://example.org/z-rules",
        }
    )
    program = claim("program", "Builders Challenge", "Program: Builders Challenge.").model_copy(
        update={"source_id": source_a.id, "source_url": source_a.final_url}
    )
    organizer = claim(
        "organizer", "Northstar Foundation", "Organizer: Northstar Foundation."
    ).model_copy(update={"source_id": source_z.id, "source_url": source_z.final_url})

    def compile_with(items):
        sources = {item.id: item for item in items}
        admitted = (
            validate_claim(program, sources),
            validate_claim(organizer, sources),
        )
        run = SimpleNamespace(
            inputs=studio_input(),
            mode="LIVE",
            sources=sources,
            candidates={},
            claims={item.evidence.id: item for item in admitted},
            contradictions=(),
            opportunity_version_resolver=lambda opportunity: opportunity,
        )
        return compile_decision_bundle(run).opportunity

    forward = compile_with((source_a, source_z))
    reverse = compile_with((source_z, source_a))

    assert forward.canonical_rules_url == "https://example.org/a-rules"
    assert reverse.canonical_rules_url == forward.canonical_rules_url
    assert reverse.source_versions == forward.source_versions == ("b" * 64, "a" * 64)


def test_evaluate_then_finish_reuses_one_authoritative_decision(monkeypatch):
    import qualor.runtime.handoff as handoff

    class Search:
        def search(self, request):
            return (SearchCandidate(RULES_URL, "Controlled rules", "discovery only"),)

    fetched = source("Projects must use Widget SDK.")

    class Fetch:
        def fetch(self, request):
            return fetched.model_copy(
                update={"original_url": request.url, "final_url": request.url}
            )

    class Extract:
        def extract(self, source_document, focus):
            del focus
            return (
                claim(
                    "required_technology",
                    ("Widget SDK",),
                    "Projects must use Widget SDK.",
                ).model_copy(
                    update={
                        "source_id": source_document.id,
                        "source_url": source_document.final_url,
                    }
                ),
            )

    real_decide = handoff.decide
    calls = 0

    def counted_decide(decision_input):
        nonlocal calls
        calls += 1
        return real_decide(decision_input)

    monkeypatch.setattr(handoff, "decide", counted_decide)
    run = OpportunityRun(
        studio_input(),
        mode="FIXTURE",
        search=Search(),
        fetcher=Fetch(),
        extractor=Extract(),
        budget=LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal(".20"))),
    )
    reference = run.search_web("controlled")
    fetched_reference = run.fetch_official_source(reference["results"][0]["candidate_id"])
    run.extract_official_claims(fetched_reference["source_id"], "technology")

    run.evaluate_current_state()
    result = run.finish()

    assert calls == 1
    assert result.bundle is not None
    assert result.decision == result.bundle.decision


def test_fetch_without_admitted_evidence_does_not_recompute_decision(monkeypatch):
    import qualor.runtime.handoff as handoff

    class Search:
        def search(self, request):
            return (SearchCandidate(RULES_URL, "Controlled rules", "discovery only"),)

    fetched = source("Program: Controlled Challenge.")

    class Fetch:
        def fetch(self, request):
            return fetched.model_copy(
                update={"original_url": request.url, "final_url": request.url}
            )

    real_decide = handoff.decide
    calls = 0

    def counted_decide(decision_input):
        nonlocal calls
        calls += 1
        return real_decide(decision_input)

    monkeypatch.setattr(handoff, "decide", counted_decide)
    run = OpportunityRun(
        studio_input(),
        mode="FIXTURE",
        search=Search(),
        fetcher=Fetch(),
        extractor=None,
        budget=LiveBudgetGuard(LiveBudgetPolicy(cost_cap_usd=Decimal(".20"))),
    )

    run.evaluate_current_state()
    reference = run.search_web("controlled")
    run.fetch_official_source(reference["results"][0]["candidate_id"])
    result = run.finish()

    assert calls == 1
    assert result.bundle is not None


def test_opportunity_version_is_resolved_before_decision_records_are_created():
    from qualor.runtime.handoff import compile_decision_bundle

    excerpt = "Program: Versioned Challenge."
    run = compiled_run(excerpt, (claim("program", "Versioned Challenge", excerpt),))
    resolved = []

    def resolve(opportunity):
        resolved.append(opportunity)
        return opportunity.model_copy(update={"version": 7})

    run.opportunity_version_resolver = resolve

    bundle = compile_decision_bundle(run)

    assert len(resolved) == 1
    assert bundle.opportunity.version == 7
    assert all(candidate.opportunity_version == 7 for candidate in bundle.decision.candidates)
