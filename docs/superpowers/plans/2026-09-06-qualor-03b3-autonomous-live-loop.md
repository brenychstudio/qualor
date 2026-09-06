# QUALOR-03B3 autonomous live loop implementation plan

> Execution: inline TDD with verification-before-completion; no development subagents.

**Goal:** One Strands agent dynamically gathers official evidence, then the existing
deterministic engines produce conditional project decisions and a portfolio result.
**Spec:** Owner task QUALOR-03B3 and `docs/00_CANONICAL_BRIEF_UA.md` (unchanged).
**Stack:** Existing Python 3.12, Strands 1.54.0, boto3/botocore, Pydantic and HTTPX.

## Constraints and architecture

Use the existing branch and model `global.anthropic.claude-sonnet-4-6`, profile
`qualor-dev`, region `us-east-1`. No IAM changes, infrastructure, submission, persistence,
private profile data or model fallback. The existing Gateway/target are read and used only.
Source registry is operator input; the agent cannot expand it. Initial authorized
domains: agentsforhumans.devpost.com and aws.amazon.com. Exact/subdomain ownership is
checked without treating every devpost.com tenant as official.

The four tools are `search_web`, `fetch_official_source`, `record_evidence`,
`evaluate_current_state`. Tool arguments contain requests/claims only, never verdicts.
One sequential Strands tool executor prevents concurrent reservations. Model response
text is never a final decision or trace. All returned decisions come from pure engines.

## 1. Mode-correct deterministic handoff

Files: `domain/fixture.py`, `decisions/fixture.py`, `decisions/model.py`,
`decisions/engine.py`, eligibility imports, `tests/runtime/test_live_handoff.py`.
Introduce `EvaluationInput`, `DecisionInput`, `DecisionOutput` accepting explicit
LIVE/FIXTURE/REPLAY; preserve strict fixture subclasses and `decide_fixture` behavior.
`decide(inputs: DecisionInput) -> DecisionOutput` reuses the existing calculation,
passing the actual mode. Synthetic evidence remains valid only in FIXTURE.

- [x] RED: LIVE handoff currently rejected; strict fixture LIVE forgery still rejected.
- [x] GREEN: share calculation without rewriting recommendation/eligibility policy.
- [x] Verify: `uv run pytest tests/runtime/test_live_handoff.py tests/decisions -q`.

## 2. Safe sources and validated claims

Files: `runtime/sources.py`, `runtime/claims.py`, `tests/runtime/test_sources.py`,
`tests/runtime/test_claims.py`.
`OfficialSourceFetcher.fetch(FetchRequest) -> SourceDocument`: only discovered candidates
on operator-approved hosts; HTTPS, public resolved addresses, pinned connection to the
validated address with original Host/SNI and TLS verification; recheck each redirect.
At most 3 redirects, 20-second socket timeout, 1 MB decoded response, HTML/JSON/plain only.
HTML parser excludes scripts/styles; complete bounded text stays in run memory only.

`ExtractedClaim` is a strict Pydantic model containing field, value/state, source ID/URL,
excerpt and confidence. `validate_claim(claim, sources)` requires a fetched source,
literal normalized excerpt, and support for normalized values. Unsupported interpretation
stays UNKNOWN; no numeric/timezone invention or unsupported N/A. A deliberately small
controlled-clause policy can review explicit technology/new-project requirements;
other legal interpretation remains unverified. No opportunity-specific answer templates.
EvidenceRecord IDs, URLs, times and hashes are assigned by code, never the model.
Disagreeing official values produce explicit contradiction and unresolved critical rules.

- [x] RED/GREEN: A05–A16, A29–A30; missing source, third-party, false excerpt, numbers,
  timezone, N/A, negation, contradiction; DNS rebinding/redirect/private-address tests.
- [x] Verify: `uv run pytest tests/runtime/test_sources.py tests/runtime/test_claims.py -q`.

## 3. Bounded run controller and trace

