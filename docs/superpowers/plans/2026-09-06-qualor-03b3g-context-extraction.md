# QUALOR-03B3G agent context and extraction boundary plan

> Execution: systematic debugging, RED/GREEN TDD, and verification before completion.

**Goal:** Close the proven B5 fetched-source-to-extraction budget blocker offline while
preserving the USD 0.15 fail-closed guard, one-agent architecture, strict evidence
admission, and zero AWS calls.

**Authority:** `docs/00_CANONICAL_BRIEF_UA.md` (unchanged), owner task QUALOR-03B3G,
and the ignored run-3 artifact used only for local forensic measurements.

## Proven starting condition

Run 3 completed four model turns, two searches, and two official fetches. The fifth
model request was rejected before AWS with current cost USD 0.077949, attempted
reservation USD 0.109659, and projected cost USD 0.187608. The reservation formula
therefore proves a 31,945-byte serialized request: USD 0.101979 input reservation plus
USD 0.007680 for 512 maximum output tokens. Provider usage retained calls 1-4, while
the historical message/tool-result byte split and fetched bodies were intentionally not
persisted. Source review proves that each fetch tool result exposed up to 9,000 source
characters to the ordinary Strands conversation. No evidence admission was attempted.

## 1. Establish bounded source capabilities

Files: `src/qualor/runtime/context.py`, `sources.py`, `loop.py`, `run_models.py`, and
focused runtime tests.

Add policy constants for the maximum source-reference excerpt and ordinary agent tool
result. Store complete fetched text only in `OpportunityRun.sources`. Replace the
fetcher-derived source identifier at admission with an opaque random source capability
valid only in that run. Return a `FetchedSourceRef` containing citation and selection
metadata plus a byte-bounded excerpt; never return the complete source body.

- RED: raw source text is absent, forged/prior-run source IDs fail, citation survives,
  the excerpt and total tool result stay bounded, and SSRF rules are unchanged.
- GREEN: add one source registry boundary and one UTF-8-safe bounded excerpt helper.

## 2. Add a model-powered extraction tool, not another agent

Files: `src/qualor/runtime/extraction.py`, `agent.py`, `loop.py`, `live_cli.py`, and tests.

Add `extract_official_claims(source_id, focus)`. Strands chooses the source and focus;
the runtime resolves the run-scoped source capability. A direct budgeted Bedrock
Converse call receives only the extraction contract, requested focus, one exact fetched
source, and the constrained claim schema. It does not receive the Strands conversation.
The tool returns only bounded typed claims. The existing `record_evidence` and
`validate_claim` code remains unchanged.

- RED: current-run resolution, forged/prior-run rejection, exact source input, no agent
  transcript, structured output/UNKNOWN preservation, and record-evidence handoff.
- GREEN: implement the extraction provider and expose it as the fifth bounded tool.

## 3. Preserve authority and prompt-injection boundaries

Files: focused agent/extraction tests and `run_models.py` trace contract.

Delimit fetched content as untrusted data, expose no arbitrary tools to the extraction
call, and reject unsupported source references or claims. Add trace events for source
reference creation and structured extraction without raw page content or model reasoning.

- RED/GREEN: hostile page instructions cannot grant tools, set eligibility, or produce
  deterministic PASS; final eligibility and recommendation still originate only in the
  deterministic engines.

## 4. Reconstruct and re-project the budget

Files: `agent.py`, `context.py`, budget tests, and local calculations.

Retain the conservative byte estimator and all call/cost ceilings. Add safe request-size
measurements (counts only) and demonstrate with the live-like replay request shape that
ordinary agent context no longer contains fetched bodies. Re-project the fifth planning
call and the separate extraction call under the unchanged USD 0.15 cap. Change estimator
logic only if an independent RED test proves a separate defect.

## 5. Offline live-like replay and verification

Files: runtime replay tests and `docs/status/QUALOR-03.md`.

Run one deterministic replay: search -> candidate -> fetch -> bounded source reference
-> extraction focus -> typed claim -> existing evidence admission -> deterministic
eligibility/decision. Assert zero Bedrock/Web Search calls, one critical EvidenceRecord,
`FAIL / SKIP` for the synthetic technology mismatch, and a bounded judge-readable trace.

Run Ruff, pytest, `scripts/verify.ps1`, read-only `scripts/aws-preflight.ps1`, schema
export, TypeScript generation, npm clean install/build, whitespace/status checks, and a
tracked-file secret scan. Commit and push only the B3G code/tests/docs on
`qualor-03-live-agent`. Do not run live dogfood, modify IAM/infrastructure, open/merge a
PR, or start QUALOR-04A.
