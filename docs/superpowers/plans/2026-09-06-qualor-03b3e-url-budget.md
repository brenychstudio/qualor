# QUALOR-03B3E URL admission and budget closure plan

> Execution: systematic debugging, RED/GREEN TDD, and verification before completion.

**Goal:** Close the proven live evidence handoff and budget-diagnostic defects offline,
without changing evidence admission, IAM, AWS resources, or performing paid calls.
**Spec:** Owner task QUALOR-03B3E and `docs/00_CANONICAL_BRIEF_UA.md` (unchanged).

## Proven starting conditions

Run 2 reached Web Search and fetched one official source, but the first fetch request was
rejected at B3 because the agent-supplied raw URL did not exactly match the run registry.
The historical rejected URL was not retained, so its precise textual difference cannot be
reconstructed. `record_evidence` was never called; its admission rules are out of scope.

The budget ledger reconciled completed model reservations and retained fixed search cost
reservations. The next model request was rejected because its conservative UTF-8 request
size plus the configured maximum output exceeded the remaining USD 0.088644. No reservation
leak or double counting is assumed; tests must prove the accounting behavior.

## 1. Replace raw URL authority with run-scoped candidate references

Files: `runtime/urls.py`, `runtime/loop.py`, `runtime/agent.py`, `runtime/run_models.py`,
`runtime/diagnostics.py`, and focused runtime tests.

`search_web` assigns an opaque `candidate_id` to each citable result and returns both the
reference and citation URL. `fetch_official_source(candidate_id, focus)` resolves only a
reference present in the current `OpportunityRun`; raw or prior-run references fail closed.
The model never creates a network capability. Source fetching still applies the existing
HTTPS, allowlist, DNS/IP, redirect, TLS, size, and timeout controls.

Canonical URL identity is limited to lower-case scheme/IDNA host, removal of the default
port and fragment, and treating an empty path as `/`. Paths, subdomains, query strings,
non-default ports, and HTTP/HTTPS remain distinct. This identity only deduplicates search
results; the registered provider URL remains the fetched and cited value.

- [x] RED: exact references pass; unknown/fabricated/prior-run references fail; citation URL is
  preserved; alternate paths cannot bypass the registry; recovery returns bounded candidate
  references and needs no second search.
- [x] GREEN: implement one registry and resolver, update the Strands tool schema and prompt, and
  emit `CANDIDATE_SELECTED` plus safe rejection diagnostics.

## 2. Make budget decisions explainable without weakening the cap

Files: `runtime/budget.py`, `runtime/agent.py`, `runtime/live_cli.py`, budget tests.

Expose bounded attempted-cost diagnostics on `BudgetLimitExceeded`, and centralize the
model reservation formula. Keep reserve-before-call, failed-call retention, successful
usage reconciliation, hard call ceilings, and the USD 0.15 diagnostic cap. Use a smaller
run-specific maximum model output only because observed tool turns are far below 1,600
tokens; do not increase any cost ceiling.

- [x] RED: successful model reservations reconcile once, fixed search cost is counted once,
  prospective cost never exceeds the cap, a true over-budget request stays blocked, and
  diagnostics identify current/attempted/projected amounts.
- [x] GREEN: add typed budget diagnostics and bind the B3 diagnostic model output limit through
  policy rather than a global relaxation.

## 3. Prove the repaired handoff with an offline replay

Files: runtime replay/agent tests and `docs/status/QUALOR-03.md`.

Use recorded synthetic search and source observations with a deterministic Strands test
model. Exercise search, a rejected reference, recovery with a returned candidate ID, fetch,
structured claim admission, deterministic eligibility, and deterministic decision. Assert
zero AWS calls, at least one EvidenceRecord, a critical rule linked to it, citations, and a
bounded judge-readable trace. Search snippets remain discovery-only. **Completed:** one
recorded search, one recoverable rejected reference, one fetch, one admitted critical claim,
and deterministic `FAIL / SKIP`, with zero AWS calls.

## 4. Verification and checkpoint

Run focused tests at RED and GREEN, then all required local gates: Ruff, pytest, repository
verify, read-only AWS preflight, schema export, TypeScript generation, npm clean install/build,
secret scan, and Git whitespace/status checks. Commit and push only the minimal QUALOR-03B3E
changes to `qualor-03-live-agent`. No live dogfood run, Web Search, Bedrock inference,
infrastructure mutation, PR, merge, or QUALOR-04A work.
