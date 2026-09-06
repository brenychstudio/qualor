# QUALOR-03B3D: bounded handoff diagnosis

Canonical: `docs/00_CANONICAL_BRIEF_UA.md`, unchanged. Baseline:
`7ae18612109beeb3efd3878629c8bdfcda611dd0`. Existing branch only.

## Evidence before a hypothesis

The original report proves search results and one official fetch, followed by no
admitted claims. It also records two generic rejections before the successful fetch.
It does not contain their tool names, arguments, exception types or exact reasons.
FIRST_RUN_ROOT_CAUSE=UNKNOWN. Best known boundary is tool dispatch/admission B3-B8;
it cannot truthfully be narrowed to extraction alone. No speculative functional fix.

The baseline added safe error-code allowlisting, tool-name/error-class metrics and
source citations without accepted claims. Independent review fixed quote-punctuation
exceptions, additive/equivalent technology claims, and interruptible HTTP reads.
Those are tested improvements, not evidence of the original live cause.

## Boundary map

| Boundary | Input type | Output type | Failure representation |
|---|---|---|---|
| B1 Strands -> search_web | typed query/include domains | SearchRequest | strict tool/schema rejection |
| B2 search -> candidates | SearchRequest | tuple[SearchCandidate] | bounded provider exception |
| B3 candidate -> fetch | discovered URL, optional focus | FetchRequest | undiscovered/unauthorized URL |
| B4 HTTP fetch -> source | FetchRequest | SourceDocument | HTTP/type/size/timeout/schema rejection |
| B5 source -> model | bounded text, source ID/URL/time | model tool-use message | model failure or no claim request |
| B6 extraction -> claims | list[ExtractedClaim] tool arguments | strict Pydantic claims | input validation error |
| B7 claim validation | ExtractedClaim + run sources | ValidatedClaim | quote/reference/value rejection |
| B8 admission | ValidatedClaim | EvidenceRecord in run memory | model/admission failure |
| B9 eligibility | rules + source evidence + explicit profiles | EligibilityGate | UNKNOWN/REVIEW for unsupported rules |
| B10 decision | gate + matching/strategy/effort/conflict | DecisionOutput | deterministic recommendation |

`record_evidence` accepts source_id/source_url/field/value/excerpt/state/confidence,
not a caller-created EvidenceRecord. Code supplies evidence ID, retrieved_at, content
hash, normalized_field and extraction_state from fetched data and admission policy.
Strands 1.54.0 validates tool arguments with Pydantic and passes model_dump dictionaries
to the typed wrapper. The wrapper validates each ExtractedClaim again. Keep this strict.

## Minimal diagnostic changes and RED/GREEN checks

1. `runtime/diagnostics.py`, `run_models.py`, `loop.py`: bounded structured events
   for source fetch, extraction request/result, claim validation and admission.
   Safe codebook summaries, components, recoverability, missing fields and type-only
   input/output shapes. Never dump exception text, model reasoning or raw pages.
2. `runtime/agent.py`: record actual tool argument shapes, classify SDK validation
   failures from chained Pydantic errors, and replace unsafe SDK error text with an
   actionable structured rejection. Keep exactly four strict tools, no fallback types.
3. `runtime/live_cli.py`: explicit diagnostic authorization selects a separate exclusive
   run-2 marker and tighter limits: six model calls, three searches, five fetches, USD
   0.15. Preserve run-1 artifacts. No automatic retry or marker deletion.
4. Tests first: successful full event sequence; missing fields/source/excerpt; raw
   secret-looking error text never serialized; actual SDK invalid tool argument reaches
   agent as REJECTED; actual tool schemas unchanged; run-2 policy and repeat guard.
5. Export schemas/types, Ruff, all tests, npm build and clean-tree verify before LIVE.
   Commit diagnostic changes as a reviewable checkpoint if needed for clean verification.

## Single live execution and stop

Use the unchanged synthetic studio profile and real Agents for Humans case. One
additional live run only. Measure model usage, search/Gateway calls, fetched documents,
admitted records and critical rule evidence references. Identify the earliest causal
rejection, not downstream symptoms. If evidence admission fails, no further fix/retry.

Update status documentation with factual outcome. Run full verification, secret scan,
commit/push only task changes. No IAM/resource mutation, final merge or QUALOR-04A.

## Execution outcome

Baseline and pre-run clean verification passed. Eight diagnostic tests were added,
including actual Strands SDK missing/unsupported-field rejections. All 537 tests passed.
One authorized run-2 executed on commit `3d967dc9c2989d9a72f7bbabd074f4fe4e6835c2`.
First rejection: B3 URL_NOT_DISCOVERED. Official FAQ subsequently fetched; after a
second search the cost guard blocked the next model call. record_evidence was never
called. No candidate validator/admission defect is inferred. No third run or speculative
post-run code fix. See docs/status/QUALOR-03.md for exact counters, costs and blockers.
