"""Run memory and deterministic tool actions. No shell, file, IAM or final-verdict tool."""

from .budget import BudgetLimitExceeded
from .claims import ExtractedClaim, validate_claim
from .handoff import compute_decision
from .mode import ProviderBoundaryError, RuntimeMode
from .providers import FetchRequest, SearchRequest
from .run_models import AgentRunResult, SourceCitation, StudioInput, TraceEvent

SAFE_FAILURE_CODES = frozenset(
    {
        "URL_NOT_DISCOVERED",
        "CLAIM_LIMIT",
        "CLAIM_BATCH_LIMIT",
        "STRUCTURED_TOOL_REJECTED",
        "CLAIM_REQUIRES_FETCHED_SOURCE",
        "EXCERPT_NOT_IN_FETCHED_SOURCE",
        "NORMALIZED_VALUE_NOT_SUPPORTED_BY_QUOTE",
        "NA_REASON_NOT_SUPPORTED",
        "SOURCE_URL_NOT_AUTHORIZED",
        "SOURCE_ADDRESS_NOT_PUBLIC",
        "SOURCE_REDIRECT_LIMIT",
        "UNSUPPORTED_SOURCE_TYPE",
        "UNSUPPORTED_SOURCE_ENCODING",
        "SOURCE_SIZE_LIMIT",
        "SOURCE_SIZE_OR_TIME_LIMIT",
        "SOURCE_HTTP_403",
        "SOURCE_HTTP_404",
        "SOURCE_HTTP_429",
    }
)


