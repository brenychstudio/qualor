# QUALOR-04A Decision Intelligence Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the persistent, functional, final-grade QUALOR Decision Intelligence Workspace: Inbox → Decision → Why/Proof → Activity → human approval → Draft Pack.

**Architecture:** Preserve the existing deterministic QUALOR core and live agent pipeline. Add a transactional SQLite persistence boundary and read-oriented API layer, then build the approved React workspace on top. Owner-approved change record `QUALOR-04A-A1_2-CANONICAL-RULING-01B` (`docs/decisions/0004-a1-2-four-zone-workspace-body.md`) supersedes the three-zone wording this plan was originally written against: the accepted wide-body layout at 1280 px and above is four zones — Opportunity Inbox, Decision Canvas, Why & Proof / Evidence Plane, Intelligence Rail. Approval and Draft Pack remain version-bound, bounded and non-submitting.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLite, React, TypeScript, Vite, Tailwind v4, existing generated QUALOR schemas/types.

**Spec:**
`docs/superpowers/specs/2026-09-07-qualor-04a-decision-intelligence-workspace-design.md`

## Sources and repository facts

This plan applies the approved design spec and the canonical brief sections for architecture, contracts, evidence, run state, approval, local API security, interface quality, testing, and the Sprint 2 acceptance gate. The canonical brief remains byte-for-byte unchanged.

The implementation starts from these verified repository facts:

- Python code lives in `src/qualor`. `src/qualor/api.py` currently owns a module-level FastAPI app with `/health` and two development-only fixture routes. `src/qualor/cli.py` owns the Typer entry point.
- The existing strict, frozen Pydantic contracts live under `src/qualor/domain`; deterministic eligibility and decision authority live under `src/qualor/eligibility` and `src/qualor/decisions`.
- `src/qualor/runtime/run_models.py` defines `StudioInput`, bounded `TraceEvent`, and `AgentRunResult`. These are execution contracts, not durable `RunRecord` or `RunEvent` entities.
- `src/qualor/runtime/replay.py` provides recorded search/fetch observations. Runtime modes already distinguish `FIXTURE`, `REPLAY`, and `LIVE`.
- No persistence package, SQLite helper, ORM, migration tool, approval model, draft-pack model, frontend router, frontend API client, or frontend test runner exists.
- JSON Schema export is centralized in `src/qualor/schemas/export.py`; `scripts/export-schemas.ps1` and `apps/web/scripts/generate-domain.mjs` produce canonical schemas and `apps/web/src/generated/domain.ts`.
- The frontend is currently `apps/web/src/main.tsx` plus `apps/web/src/index.css`. `apps/web/vite.config.ts` has React and Tailwind v4 plugins. `apps/web/package.json` has no router or test dependencies.
- Backend API tests use `httpx.ASGITransport` and `AsyncClient`. CI runs `scripts/verify.ps1`, which covers Ruff, pytest, schema/type drift, web typecheck/build, canonical hash, secrets, whitespace, and a clean worktree.

## Non-negotiable product and authority constraints

- `PRODUCT_ARCHETYPE=DECISION_INTELLIGENCE_WORKSPACE`
- `VISUAL_DIRECTION=HYBRID_DARK_FIRST`, `DARK_WORKSPACE_PERCENT=85`, and `LIGHT_PROOF_PERCENT=15`.
- Dark is where QUALOR thinks. Light is where QUALOR proves.
- `DESKTOP_FIRST=YES`, with a readable 320–1440 px baseline and no separate mobile workflow.
- `PROGRESSIVE_INTELLIGENCE=DECISION -> WHY -> PROOF`.
- `STRANDS_FINAL_ELIGIBILITY_AUTHORITY=NO` and `STRANDS_FINAL_RECOMMENDATION_AUTHORITY=NO`.
- `NO_EXTERNAL_SUBMISSION=YES`; the only V1 approved consequential action is `GENERATE_DRAFT_PACK`.
- `UI_LANGUAGE=ENGLISH`.
- `ACTIVITY_DOMAIN_SOURCE=RUN_RECORD_AND_RUN_EVENT`; Activity is a presentation of persisted `RunRecord` and `RunEvent`, never a parallel domain model or chat transcript.
- Strategy is prioritization, not probability of winning. Unknown strategy renders `Not enough evidence`; it never renders an invented number.
- `UNKNOWN != PASS`. The UI must preserve incomplete evidence and `QUALOR-05-HARDEN-CLAIM-NORMALIZER-COVERAGE` as truthful `WATCH`, `UNKNOWN`, or incomplete coverage.
- Development uses `FIXTURE` and `REPLAY`. Any later live acceptance is a separately authorized, bounded task. QUALOR-04A creates no AWS infrastructure and routine verification makes no paid AWS calls.
- No task may add a generic CRUD surface, external submission, broad workflow engine, multi-user system, vector database, or multi-agent orchestration.

## Target module boundaries and dependency direction

Use the standard-library `sqlite3` module because no ORM or migration framework exists. Keep dependencies flowing in this direction:

```text
domain + deterministic engines + runtime contracts
                      ↓
workspace contracts and policies
                      ↓
persistence repositories + workspace service
                      ↓
FastAPI read/action routes
                      ↓
generated TypeScript contracts + React feature modules
```

New Python packages:

- `src/qualor/persistence`: connection lifecycle, embedded versioned SQL migrations, and typed repositories.
- `src/qualor/workspace`: durable records, version/dedup policy, approval policy, drafting boundary, UI read models, service composition, and API router.

The persistence layer stores validated Pydantic JSON plus explicit indexed identity, version, state, sequence, and timestamp columns. Every read revalidates the Pydantic payload. API handlers call workspace services and never contain raw SQL.

The initial UI routes are `/inbox`, `/inbox/:opportunityId`, `/portfolio`, `/activity`, and `/draft-packs/:packId`. Add `react-router-dom` because these are durable product locations. Add Vitest, jsdom, Testing Library, and user-event for component behavior. Add Playwright only in the final acceptance task for the canonical browser flow. Do not add a component framework or animation library.

The product API is rooted at `/api/v1` and is task-oriented:

- `GET /api/v1/inbox`
- `GET /api/v1/portfolio`
- `PUT /api/v1/profile`
- `PUT /api/v1/projects/{project_id}`
- `GET /api/v1/opportunities/{opportunity_id}/workspace`
- `GET /api/v1/opportunities/{opportunity_id}/evidence`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}/events`
- `GET /api/v1/session`
- `POST /api/v1/opportunities/{opportunity_id}/approvals`
- `POST /api/v1/approvals/{approval_id}/confirm`
- `GET /api/v1/approvals/{approval_id}`
- `GET /api/v1/draft-packs/{pack_id}`

State-changing routes require a per-process action token, a loopback client, and an allowed `Origin`. The Vite proxy targets `http://127.0.0.1:8000`; CORS remains restricted. A read-only demo configuration does not register action routes. No anonymous route can trigger a paid run.

