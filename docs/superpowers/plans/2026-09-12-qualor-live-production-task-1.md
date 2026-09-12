# QUALOR Live Opportunity Graph and Workspace Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Persist one authoritative LIVE runtime result as a complete, source-grounded
workspace opportunity graph without recomputing its decision.

**Architecture:** Compile one cached runtime decision bundle from admitted official
evidence, resolve its opportunity version before evaluation, and let the existing
workspace capture persist the same graph atomically. The operator CLI verifies the
isolated observer's persistence outcome after the agent returns.

**Tech Stack:** Python 3.12, Pydantic v2, SQLite, pytest, existing QUALOR deterministic
engines and FastAPI read API.

**Spec:**
`docs/superpowers/specs/2026-09-12-qualor-live-production-task-1-design.md`

## Global Constraints

- Base and branch are exactly the task-authorized values.
- `UNKNOWN != PASS`; no opportunity metadata or deadline is guessed.
- Deadline promotion requires an absolute timezone-aware instant.
- `decide()` runs once for the authoritative result and never in persistence.
- The run and approval chain bind only to the selected decision.
- Runtime observer exceptions remain isolated; the operator boundary verifies capture.
- FIXTURE, REPLAY, and LIVE remain distinct.
- No paid AWS call, infrastructure change, frontend change, push, or external submit.

---

### Task 1: Canonical LIVE opportunity compilation

**Files:**

- Create: `tests/runtime/test_live_opportunity_compilation.py`
- Modify: `src/qualor/runtime/normalization.py`
- Modify: `src/qualor/runtime/claims.py`
- Modify: `src/qualor/runtime/handoff.py`

**Interfaces:**

- Produces: `LiveDecisionBundle`, `compile_decision_bundle(run)`, and deterministic
  metadata/deadline normalization.

- [ ] Write failing tests asserting literal official organizer/program promotion,
  unsupported edition `UNKNOWN`, non-`unknown` canonical ID, RFC3339 UTC deadline,
  exact excerpt/URL/hash/retrieval time, and rejection of naive/ambiguous deadlines.
- [ ] Run `uv run pytest tests/runtime/test_live_opportunity_compilation.py -q` and
  confirm failure is caused by the absent bundle/compiler behavior.
- [ ] Implement the minimum generic normalization and compiler. The deadline parser
  accepts `YYYY-MM-DDTHH:MM:SSZ` or an explicit numeric offset and canonicalizes to a
  UTC-aware instant; it does not infer a timezone.
- [ ] Run the focused tests and existing claim/autonomous-loop tests until green.

### Task 2: Single decision authority and pre-decision versioning

**Files:**

- Modify: `src/qualor/runtime/loop.py`
- Modify: `src/qualor/runtime/run_models.py`
- Modify: `src/qualor/runtime/live_cli.py`
- Test: `tests/runtime/test_live_opportunity_compilation.py`

**Interfaces:**

- Consumes: `compile_decision_bundle(run)`.
- Produces: `OpportunityVersionResolver.resolve(record) -> OpportunityRecord`, cached
  bundle reuse, and `AgentRunResult.bundle`.

- [ ] Add failing tests with a counting deterministic compiler/decision seam proving
  evaluation plus finalization reuses one bundle and a resolver runs before decision.
- [ ] Run the focused test and confirm the duplicate-computation assertion fails.
- [ ] Cache a bundle by admitted-evidence revision and attach it to `AgentRunResult`.
  Invalidate only when a new evidence record is admitted.
- [ ] Run runtime tests and generated-contract drift checks.

### Task 3: Atomic workspace graph persistence

**Files:**

- Create: `tests/workspace/test_live_run_persistence.py`
- Modify: `src/qualor/workspace/run_capture.py`
- Modify: `src/qualor/runtime/live_cli.py`

**Interfaces:**

- Produces: `WorkspaceRunCapture.resolve_opportunity_version(record)`, retained
  `persistence_error`, and `require_persisted()`.

- [ ] Write failing tests that feed a runtime-produced bundle into capture and assert
  founder/projects/opportunity/evidence/all candidate decisions/run/events persist in
  one transaction; the run links only the selected decision and reopens identically.
- [ ] Add failing tests proving partial/budget/failed runs persist telemetry only and
  that an injected repository conflict is retained by the observer then raised by
  `require_persisted()`.
- [ ] Implement idempotent immutable profile/project writes, version verification,
  graph writes, selected-link construction, rollback, and retained failure state.
- [ ] Run workspace capture, repository, lifecycle, and service tests until green.

### Task 4: Explicit CLI persistence and existing API acceptance

**Files:**

- Modify: `src/qualor/cli.py`
- Modify: `tests/runtime/test_live_cli.py`
- Create: `tests/e2e/test_live_workspace_persistence.py`

**Interfaces:**

- Produces: `--workspace-database PATH` forwarding and offline LIVE-shaped workspace
  acceptance through `/api/v1/inbox`, workspace, evidence, and runs reads.

- [ ] Write failing CLI forwarding/fail-closed tests and a controlled-provider
  integration test that persists a LIVE graph without creating AWS clients.
- [ ] Run focused tests and confirm expected failures.
- [ ] Add the explicit CLI option and operator-boundary `require_persisted()` call.
- [ ] Run focused CLI/API/E2E tests and FIXTURE/REPLAY regressions until green.

### Task 5: Generated contracts, full verification, review, and commit

**Files:**

- Modify generated schemas/types only when the Pydantic contract export changes.

**Interfaces:**

- Produces: one clean reviewed commit based on the authorized SHA.

- [ ] Run schema export/type generation and verify generated artifacts are consistent.
- [ ] Run focused runtime/persistence/API tests, the full Python suite, frontend unit
  tests, browser E2E, typecheck, build, Ruff, `git diff --check`, and
  `scripts/verify.ps1`.
- [ ] Dispatch an independent reviewer against the task requirements and fix every
  Critical or Important finding with a failing regression test first.
- [ ] Re-run verification, audit changed files and canonical SHA-256, then create the
  single commit `feat: persist authoritative live opportunity runs`.
- [ ] Confirm the committed worktree is clean and has not been pushed.