Files: `runtime/loop.py`, `runtime/run_models.py`, `runtime/budget.py`,
`tests/runtime/test_autonomous_loop.py`, `tests/runtime/test_budget.py`.
`OpportunityRun` holds source candidates, fetched documents, validated claims, evidence,
and bounded action-only `AgentRunTrace`; no raw model reasoning/messages are exported.
`evaluate_current_state()` compiles supported claims into existing RuleCandidate and
OpportunityRecord contracts and calls `decide`. Missing critical coverage remains review.
Sanitized profile input contains 3 explicit synthetic projects and effort assumptions;
unknown opportunity costs/conflict rules are not filled with optimistic defaults.

Stop on sufficient evidence, confirmed hard failure, budget exhaustion, 24 tool steps,
3 repeated no-progress actions or 3 tool failures. Always emit a termination reason.
FIXTURE/REPLAY use supplied synthetic/recorded observations through this same controller;
neither can open live providers. Recorded actions are validated, never replayed as Python.

Explicit B3 budget authorization permits up to 6 model calls, 5 searches, 10 documents,
USD 0.20; earlier default 3-call guards remain unchanged. Reserve before every physical
Bedrock invocation, including SDK recovery calls. Disable SDK/Strands automatic retries.
Reconcile only reported usage; failed/interrupted calls retain reservations. Estimate
input conservatively from serialized UTF-8 size plus framing and cap output tokens.

- [x] RED/GREEN: A01–A04, A17–A28; guarded attempts, termination, immutable authority,
  mode separation, bounded trace and deterministic final result.

## 4. Strands adapter, CLI and dogfood

Files: `runtime/agent.py`, `runtime/live_cli.py`, `cli.py`,
`examples/profiles/synthetic-studio.json`, `tests/runtime/test_agent.py`.
Construct exactly one `Agent` with the four tools, sequential execution, no default
callback output, no sessions/storage/extra tools. Pydantic tool arguments constrain
extraction; system prompt describes evidence behavior only. Bedrock wrapper reserves
before every physical Converse request and records usage only; model temperature 0.
`run-live-opportunity --profile <sanitized-json> --mode LIVE --gateway-id <local-id>`
validates before AWS access and prints a bounded structured result with citations.

- [x] RED/GREEN: adapter tool inventory, dynamic synthetic Strands model tool use,
  actual SDK loop, no final model prose used as authority, default CLI offline rejection.
- [x] Run all offline tests before any inference; freeze dependency versions.
- [x] Run ONE dogfood scenario for AWS Agents for Humans Professional Agents. Agent
  chooses queries and source URLs. A second run is allowed only for a specific recoverable
  coverage fix. Task-wide reserved/actual cost must remain within USD 0.20 across runs.
- [x] Assess autonomy, evidence, control and nontrivial value honestly; no forced APPLY.

## 5. Evidence, verification and checkpoint

Update `docs/status/QUALOR-03.md`; add ADR for mode/promotion/budget boundary decisions.
Export public Pydantic schemas and regenerate TypeScript; no handwritten duplicate types.
Record bounded source citations/excerpts and observed trace summary, no full pages,
credentials, endpoints or account identifiers. Local reports remain ignored.

- [ ] Run Ruff, all pytest, schemas/types, npm ci/build, secret scan and git diff --check.
- [ ] Commit logical tested changes; run `scripts/verify.ps1` on clean committed tree.
- [ ] Run `scripts/aws-preflight.ps1`, verify one Gateway/one target, push exact HEAD.
- [ ] Return Result Packet; no PR/merge or QUALOR-04A work.

Deferred: general legal interpretation, PDF unless proven necessary, arbitrary domains,
browser, persistent evidence/history, draft package, UI, deployment and new resources.

## Execution outcome

Offline implementation completed with 529 passing tests. One actual live run reached
search and official fetch, then stopped at the tool failure bound with no admitted
evidence. STATUS=PARTIAL; no second paid run or speculative coverage fix. Safe error
codes and fetched-source metadata retention were added with RED/GREEN regressions.
The original live observation is not rewritten. Final commit/verification/push gates
are reported in the Result Packet. See docs/status/QUALOR-03.md for precise counts.