## Delivery order and review rule

Execute the 16 tasks in order. Each task uses RED → GREEN → REFACTOR, ends with focused and related regression evidence, and creates one independently reviewable commit. Generated schemas/types belong in the task that changes their source contract. Do not batch all work into one commit. Before every commit, run `git diff --check`; before completion, run the full verification in Task 16.

## Task 1: SQLite persistence foundation

**Prize-first value:** trust and usability through durable, transactional product state.

**Files:**

- Create: `src/qualor/persistence/__init__.py`
- Create: `src/qualor/persistence/database.py`
- Create: `src/qualor/persistence/migrations.py`
- Create: `src/qualor/workspace/__init__.py`
- Create: `src/qualor/workspace/models.py`
- Modify: `src/qualor/settings.py` to add a local database path with an ignored `.qualor/local/qualor.db` default
- Test: `tests/persistence/test_database.py`
- Test: `tests/workspace/test_models.py`

**Interfaces:**

- Consumes: existing `Record`, `UtcInstant`, `FounderProfile`, `ProjectProfile`, `OpportunityRecord`, `EvidenceRecord`, `DecisionRecord`, and runtime mode vocabulary.
- Produces: `Database(path: Path)`, `Database.connect()`, `Database.transaction()`, `migrate(connection)`, `RunState`, `RunRecord`, `RunEvent`, `ApprovalAction`, `ApprovalState`, `ApprovalRecord`, `DraftJobState`, `DraftJobRecord`, `DraftPackSection`, and immutable `DraftPack`.

`Database.connect()` must set `PRAGMA foreign_keys=ON`, `journal_mode=WAL` for file databases, `busy_timeout`, and `sqlite3.Row`. `Database.transaction()` begins one explicit transaction, commits once, rolls back every exception, and never commits inside a repository method. `migrations.py` owns ordered immutable migrations and a `schema_migrations(version, applied_at)` gate. Migration 1 creates separate tables for founder profiles, project profiles, opportunity versions, evidence, decisions, runs, run events, approvals, draft jobs, and draft packs, with foreign keys and uniqueness constraints. Do not add Alembic or an ORM.