class OpportunityRun:
    def __init__(self, inputs: StudioInput, *, mode, search, fetcher, budget, max_steps=24):
        self.inputs = StudioInput.model_validate(inputs)
        self.mode = RuntimeMode(mode).value
        if self.mode == "LIVE":
            from .search import AgentCoreSearchProvider
            from .sources import OfficialSourceFetcher

            if not isinstance(search, AgentCoreSearchProvider) or not isinstance(
                fetcher, OfficialSourceFetcher
            ):
                raise ProviderBoundaryError("Explicit live providers required")
            if search.budget is not budget or fetcher.budget is not budget:
                raise ProviderBoundaryError("Live operations require one shared budget")
        else:
            from .search import AgentCoreSearchProvider
            from .sources import OfficialSourceFetcher

            if isinstance(search, AgentCoreSearchProvider) or isinstance(
                fetcher, OfficialSourceFetcher
            ):
                raise ProviderBoundaryError("Offline runs reject AWS/network providers")
        if not 1 <= max_steps <= 24:
            raise ValueError("Tool step ceiling is 24")
        self.search, self.fetcher, self.budget = search, fetcher, budget
        self.max_steps = max_steps
        self.steps = self.no_progress = self.failures = self.search_calls = 0
        self.candidates, self.sources, self.claims = {}, {}, {}
        self.trace = []
        self.actions = set()
        self.termination_reason = None
        self.decision = None
        self.contradictions = ()

    def event(self, event, reason, ids=(), count=0):
        if len(self.trace) < 99:
            self.trace.append(
                TraceEvent(event=event, reason_code=reason, source_ids=ids, count=count)
            )

    def stop(self, reason):
        if self.termination_reason is None:
            self.termination_reason = reason

    def enter(self, key):
        if self.termination_reason:
            return False
        if self.steps >= self.max_steps:
            self.stop("MAX_STEPS")
            return False
        self.steps += 1
        if key in self.actions:
            self.no_progress += 1
            if self.no_progress >= 3:
                self.stop("NO_PROGRESS")
            return False
        self.actions.add(key)
        return True

    def failure(self, exc):
        if isinstance(exc, BudgetLimitExceeded):
            self.stop("BUDGET_EXHAUSTED")
        else:
            self.failures += 1
            if self.failures >= 3:
                self.stop("TOOL_FAILURE_BOUND_REACHED")
        reason = str(exc) if str(exc) in SAFE_FAILURE_CODES else "TOOL_OR_CLAIM_REJECTED"
        self.event("HUMAN_REVIEW_NEEDED", reason)
        return {
            "status": "UNKNOWN",
            "reason_code": reason,
            "termination_reason": self.termination_reason,
        }

    def search_web(self, query: str, include_domains: list[str] | None = None):
        if not self.enter("search:" + query + str(include_domains)):
            return {"status": "STOPPED", "reason": self.termination_reason or "NO_PROGRESS"}
        try:
            request = SearchRequest(
                query,
                max_results=5,
                filters={"domainFilter": {"include": include_domains}} if include_domains else None,
            )
            self.event("SEARCH_REQUESTED", "DISCOVERY_ONLY")
            self.search_calls += 1
            results = self.search.search(request)
            for candidate in results:
                if candidate.citable_for_user_output:
                    self.candidates[candidate.url] = candidate
            self.event(
                "SEARCH_RESULTS_RECEIVED", "SNIPPETS_ARE_NOT_HARD_EVIDENCE", count=len(results)
            )
            return {
                "mode": self.mode,
                "results": [
                    {
                        "url": c.url,
                        "title": c.title,
                        "snippet": c.snippet[:500],
                        "published_date": c.published_date,
                    }
                    for c in results
                    if c.citable_for_user_output
                ],
            }
        except (ValueError, RuntimeError, OSError) as exc:
            return self.failure(exc)

    def fetch_official_source(self, url: str, focus: str = ""):
        if not self.enter("fetch:" + url + ":" + focus):
            return {"status": "STOPPED", "reason": self.termination_reason or "NO_PROGRESS"}
        try:
            if url not in self.candidates:
                raise ValueError("URL_NOT_DISCOVERED")
            existing = next((s for s in self.sources.values() if s.original_url == url), None)
            if existing is None:
                self.event("SOURCE_SELECTED", "OFFICIAL_CANDIDATE_SELECTED")
                existing = self.fetcher.fetch(FetchRequest(url))
                self.sources[existing.id] = existing
                self.event("SOURCE_FETCHED", "SOURCE_TEXT_UNTRUSTED_DATA", (existing.id,))
            position = existing.text.casefold().find(focus.casefold()) if focus else 0
            start = max(0, position - 300)
            return {
                "source_id": existing.id,
                "source_url": existing.final_url,
                "authority": existing.authority,
                "text": existing.text[start : start + 9000],
                "text_truncated": len(existing.text) > start + 9000,
                "retrieved_at": str(existing.retrieved_at),
            }
        except (ValueError, RuntimeError, OSError) as exc:
            return self.failure(exc)

    def record_evidence(self, claim: dict):
        if not self.enter("claim:" + str(claim)):
            return {"status": "STOPPED", "reason": self.termination_reason or "NO_PROGRESS"}
        try:
            if len(self.claims) >= 40:
                raise ValueError("CLAIM_LIMIT")
            parsed = ExtractedClaim.model_validate(claim)
            self.event("CLAIM_EXTRACTED", "STRUCTURED_CANDIDATE_ONLY")
            admitted = validate_claim(parsed, self.sources)
            self.claims[admitted.evidence.id] = admitted
            self.event("EVIDENCE_RECORDED", admitted.support_state, (admitted.evidence.id,))
            return {
                "status": admitted.support_state,
                "evidence_id": admitted.evidence.id,
                "source_url": admitted.evidence.final_url,
            }
        except (ValueError, RuntimeError, OSError) as exc:
            return self.failure(exc)

    def evaluate_current_state(self):
        self.decision = compute_decision(self)
        self.event(
            "ELIGIBILITY_EVALUATED", "DETERMINISTIC_ENGINE", count=len(self.decision.candidates)
        )
        self.event("DECISION_EVALUATED", "DETERMINISTIC_ENGINE")
        if all(d.eligibility_gate.state == "FAIL" for d in self.decision.candidates):
            self.stop("HARD_FAIL_CONFIRMED")
        elif all(d.eligibility_gate.state == "PASS" for d in self.decision.candidates):
            self.stop("SUFFICIENT_CRITICAL_EVIDENCE")
        return {
            "recommendation": self.decision.recommendation,
            "best_project": self.decision.best_project_id,
            "candidates": [
                {
                    "project_id": d.project_id,
                    "eligibility": d.eligibility_gate.state,
                    "recommendation": d.recommendation,
                    "reason_codes": d.reason_codes,
                    "missing_information": d.missing_information[:12],
                }
                for d in self.decision.candidates
            ],
            "termination_reason": self.termination_reason,
        }

    def finish(self):
        self.evaluate_current_state()
        self.stop("NO_PROGRESS")
        self.event("RUN_TERMINATED", self.termination_reason)
        return AgentRunResult(
            mode=self.mode,
            decision=self.decision,
            claims=tuple(self.claims.values()),
            trace=tuple(self.trace),
            termination_reason=self.termination_reason,
            agent_steps=self.steps,
            search_calls=self.search_calls,
            fetched_documents=len(self.sources),
            official_source_count=sum(
                s.authority not in {"THIRD_PARTY", "SEARCH_SNIPPET"} for s in self.sources.values()
            ),
            citation_urls=tuple(
                dict.fromkeys(
                    [s.final_url for s in self.sources.values()]
                    + [c.evidence.final_url for c in self.claims.values()]
                )
            ),
            contradictions=self.contradictions,
            sources=tuple(
                SourceCitation.model_validate(
                    s.model_dump(
                        include={
                            "id",
                            "final_url",
                            "retrieved_at",
                            "content_hash",
                            "authority",
                            "truncated",
                        }
                    )
                )
                for s in self.sources.values()
            ),
        )
