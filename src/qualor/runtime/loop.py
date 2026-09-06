"""Run memory and deterministic tool actions. No shell, file, IAM or final-verdict tool."""

from urllib.parse import urlsplit
from uuid import uuid4

from .budget import BudgetLimitExceeded
from .claims import FIELD_CATEGORY, ExtractedClaim, validate_claim
from .diagnostics import BoundaryEvent, reject, shape
from .handoff import compute_decision
from .mode import ProviderBoundaryError, RuntimeMode
from .providers import FetchRequest, SearchRequest
from .run_models import AgentRunResult, SourceCitation, StudioInput, TraceEvent
from .urls import RegisteredCandidate, canonical_url_identity, sanitized_public_url


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
        self._candidate_identities = {}
        self.trace = []
        self.boundary_events = []
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

    def diagnostic(
        self,
        event,
        component,
        status,
        code,
        summary,
        *,
        input_value=None,
        output_value=None,
        ids=(),
        rejection=None,
        requested_url_sanitized=None,
        candidate_url_count=0,
        candidate_domains=(),
        closest_candidate_urls_sanitized=(),
        budget_current_cost_usd=None,
        budget_attempted_cost_usd=None,
        budget_remaining_cost_usd=None,
        budget_projected_cost_usd=None,
    ):
        if len(self.boundary_events) >= 160:
            return
        self.boundary_events.append(
            BoundaryEvent(
                sequence=len(self.boundary_events) + 1,
                event=event,
                component=component,
                status=status,
                reason_code=code,
                safe_summary=summary,
                input_shape=shape(input_value),
                output_shape=shape(output_value),
                source_ids=ids,
                recoverable=rejection.recoverable if rejection else "NO",
                missing_fields=rejection.missing_fields if rejection else (),
                validation_issues=rejection.validation_issues if rejection else (),
                requested_url_sanitized=requested_url_sanitized,
                candidate_url_count=candidate_url_count,
                candidate_domains=candidate_domains,
                closest_candidate_urls_sanitized=closest_candidate_urls_sanitized,
                budget_current_cost_usd=budget_current_cost_usd,
                budget_attempted_cost_usd=budget_attempted_cost_usd,
                budget_remaining_cost_usd=budget_remaining_cost_usd,
                budget_projected_cost_usd=budget_projected_cost_usd,
            )
        )

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

    def failure(
        self, exc, *, component="orchestration", event="TOOL_RESULT", input_value=None, code=None
    ):
        if isinstance(exc, BudgetLimitExceeded):
            self.stop("BUDGET_EXHAUSTED")
        else:
            self.failures += 1
            if self.failures >= 3:
                self.stop("TOOL_FAILURE_BOUND_REACHED")
        info = reject(
            exc,
            component=component,
            code="BUDGET_EXHAUSTED" if isinstance(exc, BudgetLimitExceeded) else code,
        )
        output = info.model_dump(mode="json")
        budget_values = {}
        if isinstance(exc, BudgetLimitExceeded) and exc.current_cost_usd is not None:
            budget_values = {
                "current_cost_usd": str(exc.current_cost_usd),
                "attempted_cost_usd": str(exc.attempted_cost_usd),
                "remaining_cost_usd": str(exc.remaining_cost_usd),
                "projected_cost_usd": str(exc.projected_cost_usd),
            }
            output["budget"] = budget_values
        if self.termination_reason:
            output["recoverable"] = "NO"
        output["termination_reason"] = self.termination_reason
        self.event("HUMAN_REVIEW_NEEDED", info.reason_code)
        self.diagnostic(
            event,
            component,
            "REJECTED",
            info.reason_code,
            info.safe_summary,
            input_value=input_value,
            output_value=output,
            rejection=info,
            budget_current_cost_usd=budget_values.get("current_cost_usd"),
            budget_attempted_cost_usd=budget_values.get("attempted_cost_usd"),
            budget_remaining_cost_usd=budget_values.get("remaining_cost_usd"),
            budget_projected_cost_usd=budget_values.get("projected_cost_usd"),
        )
        return output

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
            returned = []
            for candidate in results:
                if candidate.citable_for_user_output:
                    identity = canonical_url_identity(candidate.url or "")
                    if identity not in self._candidate_identities:
                        candidate_id = "candidate_" + uuid4().hex[:20]
                        self._candidate_identities[identity] = candidate_id
                        self.candidates[candidate_id] = RegisteredCandidate(
                            candidate_id=candidate_id,
                            observation=candidate,
                            fetch_url=candidate.url or "",
                            provenance=(
                                "SEARCH_CANDIDATE_EXACT"
                                if candidate.url == identity
                                else "SEARCH_CANDIDATE_CANONICAL_EQUIVALENT"
                            ),
                        )
                    returned.append((self._candidate_identities[identity], candidate))
            self.event(
                "SEARCH_RESULTS_RECEIVED", "SNIPPETS_ARE_NOT_HARD_EVIDENCE", count=len(results)
            )
            return {
                "mode": self.mode,
                "results": [
                    {
                        "candidate_id": candidate_id,
                        "url": c.url,
                        "title": c.title,
                        "snippet": c.snippet[:500],
                        "published_date": c.published_date,
                    }
                    for candidate_id, c in returned
                ],
            }
        except (ValueError, RuntimeError, OSError) as exc:
            return self.failure(exc, component="search_web", input_value={"query": query})

    def _available_candidate_references(self):
        return [
            {
                "candidate_id": candidate_id,
                "title": candidate.title[:200] if candidate.title else None,
                "url": sanitized_public_url(candidate.url or ""),
            }
            for candidate_id, registered in list(self.candidates.items())[:5]
            for candidate in (registered.observation,)
        ]

    def fetch_official_source(self, candidate_id: str, focus: str = ""):
        if not self.enter("fetch:" + candidate_id + ":" + focus):
            return {"status": "STOPPED", "reason": self.termination_reason or "NO_PROGRESS"}
        try:
            if candidate_id not in self.candidates:
                raise ValueError("CANDIDATE_NOT_FOUND")
            registered = self.candidates[candidate_id]
            fetch_url = registered.fetch_url
            self.event("CANDIDATE_SELECTED", "CURRENT_RUN_CAPABILITY_REFERENCE")
            existing = next((s for s in self.sources.values() if s.original_url == fetch_url), None)
            if existing is None:
                self.event("SOURCE_SELECTED", "OFFICIAL_CANDIDATE_SELECTED")
                existing = self.fetcher.fetch(FetchRequest(fetch_url))
                self.sources[existing.id] = existing
                self.event("SOURCE_FETCHED", "SOURCE_TEXT_UNTRUSTED_DATA", (existing.id,))
            position = existing.text.casefold().find(focus.casefold()) if focus else 0
            start = max(0, position - 300)
            output = {
                "source_id": existing.id,
                "source_url": existing.final_url,
                "authority": existing.authority,
                "text": existing.text[start : start + 9000],
                "text_truncated": len(existing.text) > start + 9000,
                "retrieved_at": str(existing.retrieved_at),
            }
            self.diagnostic(
                "SOURCE_FETCH_RESULT",
                "fetch_official_source",
                "ACCEPTED",
                "FETCHED_SOURCE_AVAILABLE",
                "Bounded source text is available for claims.",
                input_value={"candidate_id": candidate_id, "focus": focus},
                output_value=output,
                ids=(existing.id,),
            )
            return output
        except (ValueError, RuntimeError, OSError) as exc:
            result = self.failure(
                exc,
                component="fetch_official_source",
                event="SOURCE_FETCH_RESULT",
                input_value={"candidate_id": candidate_id, "focus": focus},
            )
            if str(exc) == "CANDIDATE_NOT_FOUND":
                available = self._available_candidate_references()
                result["available_candidates"] = available
                requested_url = sanitized_public_url(candidate_id)
                domains = tuple(
                    dict.fromkeys(
                        host
                        for item in available
                        if (host := urlsplit(item["url"] or "").hostname) is not None
                    )
                )[:10]
                closest = tuple(
                    sanitized
                    for item in available[:5]
                    if (sanitized := sanitized_public_url(item["url"] or "")) is not None
                )
                event = self.boundary_events[-1]
                self.boundary_events[-1] = event.model_copy(
                    update={
                        "requested_url_sanitized": requested_url,
                        "candidate_url_count": min(len(self.candidates), 25),
                        "candidate_domains": domains,
                        "closest_candidate_urls_sanitized": closest,
                    }
                )
            return result

    def record_evidence(self, claim: dict):
        if not self.enter("claim:" + str(claim)):
            return {"status": "STOPPED", "reason": self.termination_reason or "NO_PROGRESS"}
        stage = "extraction"
        try:
            if len(self.claims) >= 40:
                raise ValueError("CLAIM_LIMIT")
            parsed = ExtractedClaim.model_validate(claim)
            self.diagnostic(
                "EXTRACTION_RESULT",
                stage,
                "ACCEPTED",
                "TYPED_CANDIDATE",
                "Candidate schema validated; this does not establish truth.",
                input_value=claim,
                output_value=parsed.model_dump(),
            )
            self.event("CLAIM_EXTRACTED", "STRUCTURED_CANDIDATE_ONLY")
            stage = "claim_validation"
            self.diagnostic(
                "EVIDENCE_ADMISSION_ATTEMPT",
                "evidence_admission",
                "REQUESTED",
                "VALIDATE_FETCHED_REFERENCE",
                "Validate source, quote and normalized value.",
                input_value=parsed.model_dump(),
            )
            admitted = validate_claim(parsed, self.sources)
            self.diagnostic(
                "CLAIM_VALIDATION_RESULT",
                stage,
                "ACCEPTED",
                admitted.support_state,
                "Source-linked claim checked; unverified interpretation stays unresolved.",
                input_value=claim,
                output_value=admitted.model_dump(),
                ids=(admitted.evidence.id,),
            )
            self.claims[admitted.evidence.id] = admitted
            self.diagnostic(
                "EVIDENCE_ADMISSION_RESULT",
                "evidence_admission",
                "ACCEPTED",
                admitted.support_state,
                "EvidenceRecord admitted with fetched-source provenance.",
                ids=(admitted.evidence.id,),
                output_value={"evidence_id": admitted.evidence.id},
            )
            self.event("EVIDENCE_RECORDED", admitted.support_state, (admitted.evidence.id,))
            return {
                "status": admitted.support_state,
                "evidence_id": admitted.evidence.id,
                "source_url": admitted.evidence.final_url,
            }
        except (ValueError, RuntimeError, OSError) as exc:
            event = "EXTRACTION_RESULT" if stage == "extraction" else "CLAIM_VALIDATION_RESULT"
            result = self.failure(exc, component=stage, event=event, input_value=claim)
            if stage != "extraction":
                self.diagnostic(
                    "EVIDENCE_ADMISSION_RESULT",
                    "evidence_admission",
                    "REJECTED",
                    result["reason_code"],
                    result["safe_summary"],
                    output_value=result,
                )
            return result

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
        if not any(c.claim.field in FIELD_CATEGORY for c in self.claims.values()):
            self.diagnostic(
                "EXTRACTION_RESULT",
                "extraction",
                "REJECTED",
                "EXTRACTION_NO_CRITICAL_CLAIMS",
                "Run ended without an admitted critical claim; no evidence is fabricated.",
            )
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
            boundary_events=tuple(self.boundary_events),
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