`RunState` is exactly `CREATED`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED`, `CANCELLED`, `BUDGET_STOPPED`. `RunEvent` is append-only and has `run_id`, monotonically increasing `sequence`, bounded event type/payload, mode, and UTC timestamp. It stores judge-safe telemetry, never chain-of-thought or raw source pages.

- [ ] Write RED tests proving a new database migrates once, re-opening is idempotent, an unsupported future schema version fails closed, foreign keys are active, and an exception rolls back all writes. Add strict model tests for invalid run/approval/draft states and naive timestamps.
- [ ] Run focused tests with `uv run pytest tests/persistence/test_database.py tests/workspace/test_models.py -q` and confirm failures are caused by the absent modules.
- [ ] Implement the minimum connection, migration, and workspace record contracts. Keep SQL migration text centralized in `migrations.py`.
- [ ] Run the focused tests and confirm PASS.
- [ ] Refactor repeated JSON/timestamp helpers without moving transaction ownership into repositories.
- [ ] Run `uv run ruff check src/qualor/persistence src/qualor/workspace tests/persistence tests/workspace` and `uv run pytest tests/domain tests/runtime/test_runtime_gate.py tests/persistence tests/workspace -q`.
- [ ] Commit as `feat: add transactional workspace persistence foundation`, including only this slice.

## Task 2: Typed repositories and persistence services

**Prize-first value:** trust and decision comprehension through consistent version-linked records.

**Files:**

- Create: `src/qualor/persistence/repositories.py`
- Create: `src/qualor/workspace/store.py`
- Modify: `src/qualor/persistence/__init__.py`
- Modify: `src/qualor/workspace/__init__.py`
- Test: `tests/persistence/test_repositories.py`
- Test: `tests/workspace/test_store.py`

**Interfaces:**

- Consumes: `Database`, the canonical domain records, and Task 1 workspace records.
- Produces: `ProfileRepository`, `ProjectRepository`, `OpportunityRepository`, `EvidenceRepository`, `DecisionRepository`, `RunRepository`, `ApprovalRepository`, `DraftPackRepository`, and a transaction-scoped `WorkspaceStore` facade.

Repositories expose typed operations, including `put_founder`, `put_project`, `put_opportunity_version`, `put_evidence`, `put_decision`, `create_run`, `append_run_event`, `put_approval`, `revoke_approval`, `put_draft_job`, and `put_draft_pack`. Load methods return validated models. `append_run_event` allocates the next sequence in the same transaction and rejects mutation/deletion. `DraftPackRepository` is immutable after insertion. API handlers must never receive a database connection.

- [ ] Write RED repository tests that round-trip every canonical entity, reject duplicate event sequences, reject mutation of a Draft Pack, revalidate corrupted JSON, and reconstruct opportunity evidence/decision/run links after closing and reopening SQLite.
- [ ] Run focused tests with `uv run pytest tests/persistence/test_repositories.py tests/workspace/test_store.py -q` and confirm the missing repository boundary is the failure.
- [ ] Implement the smallest parameterized SQL and typed serialization helpers. Use explicit column lists and `json.dumps(model_dump(mode="json"), sort_keys=True)`.
- [ ] Run the focused tests and confirm PASS.
- [ ] Refactor only duplicated row/model conversion while retaining entity-specific repositories.
- [ ] Run `uv run pytest tests/persistence tests/workspace/test_store.py tests/domain tests/decisions -q` and Ruff on changed paths.
- [ ] Commit as `feat: add typed workspace repositories`.

## Task 3: Deduplication, versioning, stale evidence, and restart semantics

**Prize-first value:** trust by showing history and failed refreshes truthfully.

**Files:**

- Create: `src/qualor/workspace/versioning.py`
- Create: `src/qualor/workspace/lifecycle.py`
- Modify: `src/qualor/workspace/store.py`
- Test: `tests/workspace/test_versioning.py`
- Test: `tests/workspace/test_restart_semantics.py`

**Interfaces:**

- Consumes: canonical `OpportunityRecord`, linked evidence/decisions, `WorkspaceStore`, and a caller-supplied aware timestamp.
- Produces: `opportunity_semantic_digest(record) -> str`, `persist_observation(record) -> OpportunityVersionResult`, `mark_refresh_failed(opportunity_id, failed_at)`, and `reconstruct_workspace(opportunity_id, now) -> WorkspaceAggregate`.

The semantic digest covers normalized critical opportunity content and excludes retrieval-only timestamps. Identical content reuses the existing version and Inbox identity. A meaningful rules/deadline/reward/license/project-policy change appends a new opportunity version and retains old decisions/evidence. Failed refresh preserves the prior snapshot, sets its product freshness to `STALE`, records the failure time, and never updates an actionability timestamp. Restart reconstruction validates all version links and computes approval validity instead of trusting stored presentation state.

- [ ] Write RED tests for an unchanged observation producing no duplicate, a critical change producing a new version with retained history, failed refresh preserving evidence while returning `STALE`, and a process restart reconstructing the same Inbox/decision/evidence links.
- [ ] Run `uv run pytest tests/workspace/test_versioning.py tests/workspace/test_restart_semantics.py -q` and confirm expected failures.
- [ ] Implement the digest and lifecycle service inside one database transaction per observation/refresh result.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor the list of critical digest fields into a named versioned policy constant; do not compare whole serialized records accidentally.
- [ ] Run `uv run pytest tests/workspace tests/eligibility/test_freshness.py -q` and Ruff.
- [ ] Commit as `feat: persist opportunity versions and stale state`.

## Task 4: Version-bound approval lifecycle

**Prize-first value:** trust and usability through an explicit human control boundary.

**Files:**

- Create: `src/qualor/workspace/approval.py`
- Modify: `src/qualor/workspace/models.py`
- Modify: `src/qualor/workspace/store.py`
- Test: `tests/workspace/test_approval.py`

**Interfaces:**

- Consumes: actor ID, opportunity content hash and version, founder/profile version, project version, deterministic policy versions, action, opportunity deadline, and caller-supplied UTC time.
- Produces: `request_approval(actor_id, opportunity_hash, opportunity_version, profile_version, project_version, policy_versions, action, deadline, now) -> ApprovalRecord`, `confirm_approval(approval_id, idempotency_key, now) -> ApprovalRecord`, `validate_approval(approval_id, expected_versions, now) -> ApprovalValidation`, and `revoke_invalid_approvals(change, now) -> tuple of ApprovalRecord`.

The only allowed action is `GENERATE_DRAFT_PACK`. Default expiry is `min(now + 24 hours, exact opportunity deadline)`; a calendar-only deadline does not invent a timezone and leaves the 24-hour bound. Approval binds actor, opportunity hash/version, founder version, project version, all deterministic policy versions, action, and expiry. Confirmation is idempotent for the same key, one-time for side effects, and fail-closed for expiry, revocation, version mismatch, or action mismatch. Critical changes to rules, profile, project, license, or policy revoke a prior approval.

- [ ] Write RED tests for valid confirmation, default/deadline expiry, revoked approval, each version mismatch, action mismatch, one-time consumption, and same-key idempotent retry returning the original result.
- [ ] Run `uv run pytest tests/workspace/test_approval.py -q` and confirm the absent policy fails.
- [ ] Implement the minimum pure approval policy plus transactional repository orchestration.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor reason codes into a bounded enum used by later API read models.
- [ ] Run `uv run pytest tests/workspace tests/decisions -q` and Ruff.
- [ ] Commit as `feat: add version-bound draft approval`.

## Task 5: New bounded Draft Pack job

**Prize-first value:** demo impact and trust through a visible human-approved transition from judgment to preparation.

**Files:**

- Create: `src/qualor/workspace/drafting.py`
- Create: `src/qualor/workspace/draft_templates.py`
- Modify: `src/qualor/workspace/models.py`
- Modify: `src/qualor/workspace/store.py`
- Test: `tests/workspace/test_drafting.py`

**Interfaces:**

- Consumes: a confirmed valid `ApprovalRecord`, completed source `RunRecord`, version-matched opportunity/profile/project/decision/evidence, and a caller-supplied UTC timestamp.
- Produces: `DraftAuthor` protocol, `DeterministicDraftAuthor`, and `start_draft_job(approval_id, idempotency_key, now) -> DraftJobResult` containing a new bounded `DraftJobRecord` and immutable `DraftPack`.

The source research run must already be terminal. Drafting creates a distinct job/run identity; it never resumes the Strands or cloud session that produced the decision. The initial `DeterministicDraftAuthor` composes only persisted, already-approved facts and explicit missing-field markers, making routine development fully offline. A future model-backed author may implement the protocol only in a separately authorized task with its own budget guard. Facts and exact evidence remain authoritative; generated or templated narrative is visibly draft prose.

The pack has seven ordered sections: `SUBMISSION_SUMMARY`, `PROJECT_FIT_NARRATIVE`, `ELIGIBILITY_CHECKLIST`, `REQUIRED_DELIVERABLES`, `EVIDENCE_REFERENCES`, `READINESS_GAPS`, and `SUGGESTED_APPLICATION_ANSWERS`. It retains approval ID, opportunity/profile/project versions, policy versions, source/evidence references, missing fields, creator kind, creation timestamp, and pack version. It contains no send/submit destination.

- [ ] Write RED tests proving drafting requires a terminal source run and confirmed valid approval; creates a new job identity; consumes approval once; returns the same pack for an idempotent retry; rejects expired/revoked/version-mismatched approvals; includes all seven ordered sections and source references; and stores missing fields without inventing answers.
- [ ] Run `uv run pytest tests/workspace/test_drafting.py -q` and confirm the drafting boundary is absent.
- [ ] Implement the protocol, deterministic author, and one transaction that consumes approval and persists job plus immutable pack.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor section assembly into named pure functions while keeping all factual inputs explicit.
- [ ] Run `uv run pytest tests/workspace tests/decisions tests/eligibility -q` and Ruff.
- [ ] Commit as `feat: add bounded approved draft pack job`.

## Task 6: Product read models and protected FastAPI routes

**Prize-first value:** clarity and security by giving the UI purpose-built truthful views rather than internal payload dumps.

**Files:**

- Create: `src/qualor/workspace/read_models.py`
- Create: `src/qualor/workspace/service.py`
- Create: `src/qualor/workspace/api.py`
- Create: `src/qualor/api_security.py`
- Modify: `src/qualor/api.py` to install restricted CORS and include the workspace router
- Modify: `src/qualor/settings.py` for allowed origins, read-only demo mode, and a process-local action-token source
- Modify: `src/qualor/cli.py` to add a loopback-only `serve` command
- Modify: `src/qualor/schemas/export.py` to export public workspace read/action contracts
- Test: `tests/workspace/test_read_models.py`
- Test: `tests/test_workspace_api.py`
- Test: `tests/domain/test_schema_export.py`
- Regenerate: `schemas/*.schema.json`
- Regenerate: `apps/web/src/generated/domain.ts`

**Interfaces:**

- Consumes: typed repositories/services, deterministic `DecisionRecord`, exact `EvidenceRecord`, `RunRecord`/`RunEvent`, approval state, and Draft Pack state.
- Produces: `PortfolioView`, `ProfileUpdateRequest`, `ProjectUpdateRequest`, `InboxResponse`, `InboxItem`, `OpportunityWorkspaceResponse`, `DecisionCanvasView`, `EvidenceSheetView`, `ActivityResponse`, `ApprovalRequest`, `ApprovalView`, `DraftPackView`, and the `/api/v1` routes listed in the target boundary.

`WorkspaceService` maps domain state to UI state without recalculating eligibility or recommendation. `DecisionCanvasView.strategy` carries either the deterministic score with `PRIORITIZATION_NOT_WIN_PROBABILITY` or a `NOT_ENOUGH_EVIDENCE` state. Reward kind, exact deadline/timezone status, effort range, primary blocker, and freshness remain available through progressive detail. Evidence views contain exact excerpts and citations but omit raw pages, HMAC keys, and model reasoning. Technical provenance is a separate optional bounded view.

Mutating routes require all three checks: loopback client, configured allowed `Origin`, and `X-QUALOR-Action-Token`. Generate the token in memory at process start; never persist or log it. `qualor serve` binds `127.0.0.1` and prints only the local URL. When `QUALOR_READ_ONLY_DEMO=true`, action routes return 404. Existing `/dev/*` fixture routes remain development-only and unchanged in authority.

- [ ] Write RED read-model tests for complete, unknown, stale, partial, and no-decision inputs. Write API tests for every route, response schema, 404 ownership boundaries, restricted origin, loopback requirement, missing/wrong action token, read-only demo rejection, and no route capable of external submission.
- [ ] Run `uv run pytest tests/workspace/test_read_models.py tests/test_workspace_api.py -q` and confirm missing contracts/routes fail.
- [ ] Implement read models, service composition, action guard, and exact task-oriented routes. Keep database creation in an app lifespan/factory rather than import side effects.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor repeated HTTP-to-service error conversion into one bounded adapter while keeping authorization checks on every mutating route.
- [ ] Export only the new public contracts, run `./scripts/export-schemas.ps1` and `./scripts/generate-types.ps1`, and inspect generated TypeScript for duplicate or weakened types.
- [ ] Run `uv run pytest tests/test_api_health.py tests/test_fixture_adapters.py tests/test_workspace_api.py tests/workspace -q`, `uv run ruff check .`, and both schema/type check modes.
- [ ] Commit as `feat: expose protected workspace read API`, including the Python, tests, schemas, and generated types.

## Task 7: React routing, test harness, tokens, and workspace shell

**Prize-first value:** clarity, usability, and a premium foundation that 04B can refine without restructuring.

**Files:**

- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/layout/WorkspaceShell.tsx`
- Create: `apps/web/src/features/portfolio/PortfolioView.tsx`
- Create: `apps/web/src/features/portfolio/ProfileForm.tsx`
- Create: `apps/web/src/features/portfolio/PortfolioView.test.tsx`
- Create: `apps/web/src/styles/tokens.css`
- Create: `apps/web/src/styles/base.css`
- Create: `apps/web/src/test/setup.ts`
- Create: `apps/web/src/layout/WorkspaceShell.test.tsx`
- Create: `apps/web/vitest.config.ts`
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/index.css`
- Modify: `apps/web/vite.config.ts` to proxy `/api` to loopback in development
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`

**Interfaces:**

- Consumes: generated workspace types and JSON responses under `/api/v1`.
- Produces: stable routes `/inbox`, `/inbox/:opportunityId`, `/portfolio`, `/activity`, `/draft-packs/:packId`; `WorkspaceShell`; a functional version-aware Portfolio surface; typed `apiRequest<T>`; semantic design tokens; and `npm run test:run`.

Add pinned `react-router-dom`. Add pinned Vitest, jsdom, `@testing-library/react`, `@testing-library/user-event`, and `@testing-library/jest-dom` development dependencies. The shell owns minimal Inbox/Portfolio/Activity navigation and the accepted body zones. This task was originally planned as three semantic regions; the A1.2 Spatial Precision pass separated proof from telemetry, and the accepted contract recorded in `QUALOR-04A-A1_2-CANONICAL-RULING-01B` is four semantic regions. At 1280 px and above the shell renders supporting inbox, dominant canvas, supporting Why & Proof plane, and supporting Intelligence Rail; at narrower widths the rail becomes a user-invoked panel and the content order remains Decision → Why/Proof → Activity. Do not add a component kit or animation dependency.

The Portfolio route reads the persisted founder and project versions and supports the bounded canonical profile/project fields needed by existing deterministic evaluation. Saving uses the protected version-aware API and reports a version conflict rather than overwriting newer state. This is a restrained profile workspace, not a new CRM or settings product.

Tokens must name semantic roles for warm graphite workspace, tonal surfaces, divider, text hierarchy, proof paper/ink, citation, focus, recommendation personalities, spacing, and reduced motion. Recommendation meaning must also appear in text. Avoid pure black, neon gradients, excessive translucent panels, card grids, and generic Tailwind starter composition.

- [ ] Write RED shell tests that assert landmark order, selected navigation, 320 px content availability, the desktop body-zone classes accepted in `QUALOR-04A-A1_2-CANONICAL-RULING-01B`, keyboard-visible navigation, and reduced-motion class behavior. Write Portfolio tests for loading persisted versions, saving canonical fields with an action token, validation errors, and stale-version conflict. Confirm `npm --prefix apps/web run test:run -- WorkspaceShell PortfolioView` fails before the harness exists.
- [ ] Implement the minimum foundation by installing only the listed pinned dependencies and creating the test setup, router, API client, tokens, Portfolio view, and shell with semantic HTML.
- [ ] Run the focused shell test and confirm PASS.
- [ ] Refactor layout/token names so components consume semantic roles instead of raw color values.
- [ ] Run focused shell and Portfolio tests, then run `npm --prefix apps/web run test:run`, `npm --prefix apps/web run typecheck`, and `npm --prefix apps/web run build`.
- [ ] Run `git diff --check` and confirm no backend contract changed.
- [ ] Commit as `feat: establish QUALOR workspace foundation`.

## Task 8: Opportunity Inbox priority queue

**Prize-first value:** decision comprehension and usability within the first five seconds.

**Files:**

- Create: `apps/web/src/features/inbox/OpportunityInbox.tsx`
- Create: `apps/web/src/features/inbox/OpportunityRow.tsx`
- Create: `apps/web/src/features/inbox/inbox-state.ts`
- Create: `apps/web/src/features/inbox/OpportunityInbox.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/layout/WorkspaceShell.tsx`

**Interfaces:**

- Consumes: `InboxResponse` with deterministic priority keys, pipeline state, recommendation, deadline, best-project state, freshness, and selected opportunity ID.
- Produces: `OpportunityInbox`, URL-backed selection, `InboxSort = PRIORITY | DEADLINE | NEWEST | DECISION`, `InboxFilter = ALL | APPLY | PREPARE | WATCH | SKIP`, and bounded title/organizer search.

Render a vertical queue, not a card grid. Decision is primary; pipeline state is quiet metadata. Pipeline presentation maps persisted states into `DISCOVERED`, `VERIFYING`, `EVALUATED`, or `NEEDS_REVIEW` without modifying the decision. Priority sort consumes the deterministic server priority key rather than inventing client AI ranking. Preserve `NO_RESULTS`, incomplete/unknown best project, stale, and partial state. Rows use roving keyboard selection and synchronize the selected ID into the URL.

- [ ] Write RED tests for deterministic default order, all sort modes, all filters, case-insensitive title/organizer search, URL selection, arrow/Home/End keyboard behavior, unknown best project, no results, partial run metadata, and non-color decision labels.
- [ ] Run `npm --prefix apps/web run test:run -- OpportunityInbox` and confirm the feature is missing.
- [ ] Implement pure filter/sort functions, row semantics, controls, and shell integration with the minimum visual treatment.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor repeated date/state formatting into typed local helpers; never infer a timezone.
- [ ] Run all web tests, typecheck, and build.
- [ ] Commit as `feat: add decision-priority opportunity inbox`.

## Task 9: Decision Canvas

**Prize-first value:** immediate decision comprehension, trust, and a strong judge-facing product story.

**Files:**

- Create: `apps/web/src/features/decision/DecisionCanvas.tsx`
- Create: `apps/web/src/features/decision/decision-copy.ts`
- Create: `apps/web/src/features/decision/DecisionCanvas.test.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**

- Consumes: `DecisionCanvasView`, selected opportunity context, and callbacks for `Why this decision` and the one allowed primary action.
- Produces: the dominant recommendation surface, concise reason, Strategy semantics, four core facts, readiness summary, contextual metadata, and state-appropriate CTA.

Level 1 shows recommendation, one reason line, Strategy, best project, eligibility, effort, deadline, readiness summary, `Why this decision`, and exactly one dominant action. Program/edition, reward type, deadline timezone state, most important blocker, and freshness remain available in quiet context or Level 2. Strategy displays its numeric value only when the deterministic record has a score; otherwise it says `Not enough evidence`. It never uses a gauge, radar, speedometer, progress bar, or win-probability language.

CTA mapping is exact: APPLY → `Approve application`; PREPARE → `Approve preparation`; WATCH → `Resolve unknowns`; SKIP → `Review rejection`. Active/incomplete runs show operational state and no fabricated recommendation or approval action.

- [ ] Write RED tests for all four recommendations, unknown Strategy, unresolved best project, exact effort ranges, date-with-timezone versus date-only, blocker/freshness detail, active run with no recommendation, one-primary-action invariant, and every CTA label/action.
- [ ] Run `npm --prefix apps/web run test:run -- DecisionCanvas` and confirm expected failure.
- [ ] Implement the semantic canvas and state-copy mapping without decorative chart components.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor recommendation visual classes into token-driven variants while retaining text labels.
- [ ] Run all web tests, typecheck, and build.
- [ ] Commit as `feat: add deterministic decision canvas`.

## Task 10: Warm-light Evidence Sheet

**Prize-first value:** evidence comprehension and trust through exact official proof.

**Files:**

- Create: `apps/web/src/features/evidence/EvidenceSheet.tsx`
- Create: `apps/web/src/features/evidence/EvidenceClaim.tsx`
- Create: `apps/web/src/features/evidence/TechnicalProvenance.tsx`
- Create: `apps/web/src/features/evidence/EvidenceSheet.test.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**

- Consumes: `EvidenceSheetView`, evidence-section groups, exact excerpt/citation/freshness, optional bounded technical provenance, open state, and the trigger element reference.
- Produces: a focus-managed warm-paper proof layer with sections `Eligibility`, `Project Fit`, `Constraints & Conflicts`, and `Reward & Deadline`.

The dark workspace stays visible and de-emphasized behind the sheet. Claim blocks distinguish QUALOR interpretation from exact source excerpt and support `PASS`, `FAIL`, `UNKNOWN`, `CONFLICT`, and `STALE`. `View original` uses the preserved official citation URL. UNKNOWN states explain what remains unresolved; CONFLICT presents opposing evidence and review need; STALE preserves the prior snapshot without claiming renewed actionability. Source/span IDs, offsets, policy version, normalizer version, and extraction state appear only after the optional `Technical provenance` disclosure.

- [ ] Write RED tests for section order, all five evidence states, exact excerpt preservation, citation target and safe link attributes, technical-provenance disclosure, Escape close, trapped focus, initial focus, return focus, outside click policy, and reduced-motion behavior.
- [ ] Run `npm --prefix apps/web run test:run -- EvidenceSheet` and confirm expected failure.
- [ ] Implement the sheet with native dialog semantics or an accessible equivalent, warm-light tokens, and no generic modal-card composition.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor focus management into a small reusable hook only after tests pass.
- [ ] Run all web tests, typecheck, and build.
- [ ] Commit as `feat: add source-grounded evidence sheet`.

## Task 11: Persisted run capture, Activity, and Live Intelligence Rail

**Prize-first value:** autonomy and trust made visible through truthful operational history.

**Files:**

- Create: `src/qualor/workspace/run_capture.py`
- Modify: `src/qualor/runtime/loop.py` to accept an optional typed event sink without importing persistence
- Modify: `src/qualor/runtime/live_cli.py` to pass a configured sink when workspace persistence is enabled
- Modify: `src/qualor/workspace/service.py`
- Create: `apps/web/src/features/activity/IntelligenceRail.tsx`
- Create: `apps/web/src/features/activity/ActivityHistory.tsx`
- Create: `apps/web/src/features/activity/activity-presenter.ts`
- Create: `apps/web/src/features/activity/IntelligenceRail.test.tsx`
- Test: `tests/workspace/test_run_capture.py`
- Test: `tests/runtime/test_run_event_sink.py`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**

- Consumes: bounded runtime `TraceEvent`, `AgentRunResult`, budget counters, mode, timestamps, and persisted `RunRecord`/`RunEvent`.
- Produces: runtime-neutral `RunEventSink` protocol, `WorkspaceRunCapture`, `ActivityResponse`, `IntelligenceRail`, and full `/activity` history.

The runtime owns facts about what happened; the persistence adapter only maps bounded events and terminal results. `loop.py` receives a sink through dependency injection and defaults to an in-memory/no-op implementation so deterministic and replay tests stay isolated. It must not import SQLite or workspace repositories. Every captured event remains append-only and mode-labelled `LIVE`, `REPLAY`, or `FIXTURE`.

The rail is structured telemetry, never chat. It renders actual events such as opportunity discovered, official rules located, source verified, eligibility evaluated, project fit updated, and decision updated. Active state may show bounded call counts and estimated spend already present in records. `BUDGET_STOPPED`, `DISCONNECTED_LIVE_PROVIDER`, `PARTIAL`, and `FAILED` render exact persisted state. No timer invents progress and no fixture/replay event is presented as live.

- [ ] Write RED backend tests that map a bounded event exactly once, retain order/mode/counters, omit hidden reasoning/raw page bodies, and persist terminal states including budget stop and provider disconnect. Write RED UI tests for event order, mode labels, degraded states, cost/call display, no chat vocabulary, and no fabricated activity when events are absent.
- [ ] Run `uv run pytest tests/workspace/test_run_capture.py tests/runtime/test_run_event_sink.py -q` and `npm --prefix apps/web run test:run -- IntelligenceRail`; confirm both missing boundaries fail.
- [ ] Implement the protocol, adapter, service read model, presenter, rail, and Activity route.
- [ ] Run focused Python and frontend tests and confirm PASS.
- [ ] Refactor event-to-copy mapping into an exhaustive presenter that fails typecheck when a public event type is added.
- [ ] Run `uv run pytest tests/runtime tests/workspace -q`, all web tests, typecheck, build, and Ruff.
- [ ] Commit as `feat: persist and present QUALOR run activity`.

## Task 12: Human approval interface

**Prize-first value:** trust and usability through an unmistakable consequential-action checkpoint.

**Files:**

- Create: `apps/web/src/features/approval/ApprovalPanel.tsx`
- Create: `apps/web/src/features/approval/approval-copy.ts`
- Create: `apps/web/src/features/approval/ApprovalPanel.test.tsx`
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/features/decision/DecisionCanvas.tsx`
- Modify: `apps/web/src/App.tsx`
- Test: `tests/test_workspace_api.py`

**Interfaces:**

- Consumes: Decision Canvas CTA intent, `ApprovalRequest`, process-local action token, and server `ApprovalView`.
- Produces: `NOT_REVIEWED`, `PENDING_APPROVAL`, `APPROVED_FOR_PREPARATION`, `REVOKED_APPROVAL`, and `DRAFT_READY` UI states; protected request/confirm calls; and accessible error explanations.

The panel summarizes actor, approved action, version-bound opportunity/project context, expiry, and the fact that approval starts a new drafting job but submits nothing externally. Expired, version-changed, rules-changed, profile/project-changed, revoked, and already-consumed outcomes receive distinct server reason codes and English copy. The client supplies an idempotency key once per user intent and reuses it for network retry.

- [ ] Write RED API tests for request and confirm status mappings, read-only-demo rejection, and idempotent response IDs. Write RED UI tests for all approval states, keyboard confirmation/cancellation, expiry copy, version/revocation errors, duplicate-click suppression, and absence of submit/send language.
- [ ] Run the focused API and `ApprovalPanel` tests and confirm expected failures.
- [ ] Implement protected API client calls and the approval panel; wire only APPLY/PREPARE actions from the canvas.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor error copy into an exhaustive reason-code map and retain server authority.
- [ ] Run workspace API tests, all web tests, typecheck, build, and Ruff.
- [ ] Commit as `feat: add version-bound approval experience`.

## Task 13: Application Pack light document mode

**Prize-first value:** demo impact and usability by completing the discover → prove → approve → prepare story.

**Files:**

- Create: `apps/web/src/features/draft-pack/ApplicationPack.tsx`
- Create: `apps/web/src/features/draft-pack/DraftPackSection.tsx`
- Create: `apps/web/src/features/draft-pack/ApplicationPack.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/styles/tokens.css`
- Test: `tests/test_workspace_api.py`

**Interfaces:**

- Consumes: persisted `DraftPackView` from `GET /api/v1/draft-packs/{pack_id}` and the `DRAFT_READY` navigation target.
- Produces: `/draft-packs/:packId` warm-light document view with seven numbered sections, attribution/version metadata, source references, and explicit missing-field treatment.

The pack visually shifts from dark judgment to light documentation. It is review-oriented, not a rich editor. Exact evidence references remain distinguishable from non-authoritative draft prose. Missing fields stay visible. The view has no email, form-fill, Devpost, send, or external-submit action.

- [ ] Write RED API tests for ownership/not-found, immutable retrieval, version attribution, source references, and no submission fields. Write RED UI tests for seven-section order, approval attribution, missing fields, exact citation links, draft-prose labelling, finished state, direct URL reload, and no external-action control.
- [ ] Run focused API and `ApplicationPack` tests and confirm expected failures.
- [ ] Implement the read endpoint integration and light document components using proof tokens.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor section rendering without creating a generic document-editor abstraction.
- [ ] Run all web tests, typecheck, build, workspace API tests, and Ruff.
- [ ] Commit as `feat: add approved application pack document mode`.

## Task 14: Required product and error states

**Prize-first value:** trust and clarity when reality is incomplete, stale, disconnected, or blocked.

**Files:**

- Create: `src/qualor/workspace/product_state.py`
- Modify: `src/qualor/workspace/read_models.py`
- Modify: `src/qualor/workspace/service.py`
- Create: `apps/web/src/features/states/ProductStateSurface.tsx`
- Create: `apps/web/src/features/states/product-state.ts`
- Create: `apps/web/src/features/states/ProductStateSurface.test.tsx`
- Test: `tests/workspace/test_product_state.py`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**

- Consumes: profile presence, result count, latest run state, evidence freshness/coverage, eligibility, provider state, approval state, and Draft Pack state.
- Produces: one deterministic `ProductState` plus per-region presentation and allowed-action policy.

Implement this exhaustive behavior table. The server determines allowed actions; the client only presents them.

| State | Decision Canvas | Primary action | Evidence Sheet | Intelligence Rail | Approval/draft |
| --- | --- | --- | --- | --- | --- |
| `EMPTY_PROFILE` | Explain that evaluation needs a founder/project profile; no recommendation | `Create profile` | Unavailable | Quiet onboarding state | Disallowed |
| `NO_RESULTS` | No selected decision | `Adjust search` | Unavailable | Show completed discovery with zero results | Disallowed |
| `PARTIAL_SOURCE_FAILURE` | Preserve any verified decision but mark incomplete coverage | `Review available evidence` or `Resolve unknowns` | Available for verified records with partial warning | Show failed source and retained successes | Approval allowed only if server policy still returns actionable deterministic state |
| `STALE_EVIDENCE` | Preserve prior decision with stale warning and no renewed actionability | `Refresh evidence` | Available with stale timestamps | Show failed refresh event | New approval disallowed; existing approval revalidated/revoked |
| `UNKNOWN_ELIGIBILITY` | `WATCH`, unknown fields, no fake Strategy | `Resolve unknowns` | Available | Show incomplete evaluation | Disallowed |
| `BUDGET_STOPPED` | No fabricated completion; retain verified partial facts | `Review available evidence` | Available only for admitted evidence | Show exact budget stop | Disallowed unless a prior independently valid approval still passes server validation |
| `DISCONNECTED_LIVE_PROVIDER` | Last persisted state with disconnected marker | `Reconnect provider` | Prior persisted proof remains readable | Show disconnect, no fake progress | New approval disallowed until server validation succeeds |
| `PENDING_APPROVAL` | Decision remains visible | `Review approval` | Available | Show persisted approval request event | Draft not started |
| `REVOKED_APPROVAL` | Decision and revocation cause visible | `Review changes` | Available | Show revocation event | Draft disallowed |
| `FINISHED_PACK` | Decision remains attributable | `Open application pack` | Available | Show bounded drafting completion | Existing pack available; no external submit |

Run state and decision state remain separate. A `PARTIAL` run can contain verified evidence; it is never relabelled as `WATCH` unless the deterministic decision is actually WATCH. The healthy default view must not render the full error-state catalogue.

- [ ] Write RED server matrix tests for every state and precedence edge, including partial run plus APPLY decision, stale plus prior evidence, disconnected plus retained pack, and unknown normalization from the QUALOR-05 backlog. Write RED UI tests for each row's copy, action, sheet availability, rail state, and approval availability.
- [ ] Run focused backend and frontend state tests and confirm expected failures.
- [ ] Implement the pure state derivation policy and exhaustive presentation mapping.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor precedence into a documented ordered policy and verify no state changes deterministic recommendation authority.
- [ ] Run all workspace, API, and web tests plus typecheck/build/Ruff.
- [ ] Commit as `feat: add truthful workspace product states`.

## Task 15: Responsive and accessibility baseline

**Prize-first value:** usability, clarity, and professional product quality across the required viewing range.

**Files:**

- Create: `apps/web/src/a11y/useFocusReturn.ts`
- Create: `apps/web/src/a11y/useReducedMotion.ts`
- Create: `apps/web/src/a11y/accessibility.test.tsx`
- Modify: `apps/web/src/layout/WorkspaceShell.tsx`
- Modify: `apps/web/src/features/inbox/OpportunityInbox.tsx`
- Modify: `apps/web/src/features/decision/DecisionCanvas.tsx`
- Modify: `apps/web/src/features/evidence/EvidenceSheet.tsx`
- Modify: `apps/web/src/features/activity/IntelligenceRail.tsx`
- Modify: `apps/web/src/features/approval/ApprovalPanel.tsx`
- Modify: `apps/web/src/features/draft-pack/ApplicationPack.tsx`
- Modify: `apps/web/src/styles/base.css`
- Modify: `apps/web/src/styles/tokens.css`

**Interfaces:**

- Consumes: the completed workspace component surfaces and browser accessibility media/query APIs.
- Produces: keyboard-complete navigation, visible focus, semantic heading order, focus restoration, Escape behavior, reduced-motion variants, non-color-only status communication, contrast tokens, and readable layouts from 320 through 1440 px.

At 1280 px and above, retain the accepted four-zone composition — inbox, canvas, Why & Proof plane, Intelligence Rail. Between 768 and 1279 px, keep the canvas dominant, keep the inbox as a persistent column, move the Why & Proof plane below the canvas, and let Activity open as a user-invoked panel. Below 768 px, preserve the same content and action semantics in one readable sequence. Do not create a mobile-only information architecture or remove evidence/approval meaning.

- [ ] Write RED accessibility tests for landmarks/headings, complete Tab order, inbox roving focus, sheet focus trap/return, Escape, action names, status text independent of color, reduced-motion behavior, and 320/768/1024/1440 layout contracts. Add an automated contrast-token assertion for required text/background pairs.
- [ ] Run `npm --prefix apps/web run test:run -- accessibility` and confirm the incomplete baseline fails.
- [ ] Implement shared hooks and the minimum component/style changes needed to satisfy the tests.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor duplicate keyboard/media-query code into the two named hooks without changing content order.
- [ ] Run all web tests, typecheck, and production build; inspect the built app at 320, 768, 1024, and 1440 px with reduced motion on and off.
- [ ] Commit as `feat: complete workspace accessibility baseline`.

## Task 16: Sprint 2 end-to-end acceptance and final verification

**Prize-first value:** proof that the approved product story and restart safety work as one system.

**Files:**

- Create: `tests/fixtures/workspace/W01_DECISION_TO_DRAFT_PACK.json`
- Create: `tests/fixtures/workspace/W02_PARTIAL_STALE_WATCH.json`
- Create: `tests/e2e/test_workspace_lifecycle.py`
- Create: `apps/web/e2e/workspace.spec.ts`
- Create: `apps/web/playwright.config.ts`
- Modify: `src/qualor/cli.py` to add a development-only `seed-workspace-fixture` command for owned explicit fixture files
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Modify: `scripts/verify.ps1` to include frontend unit tests; keep browser E2E as a separately named local/CI gate
- Modify: `.github/workflows/ci.yml` to run the browser gate with local FIXTURE data and no AWS credentials
- Test: `tests/test_cli_doctor.py`

**Interfaces:**

- Consumes: the complete persistence, service, API, UI, approval, and drafting boundaries plus owned FIXTURE/REPLAY observations.
- Produces: one repeatable backend lifecycle acceptance and one browser judge-flow acceptance with zero AWS calls.

`seed-workspace-fixture` is local development tooling: it accepts an explicit owned JSON fixture path, validates `mode=FIXTURE`, persists through the same workspace services, and is disabled outside development. It cannot claim LIVE or accept authoritative result fields that bypass deterministic decision calculation. Playwright starts the loopback API with a temporary database, seeds W01, starts Vite, and exercises the real API through the browser.

The backend acceptance proves: profile/project persisted → opportunity/evidence persisted → deterministic decision persisted → Inbox/read models → Why/Proof → RunRecord/RunEvent Activity → version-bound approval → new bounded drafting job → immutable Draft Pack → database close/reopen → same valid state. It separately proves a critical version change revokes approval, failed refresh keeps evidence and marks STALE, and unchanged rerun produces no duplicate Inbox item.

The browser acceptance follows the approved demo: Inbox visible → open AWS Agents for Humans fixture → read decision/best project/effort/deadline → open Why this decision → inspect exact official evidence link → return to dark canvas → inspect Activity → approve preparation/application → open light Application Pack. It also checks English UI, no fake LIVE label, no external submission, and first-five-seconds hierarchy by asserting the primary elements are present without opening secondary detail.

- [ ] Write RED lifecycle and Playwright tests first. Confirm `uv run pytest tests/e2e/test_workspace_lifecycle.py -q` and `npm --prefix apps/web run test:e2e` fail because seed/acceptance integration is absent.
- [ ] Implement the minimum acceptance integration by adding pinned Playwright test tooling, owned sanitized fixtures, the guarded seed command, and local server configuration needed for the tests.
- [ ] Run focused lifecycle and browser tests and confirm PASS with network/AWS access denied in the test processes.
- [ ] Refactor fixture bootstrapping so browser and Python acceptance share the same canonical owned fixture without duplicating domain expectations.
- [ ] Run `./scripts/export-schemas.ps1`, `./scripts/generate-types.ps1`, `uv run ruff check .`, `uv run pytest -q`, `npm --prefix apps/web ci`, `npm --prefix apps/web run test:run`, `npm --prefix apps/web run build`, and `npm --prefix apps/web run test:e2e`.
- [ ] Run `./scripts/verify.ps1`, `git diff --check`, and `git status --short`. Verify no paid calls, AWS resources, external submission path, proprietary artifacts, raw pages, credentials, or chain-of-thought were introduced.
- [ ] Commit as `test: prove QUALOR workspace lifecycle`, including only the acceptance slice.

## Commit sequence

The intended implementation history is:

1. `feat: add transactional workspace persistence foundation`
2. `feat: add typed workspace repositories`
3. `feat: persist opportunity versions and stale state`
4. `feat: add version-bound draft approval`
5. `feat: add bounded approved draft pack job`
6. `feat: expose protected workspace read API`
7. `feat: establish QUALOR workspace foundation`
8. `feat: add decision-priority opportunity inbox`
9. `feat: add deterministic decision canvas`
10. `feat: add source-grounded evidence sheet`
11. `feat: persist and present QUALOR run activity`
12. `feat: add version-bound approval experience`
13. `feat: add approved application pack document mode`
14. `feat: add truthful workspace product states`
15. `feat: complete workspace accessibility baseline`
16. `test: prove QUALOR workspace lifecycle`

Generated schemas/types travel with their source-contract commit. If one task reveals a repository-local naming conflict, change the smallest local filename before implementation review and update this plan through the approved documentation process; do not redesign the product in code.

## 04A visual quality and 04B boundary

QUALOR-04A must already look intentional, restrained, editorial, and final-grade in structure. Review every UI task against these rejection criteria: generic admin dashboard, Tailwind starter look, badge soup, heavy glassmorphism, neon/cyberpunk AI styling, arbitrary widgets, chat-first activity, or disposable MVP CSS. Reject any of these during task review.

QUALOR-04B owns exact art-direction refinement, final typography/color tuning, motion choreography, micro-interactions, responsive refinement, and cinematic demo transitions. It must build on the route structure, the accepted four-zone wide-body composition, progressive disclosure, tokens, accessibility semantics, and product-state contracts delivered here. It must not rewrite 04A information architecture.

Every proposed UI feature must improve at least one of clarity, trust, decision comprehension, evidence comprehension, demo impact, or usability. Defer it when it improves none.

## Cost and cloud execution policy

All persistence, API, UI, and acceptance development uses FIXTURE or REPLAY. Unit, integration, browser, CI, schema, and build checks run without AWS credentials and with network providers denied. No task creates cloud resources. Any future live acceptance requires a separate owner-authorized task with explicit call and cost caps; this plan does not authorize one.

## Plan self-review

- `SPEC_COVERAGE=PASS`
- `APPROVED_IA_PRESERVED=YES`
- `APPROVED_VISUAL_DIRECTION_PRESERVED=YES`
- `PERSISTENCE_COMPLETE=YES`
- `RESTART_SEMANTICS_PLANNED=YES`
- `DEDUP_RERUN_PLANNED=YES`
- `STALE_EVIDENCE_PLANNED=YES`
- `APPROVAL_VERSIONING_PLANNED=YES`
- `APPROVAL_REVOCATION_PLANNED=YES`
- `DRAFT_JOB_BOUNDARY_PLANNED=YES`
- `INBOX_PLANNED=YES`
- `DECISION_CANVAS_PLANNED=YES`
- `EVIDENCE_SHEET_PLANNED=YES`
- `INTELLIGENCE_RAIL_PLANNED=YES`
- `APPLICATION_PACK_PLANNED=YES`
- `REQUIRED_STATES_PLANNED=YES`
- `ACCESSIBILITY_PLANNED=YES`
- `RESPONSIVE_PLANNED=YES`
- `04A_04B_BOUNDARY_PRESERVED=YES`
- `PLACEHOLDERS=0`
- `TODO=0`
- `TBD=0`
- `TYPE_CONSISTENCY=PASS`
- `PATHS_VERIFIED=PASS`
- `SCOPE_CREEP=NO`

The plan introduces no implementation code, database file, migration execution, AWS call, or product-concept change. It converts the approved spec into the 16 reviewable execution slices above.
