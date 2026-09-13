# Coverage-Driven Canonical Evidence Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove, without AWS execution, that the production acquisition/compiler can reach relevant archived official clauses and produce source-grounded executable authority within the existing call/cost limits.

**Architecture:** Index the entire fetched canonical document, track acquisition coverage separately from eligibility, and deterministically dispatch bounded section jobs. Generic adapters compile exact candidates into existing RuleCandidate/EvidenceRecord contracts; the existing evaluator and revision-cached decision bundle remain authoritative. Durable safe receipts and archived-source scheduling/reservation simulation prove progress without a paid run.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, existing Strands/Bedrock interfaces with offline transports, SQLite workspace repositories, existing JSON Schema/TypeScript generation, React/Vite/Vitest/Playwright regressions. No new service or dependency is planned.

**Spec:** [docs/superpowers/specs/2026-09-13-coverage-driven-canonical-evidence-compiler-design.md](../specs/2026-09-13-coverage-driven-canonical-evidence-compiler-design.md), owner-approved and normative.

## 2026-09-14 owner-authorized cost envelope amendment

This amendment has precedence over every cost-cap statement in this plan for
current Task 5F work, from Task 12B onward.

Task 12 measured, with the exact captured Task 11 requests and the production
estimator, a conservative canonical worst case of **USD 0.306591** (model
reservations 0.297591 + search 0.009000 + fetch 0.000000) with no reconciliation
assumed. Under `QUALOR_03B3`'s USD 0.20 ceiling the guard refused the sixth model
request. That measured blocker is accepted evidence and is not rewritten.

On 2026-09-14 the owner authorized a new explicitly named current policy,
`QUALOR_5F`: inference ceiling 9 (unchanged), cost ceiling **USD 0.35**,
measured headroom USD 0.043409. The historical `QUALOR_03B3` USD 0.20
authorization remains intact and unchanged, as does the diagnostic policy.

Task ownership:

- Task 12 owns the original measurement and its recorded blocker.
- Task 12B owns the policy transition and the re-verification against `QUALOR_5F`.

Task 1-11 reports stating USD 0.20 describe the authorization in force when they
were written and are NOT retroactively restated. Every other limit in the Global
Constraints below - `INFERENCE_CALL_CEILING=9`, `MAX_EXTRACTED_CLAIMS_PER_CALL=2`,
max steps 24, failure threshold 3, model/extraction output bounds, scheduler,
coverage, adapters, evaluator, and completion policy - remains frozen. A fourth
paid LIVE run still requires separate explicit owner authorization.

## Global Constraints

- Planning baseline: branch `feature/qualor-live-production`, HEAD `1942690072c58a3fe37e840180025c81d8ed115f`, clean before this plan commit. Implementation starts from the owner-approved plan commit on that branch; inspect it, do not reset/rebase/stash.
- Existing intended workspace: `C:\PROJECTS\qualor\.worktrees\qualor-live-production`. The wrapper spelling `qualor.worktrees` is not a second checkout to create.
- Read `AGENTS.md`, `docs/00_CANONICAL_BRIEF_UA.md`, the spec, and this plan before execution. Preserve brief SHA-256 `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829` and its bytes.
- AWS_PAID_CALLS=0 throughout Task 5F, including verification. Do not invoke AWS, Bedrock, AgentCore, a real LIVE command, or deployment. Offline tests must intercept transports before constructing production execution; never obtain credentials.
- UNKNOWN != PASS; AMBIGUOUS != PASS; UNSUPPORTED != PASS. Strategy is prioritization, not probability. No predetermined positive recommendation.
- INFERENCE_CALL_CEILING=9; MAX_EXTRACTED_CLAIMS_PER_CALL=2; MAX_COST_USD=0.20. Use `live_budget()`/QUALOR_03B3 policy, not the older baseline policy whose default cap is USD 2.00. Preserve diagnostic-mode limits too.
- Preserve max steps 24, operational failure threshold 3, no-progress protection, shared physical LiveBudgetGuard, no hidden retry, and Task 5C semantic rejection handling.
- No automatic second-source research, new source admission, batch/call/cost increase, completion-policy change, frontend policy, visual change, profile store, external compliance lookup, or external submission.
- No runtime branching on contest/organizer names, source domains, archived wording hashes, or Devpost templates. Archive names/hashes are test input bindings only.
- Existing RuleCandidate/RuleEvaluation/EligibilityGate/DecisionInput/RuntimeDecisionBundle remain authorities. No second eligibility engine. No decision recomputation in persistence.
- Preserve LOCAL/HOSTED_DEMO boundaries, single-slot API execution, action capabilities, selected-decision approval linkage, expiry/idempotency, immutable packs, and FIXTURE/REPLAY behavior.
- Only after owner approval of this plan may the tasks below modify code. This plan commit changes exactly this document. Future tasks use RED -> GREEN -> review -> scoped commit; no giant final commit and no push.
- All commands below run in the intended worktree unless an explicit `Push-Location` is shown. Tests never run against the three paid dogfood databases.

## Repository mapping verified at the planning baseline

| Existing path and symbol | Current responsibility / integration boundary |
|---|---|
| `src/qualor/runtime/loop.py`: OpportunityRun, fetch_official_source, extract_official_claims, record_evidence, evaluate_current_state, finish, _notify | Source/claim memory; revision cache; sticky terminal reason; isolated observer notifications. New acquisition orchestration must not replace these authorities. |
| `src/qualor/runtime/sources.py`: SourceDocument, _ReadableHTML, OfficialSourceFetcher.fetch, source_authority | Exact fetched text, network/SSRF limits, source classification. Extract the existing text-decoding block into a pure callable without changing its bytes. |
| `src/qualor/runtime/spans.py`: EvidenceSpan, EvidenceSpanRegistry, extraction_window, _segments | Run-scoped capabilities; current literal focus-based 9,000-byte window. Retain legacy entry points; add section registration. |
| `src/qualor/runtime/extraction.py`: ExtractedClaimBatchTransport, validate_extraction_payload, ground_extraction_payload, build_extraction_request, BedrockClaimExtractor.extract | Strict JSON wire validation, exact span grounding, two-claim ceiling, receipt capture, no retry. Add a section-specific wire contract, not a second provider implementation. |
| `src/qualor/runtime/claims.py`: ExtractedClaim, ValidatedClaim, validate_claim, FIELD_CATEGORY, HARD_AUTHORITIES | Legacy grounded admission. Keep existing FIXTURE/REPLAY/legacy tests; the section path performs stronger context-aware validation before typed adaptation. |
| `src/qualor/runtime/normalization.py`: NormalizationStatus, NormalizedSupportResult, ClaimNormalizationError, normalize_supported_claim | Existing narrow normalizers and typed semantic rejection. Do not globally loosen this path to make new adapters pass. |
| `src/qualor/runtime/handoff.py`: _compile_rules, compile_decision_bundle, compute_decision | Existing OpportunityRecord/DecisionInput construction, version resolution, one decide call. Merge validated section authority here. |
| `src/qualor/runtime/run_models.py`: StudioInput, TraceEvent, RuntimeDecisionBundle, AgentRunResult | Bounded runtime contracts; bundle excluded from public schema. Add bounded diagnostics without exposing input profiles. |
| `src/qualor/runtime/agent.py`: run_agent, BudgetedBedrockClient.converse, estimate_model_reservation, model_request_metrics | Real Strands tool wrappers and shared physical model reservations. Activate deterministic section draining after successful first-source fetch. |
| `src/qualor/runtime/budget.py`: LiveBudgetPolicy, LiveBudgetGuard, BudgetSnapshot, LiveCallKind | Sole physical call/cost authority. No policy changes. |
| `src/qualor/runtime/diagnostics.py`: BoundaryEvent, Rejection, CODEBOOK, shape; `extraction_receipt.py`: StructuredExtractionReceipt, response_metadata | Safe failure vocabulary and extraction-envelope metadata. Keep raw payloads out of durable diagnostics. |
| `src/qualor/domain/base.py`: Fact, Record, Provenance; `profiles.py`: FounderProfile, ProjectProfile | USER_ASSERTED / DOCUMENTED / UNKNOWN facts and existing profile stores. No age/compliance fact exists to invent. |
| `src/qualor/domain/rules.py`: RuleCandidate, RuleEvaluation; `values.py`: TextValue, BoolValue, NumberValue, DateValue, InstantValue | Existing recursive typed expressions; add optional provenance context, not verdict fields. |
| `src/qualor/eligibility/coverage.py`: REQUIRED_CATEGORIES, evaluate_coverage | All nine critical categories. Existing CoverageState is evaluator coverage, not the new acquisition state. |
| `src/qualor/eligibility/subjects.py`: ALLOWED_SUBJECTS, resolve_subject | DATE_BETWEEN is the supported deadline shape. New-project evidence requires documented ORIGINAL provenance. License subject currently resolves license_intent, not verified repository compliance. |
| `src/qualor/eligibility/operators.py`: evaluate_operator; `engine.py`: _evaluate, aggregate_eligibility | AND/OR/IN/NOT_IN/date/boolean semantics already exist. Unsupported subjects/operators remain UNKNOWN. Do not change aggregation. |
| `src/qualor/workspace/run_capture.py`: WorkspaceRunCapture._payload, _validated_graph, _persist_graph, require_persisted | Terminal run/event capture and successful graph validation; no partial-success policy changes. |
| `src/qualor/workspace/models.py`: RunRecord, RunEventPayload, RunEvent | JSON persistence permits additive optional payload fields without a new table; RunEvent stays <=4,096 bytes. |
| `src/qualor/runtime/live_cli.py`: live_budget, execute_live, run_command | Shared providers and explicit command-boundary persistence verification. Do not execute these against AWS during this task. |
| `src/qualor/hosted/coordinator.py`: LiveRunCoordinator._execute, _persisted_status, _ProgressCapture.trace_event | Async single slot; completion comes from persisted graph. New events must not fabricate progress. |
| `src/qualor/hosted/inputs.py`: load_demo_profile | Strips private founder facts. Do not restore residence or other stripped facts to force eligibility. |
| `src/qualor/workspace/read_models.py`: RunEventView, ActivityResponse | Existing public projections keep persistence diagnostics private. No new frontend contract for internal receipts is required. |
| `src/qualor/schemas/export.py`; `apps/web/scripts/generate-domain.mjs` | Own generated schemas/types. Regenerate only dependency-affected outputs, never hand-edit them. |

Read regression references: `tests/runtime/test_autonomous_loop.py`, `test_claims.py`, `test_claim_normalization.py`, `test_grounded_extraction.py`, `test_extraction_wire.py`, `test_live_inference_efficiency.py`, `test_live_budget.py`, `test_live_opportunity_compilation.py`, `test_agent.py`; `tests/workspace/test_live_run_persistence.py`; `tests/e2e/test_live_workspace_persistence.py`; `tests/test_hosted_live_runs.py`, `test_hosted_action_capability.py`, `test_hosted_approval.py`; `tests/eligibility/test_fixtures.py`; `tests/test_fixture_adapters.py`.

Existing replay entry points are in `src/qualor/runtime/replay.py`; do not route the archived compiler test through seeded replay decisions. Existing Task 3/4 controlled browser configurations are `apps/web/playwright.live.config.ts` and `apps/web/playwright.task4.config.ts`; the default Playwright config excludes those flows.

## File map and dependency contracts

All paths in this map are relative to the worktree. A Create entry is intentional new work, not an assertion that the file already exists. Consumers must use the exact interface names introduced by the producer task.

| Producer | New files | Existing files modified / responsibility |
|---|---|---|
| 1 | `src/qualor/runtime/sections.py`, `tests/runtime/conftest.py`, `tests/runtime/test_sections.py` | `runtime/sources.py`, `runtime/spans.py`: pure parser extraction and exact section capabilities |
| 2 | `src/qualor/runtime/acquisition_coverage.py`, `tests/runtime/test_acquisition_coverage.py` | No evaluator CoverageState change |
| 3 | `src/qualor/runtime/section_scheduler.py`, `tests/runtime/test_section_scheduler.py` | No model/provider activation yet |
| 4 | `src/qualor/runtime/section_extraction.py`, `tests/runtime/test_section_extraction.py` | `domain/evidence.py`, `domain/rules.py`, `runtime/extraction.py`, `tests/runtime/conftest.py`: provenance and bounded wire integration |
| 5 | `src/qualor/runtime/adapters/__init__.py`, `base.py`, `deadline.py`, `entrant_type.py`, `geography.py`, `legal_entity.py`, `project_policy.py`, `license.py`, `technology.py`, `financial_support.py`, `reward_conditions.py`; `tests/runtime/test_canonical_adapters.py` | No evaluator policy edits |
| 6 | `src/qualor/runtime/fact_authority.py`, `tests/runtime/test_fact_authority.py` | `tests/runtime/conftest.py`; existing profile models/stores unchanged |
| 7 | `src/qualor/runtime/canonical_compilation.py`, `tests/runtime/test_section_handoff.py` | `runtime/handoff.py`: combine section authority with legacy authority; no completion change |
| 8 | `src/qualor/runtime/section_acquisition.py`, `tests/runtime/test_section_acquisition.py` | `runtime/loop.py`, `runtime/agent.py`: activate section pipeline and revision-cached evaluation |
| 9 | `src/qualor/runtime/model_receipts.py`, `tests/runtime/test_model_receipts.py`, `tests/workspace/test_compiler_receipts.py` | `runtime/agent.py`, `runtime/loop.py`, `runtime/section_acquisition.py`, `runtime/run_models.py`, `runtime/diagnostics.py`, `workspace/models.py`, `workspace/run_capture.py` |
| 10 | `tests/runtime/archived_compiler_support.py`, `tests/runtime/test_archived_source_input.py` | `tests/runtime/conftest.py`, `pyproject.toml`: explicit archive fixture and marker |
| 11 | `tests/runtime/test_archived_compiler_acceptance.py` | `tests/runtime/archived_compiler_support.py`: candidate-only archive oracle and offline report |
| 12 | `tests/runtime/test_compiler_cost_simulation.py` | `tests/runtime/archived_compiler_support.py`: production-request simulation, no pricing changes |
| 13 | No required source files | Verification/review only; fix only demonstrated in-scope regressions through RED/GREEN |
| 14 | `tests/workspace/test_compiler_completion_gate.py` | Diagnostic acceptance only, no terminal-state mapping change |

The nine adapter files in row 5 are inside `src/qualor/runtime/adapters/`; their names are enumerated, not a wildcard implementation assignment. All other shortened paths in the modified column are under `src/qualor/`.

Generated companions for Task 4 are `schemas/AgentRunResult.schema.json`, `schemas/DecisionFixture.schema.json`, `schemas/DecisionInput.schema.json`, `schemas/EvidenceRecord.schema.json`, `schemas/RuleCandidate.schema.json`, and `apps/web/src/generated/domain.ts`. Task 9 additionally refreshes `schemas/AgentRunResult.schema.json` and that same generated TypeScript file. No visual or hand-maintained frontend file is planned. If export reveals another dependency, verify its reference chain before staging it and name it in review; do not accept unrelated generated churn.

Global generated-contract command block, used when a task changes a public nested model:

```powershell
uv run --locked python -m qualor.schemas.export
node apps/web/scripts/generate-domain.mjs
uv run --locked python -m qualor.schemas.export --check
node apps/web/scripts/generate-domain.mjs --check
uv run --locked pytest tests/domain/test_schema_export.py tests/test_type_codegen.py -q
```

## Task 1 — Deterministic full-document Section Index

**Files:** Create `src/qualor/runtime/sections.py`, `tests/runtime/conftest.py`, `tests/runtime/test_sections.py`. Modify `src/qualor/runtime/sources.py` and `src/qualor/runtime/spans.py` only at parser/span boundaries.

**Interfaces:** Consume existing SourceDocument/EvidenceSpan/EvidenceSpanRegistry/Category. Produce:

- `canonical_source_text(body: bytes, content_type: str) -> tuple[str, bool]` in sources.py: extracted existing decode/HTML/JSON/truncation behavior; bool means truncated.
- `SourceSection(Contract)`: section_id, source_id, source_revision, heading (optional exact text), start_offset, end_offset, span_ids, section_hash, candidate_categories (`tuple[Category, ...]`), parent_id (optional), context_section_ids, context_complete (bool).
- `SectionIndex(Contract)`: source_id, source_revision, indexer_version, sections (`tuple[SourceSection, ...]`). `source_revision` hashes normalized final URL plus raw content hash, not an ephemeral run UUID.
- `index_source(source: SourceDocument, registry: EvidenceSpanRegistry) -> SectionIndex`.
- `EvidenceSpanRegistry.register_section(source: SourceDocument, *, start_offset: int, end_offset: int) -> tuple[EvidenceSpan, ...]`; it validates offsets, uses existing segment/capability machinery, and never falls back to broad focus.

- [ ] RED: add a pytest `document` factory fixture in conftest.py, constructing SourceDocument from supplied text, SHA-256 of that text, `https://example.org/rules`, and aware `2026-09-12T11:25:52Z`; allow optional content_hash override for revision tests. It performs no network or database work. Add tests for late clauses, stable identity, revision invalidation, exact offsets, child/context linkage, unclassified fallback and routing-only hints.

```python
def test_late_license_section_is_reachable(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry
    text = "Introduction\n" + ("General background.\n" * 700) + "\nLicense\nAn MIT license is required."
    source = document(text)
    index = index_source(source, EvidenceSpanRegistry())
    reached = [s for s in index.sections if s.start_offset > 9000]
    assert reached
    assert any("MIT" in source.text[s.start_offset:s.end_offset] for s in reached)
    assert not hasattr(index, "eligibility")
```

- [ ] Run RED: `uv run --locked pytest tests/runtime/test_sections.py -q`. Expected failure: missing sections module/register_section and inaccessible late sections, not a provider/import-environment failure.
- [ ] GREEN implementation: factor existing parser byte-for-byte; scan the complete retained text into heading/paragraph/list regions; route generic category terms; partition oversized regions into bounded children using existing span limits. Bind identities to source revision/indexer version/offsets/text hash. Parent/global applicability and exact referenced sections remain context links. An unresolvable link sets context_complete=False, never silently omits a restriction. Index unclassified regions for deterministic fallback. No new external parser dependency.

Use line offsets from splitlines(keepends=True); a heading candidate is a short non-sentence line (<=100 characters) with a numbered section prefix or generic heading vocabulary (submission period/deadline, eligibility, geography/residency, legal/entity, project requirements/new work, license, technology, financial/support, prizes/reward/verification). Resolve overlaps by source order, never by a model or host. Route body terms as additional hints. Child segmentation uses existing byte/character limits and source-order boundaries, with parent IDs preserved. Explicit references such as `subject to section 3` resolve to indexed numbered headings; unresolved references and unbounded global-scope conditions set context_complete=False. Tests must distinguish an unrelated local `may` from an expressly applicable global restriction. Headingless content remains indexed in source-order fallback children.

```python
text, truncated = canonical_source_text(body, mime)
# OfficialSourceFetcher.fetch uses these outputs instead of its inline decoder.
# Section digest input excludes registry secrets and model focus.
identity_material = (source_revision, indexer_version, start_offset, end_offset, section_hash)
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_sections.py tests/runtime/test_sources.py tests/runtime/test_evidence_spans.py -q`. Expected: all tests pass; original parser/fetch and legacy span tests unchanged.
- [ ] Review exact offset coverage, no quote rewriting, full-source reachability, parent exception linkage and no source-name branching. Record source-context overflow as unresolved.
- [ ] Commit only these five files: `git commit -m "feat: index canonical source sections"` after explicit-path staging and `git diff --cached --check`.

## Task 2 — Acquisition coverage distinct from eligibility

**Files:** Create `src/qualor/runtime/acquisition_coverage.py`, `tests/runtime/test_acquisition_coverage.py`.

**Interfaces:** Consume Task 1 SectionIndex and existing Category/NormalizationStatus. Produce `AcquisitionState` with the seven spec states, `AttemptKey = tuple[str, str, Category]` (revision, section_id, category), `AcquisitionOutcome(Contract)` (normalization_status, supported_rule_ids, conditional, context_complete, safe reason_code), `CoverageTransition(Contract)` (key, before, after, outcome, authority_revision), and `CoverageLedger(index: SectionIndex)`.
Ledger methods: `state(category)`, `begin(section_id, categories, authority_revision)`, `complete(section_id, outcomes: dict[Category, AcquisitionOutcome], authority_revision)`, `operational_failure(section_id, categories, reason_code)`, `budget_blocked(section_id, categories)`, `replace_index(index)`. Expose immutable `transitions`, `attempts`, `outcomes` snapshots. No acquisition field is an eligibility verdict.

- [ ] RED: test all spec transitions, three ambiguous outcomes without operational failure, partial supported IDs surviving category exhaustion, explicit UNKNOWN outcome preservation, source-revision reopening, same-revision replacement refusing reopening, and supported conditional rules with unknown applicant compliance.

```python
def test_unknown_survives_exhaustion(document):
    from qualor.runtime.acquisition_coverage import CoverageLedger, AcquisitionOutcome
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry
    from qualor.domain.enums import Category
    index = index_source(document("Geography\nEligibility depends on local law."), EvidenceSpanRegistry())
    ledger = CoverageLedger(index)
    section = next(s for s in index.sections if Category.GEOGRAPHY in s.candidate_categories)
    ledger.begin(section.section_id, (Category.GEOGRAPHY,), 0)
    result = AcquisitionOutcome(normalization_status="UNKNOWN", supported_rule_ids=(), conditional=False, context_complete=True, reason_code="SOURCE_UNRESOLVED")
    ledger.complete(section.section_id, {Category.GEOGRAPHY: result}, 0)
    assert ledger.outcomes[(index.source_revision, section.section_id, Category.GEOGRAPHY)].normalization_status == "UNKNOWN"
    assert ledger.state(Category.GEOGRAPHY).value != "PASS"
```

- [ ] RED command: `uv run --locked pytest tests/runtime/test_acquisition_coverage.py -q`; expected missing ledger, then transition assertion failures.
- [ ] GREEN: implement deterministic per-pair outcomes and aggregate derivation. After an outcome, choose SECTION_AVAILABLE if relevant unattempted sections remain, SUPPORTED only after governing interpretation is complete, otherwise EXHAUSTED with outcomes retained. Failed dispatched pairs are consumed but not successfully inspected; budget-blocked undispatched work is not consumed as inspection. Preserve transitions for AMBIGUOUS/UNSUPPORTED before aggregation. New source revision creates a new ledger revision; focus is not an API input.

```python
key = (index.source_revision, section_id, category)
if key in attempts:
    raise ValueError("DUPLICATE_SECTION_CATEGORY_ATTEMPT")
# Store the original normalization_status even when its acquisition state is UNSUPPORTED.
```

- [ ] GREEN command: `uv run --locked pytest tests/runtime/test_acquisition_coverage.py tests/eligibility/test_engine.py tests/eligibility/test_fixtures.py -q`; expected PASS without modifying evaluator coverage enums.
- [ ] Review acquisition/semantic/eligibility separation and deterministic reopening. Commit: `feat: track deterministic evidence coverage` (only the two new files).

## Task 3 — One-job deterministic section scheduler

**Files:** Create `src/qualor/runtime/section_scheduler.py`, `tests/runtime/test_section_scheduler.py`.

**Interfaces:** Consume SectionIndex, CoverageLedger, LiveBudgetGuard, BudgetSnapshot. Produce `ExtractionJob(Contract)` with job_id, source_id, source_revision, section_id, categories (`tuple[Category, ...]`), span_ids, context_section_ids, authority_revision; `NoExtractionJob(Contract)` with reason_code and pivot_eligible; `SectionScheduler(index, ledger, budget)` with `next_job(*, authority_revision: int, steps_remaining: int, terminated: bool) -> ExtractionJob | NoExtractionJob` and `begin(job) -> None`.
No-job codes are RUN_TERMINATED, STEP_BOUND, BUDGET_BLOCKED, SOURCE_EXHAUSTED, CONTEXT_UNRESOLVED. Pivot eligibility is information only, never a network action.

- [ ] RED: test Category enumeration order, offsets as tie-breaker, at most two target categories per job, no pair rescheduling, failed-pair suppression, deterministic fallback, all current-source sections before pivot, and budget refusal with zero successful inspections.

```python
def test_scheduler_cannot_repeat_pair(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry
    from qualor.runtime.acquisition_coverage import CoverageLedger
    from qualor.runtime.section_scheduler import SectionScheduler
    from qualor.runtime.live_cli import live_budget
    index = index_source(document("License\nAn MIT license is required."), EvidenceSpanRegistry())
    scheduler = SectionScheduler(index, CoverageLedger(index), live_budget())
    job = scheduler.next_job(authority_revision=0, steps_remaining=24, terminated=False)
    scheduler.begin(job)
    import pytest
    with pytest.raises(ValueError, match="DUPLICATE_SECTION_CATEGORY_ATTEMPT"):
        scheduler.begin(job)
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_section_scheduler.py -q`; expected missing scheduler and duplicate dispatch tests failing.
- [ ] GREEN: choose unresolved category/section pairs using stable order; pack at most two categories only when their complete context fits one job. Keep repeated context distinguishable from repeated target work. Use guard snapshots for eligibility checks, never a parallel cost counter. Monetary reservation is deferred until the production request exists. Record begin before invoking the extractor; a physical guard refusal updates budget_blocked and stops, not an inspected success. Stop when no eligible pair remains. Do not call search, fetch, a model, or a compliance service here.

```python
if terminated:
    return NoExtractionJob(reason_code="RUN_TERMINATED", pivot_eligible=False)
if budget.calls_used(LiveCallKind.INFERENCE) >= budget.policy.inference_max_calls:
    return NoExtractionJob(reason_code="BUDGET_BLOCKED", pivot_eligible=False)
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_section_scheduler.py tests/runtime/test_acquisition_coverage.py tests/runtime/test_live_budget.py -q`; expected PASS; zero cloud calls.
- [ ] Review no retry via renamed jobs/focus and no premature source exhaustion. Commit: `feat: schedule bounded section extraction` (two new files).

## Task 4 — Section-scoped wire contract and exact clause context

**Files:** Create `src/qualor/runtime/section_extraction.py`, `tests/runtime/test_section_extraction.py`. Modify `src/qualor/runtime/extraction.py`, `src/qualor/domain/evidence.py`, `src/qualor/domain/rules.py`, `tests/runtime/conftest.py`; regenerate the Task 4 companions listed in the file map.

**Interfaces:** Consume SourceDocument, SectionIndex, ExtractionJob, EvidenceSpanRegistry, existing ExtractedClaim/NormalizationStatus.

- Add `ClauseContext(Contract)` in domain/evidence.py: source_id, section_id, span_ids (ordered unique, max 12), qualifiers and exceptions (tuples of exact source excerpts, max 12 each, max 700 chars per excerpt), context_section_ids (max 12), context_complete. Add optional `clause_context: ClauseContext | None = None` to EvidenceRecord and RuleCandidate. Existing JSON lacking the field remains valid. Evidence retains all original provenance fields.
- `SectionCandidateTransport(Contract)`: category (Category), proposed_value (existing NormalizedValue), source_id, section_id, span_ids, qualifier_span_ids, exception_span_ids, confidence_class (HIGH/MEDIUM/LOW/UNKNOWN), state (CANDIDATE/UNKNOWN). No model quote field: grounding derives exact quotes from capabilities. Candidate state requires a value; UNKNOWN forbids one.
- `SectionCandidateBatch(Contract)` with at most two transport candidates.
- `GroundedSectionCandidate(Contract)` with `candidate: SectionCandidateTransport`, exact `quotes: tuple[str, ...]`, `context: ClauseContext`, `source: SourceDocument` (`Field(exclude=True)`, internal only), and `semantic_context_complete: bool`. The source body MUST NOT enter diagnostics or public model serialization; persist only the resulting bounded EvidenceRecords.
- `validate_section_payload(payload: object) -> SectionCandidateBatch`; `ground_section_claim(candidate, *, source, index, job, registry) -> GroundedSectionCandidate`; `build_section_extraction_request(source, index, job, registry, *, max_output_tokens: int) -> dict`.
- Add `BedrockClaimExtractor.extract_section(source, index, job) -> tuple[GroundedSectionCandidate, ...]` using its existing client/receipt parsing. Retain extract(source, focus) unchanged for legacy paths. Both use the same model ID, physical budget client, two-claim schema bound and no retry.

- [ ] RED: invalid source/section/prior-run spans, out-of-job spans, category mismatch, invented quotes, reordered spans, excess claims, malformed JSON, remote governing context, unrelated document qualifiers, and model confidence independent of support. Add `grounded_candidate` fixture to conftest.py: it builds a document/index/job, resolves supplied exact test quote/qualifier/exception substrings to capabilities, and calls ground_section_claim; it must never create a RuleCandidate.

```python
def test_third_candidate_is_rejected():
    from qualor.runtime.section_extraction import validate_section_payload
    from pydantic import ValidationError
    import pytest
    item = dict(category="LICENSE", proposed_value="MIT", source_id="source-test", section_id="section-test", span_ids=["span_" + "a" * 32], qualifier_span_ids=[], exception_span_ids=[], confidence_class="HIGH", state="CANDIDATE")
    with pytest.raises(ValidationError):
        validate_section_payload({"claims": [item, item, item]})
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_section_extraction.py -q`; expected unavailable section API and rejection/context assertions.
- [ ] GREEN: build request from scheduler-owned exact spans only; use existing structured-output envelope and provider-error mapping. Resolve every ordered capability against source revision and allowed context; derive quotes without concatenating them into a fictitious verbatim sentence. Independently inspect applicable parent/reference context; omitted or unresolvable conditions force semantic_context_complete=False. Missing/forged references are operational errors. A missing semantic interpretation is not.

Keep the existing `EXTRACTION_TOOL_NAME` value `return_extracted_claims` in the new section request's outputConfig schema name so BudgetedBedrockClient selects the existing extraction output/token guard. Reuse response_metadata and STOP_FAILURES handling from extraction_receipt.py; factor envelope decoding inside extraction.py only if necessary to avoid duplicating that logic. No fallback between wire schemas after a provider response.

```python
if candidate.category not in job.categories:
    raise ValueError("EXTRACTION_CATEGORY_NOT_ALLOWED")
quotes = tuple(registry.resolve(source.id, span_id).exact_text for span_id in candidate.span_ids)
# Exact quotes and independently established governing context are passed to adapters.
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_section_extraction.py tests/runtime/test_grounded_extraction.py tests/runtime/test_extraction_wire.py tests/runtime/test_context_extraction.py tests/domain/test_contracts.py -q`, then generated-contract command block. Expected PASS, old contracts accepted, no raw model quote admitted.
- [ ] Review additive schema defaults, complete context retention, protected evidence storage and no provider duplication. Commit all named source/test/generated companions: `feat: ground section-scoped extraction candidates`.

## Task 5 — Nine generic typed semantic-family adapters

**Files:** Create the eleven files under `src/qualor/runtime/adapters/` enumerated in the file map and `tests/runtime/test_canonical_adapters.py`.

**Interfaces:** Consume GroundedSectionCandidate/ClauseContext and existing RuleCandidate, EvidenceRecord, Category, Operator, SubjectReference, Scalar, NormalizationStatus. Produce:

- In base.py: `AdapterResult(Contract)` with category, normalization_status, normalized_value, rules (`tuple[RuleCandidate, ...]`), evidence (`tuple[EvidenceRecord, ...]`), conditional, reason_codes (bounded safe strings). These are compiler outputs, not profile facts or verdicts.
- `SemanticAdapter` protocol: `compile(candidate: GroundedSectionCandidate, *, evaluated_at: datetime) -> AdapterResult`.
- DeadlineAdapter, EntrantTypeAdapter, GeographyRuleAdapter, LegalEntityAdapter, ProjectPolicyAdapter, LicenseAdapter, TechnologyRequirementAdapter, FinancialSupportAdapter, RewardConditionAdapter implement that signature.
- `adapt_candidate(candidate, *, evaluated_at) -> AdapterResult` in __init__.py dispatches by Category only.
- `GeographyCondition(Contract)` in geography.py retains explicitly_allowed and explicitly_excluded (`tuple[str, ...]`), open_ended_legal_restriction and requires_external_compliance_check (bool), qualifiers and exceptions (`tuple[str, ...]`), and provenance (`ClauseContext`); it is an internal compiler representation, not an applicant clearance record. Apply the same tuple/text bounds as ClauseContext.

Shared rule construction in base.py must generate deterministic rule/evidence IDs from revision, exact span, category and typed expression; use existing Record fields, DOCUMENTED provenance and the supplied aware clock. One EvidenceRecord per exact quoted span (<=700 chars), with ClauseContext; rules cite all governing records. REVIEWED means source interpretation verified, never applicant compliance. Unsupported residual predicates are RuleCandidate(supported=False) with real evidence and no invented subject. Conditional composite parents preserve required unresolved children. Limit rule count to existing DecisionInput bound 100 and bundle evidence bound 40; overflow fails boundedly rather than dropping clauses.

| Family/file | Exact mapping to existing evaluator contracts |
|---|---|
| Deadline / deadline.py | Parse generic explicit ISO offsets and unambiguous dated timezone phrases into InstantValue bounds; DATE_BETWEEN/EVALUATED_AT only with two source-supported endpoints. Named zones use zoneinfo, reject ambiguous/nonexistent local times; explicit generic US Pacific Time mapping is America/Los_Angeles, never inferred from host. A lone closing instant can populate deadline authority but does not invent an opening instant for DATE_BETWEEN. |
| EntrantType / entrant_type.py | IN/LEGAL_FORM and supported numeric TEAM_SIZE conditions; alternatives stay OR. Age/representative predicates lacking profile subjects become unsupported children under the correct AND/OR branch. Never infer age from legal form or team size. |
| Geography / geography.py | IN or NOT_IN with RESIDENCE/CITIZENSHIP only when expressly applicable. Preserve subnational scope; no guessed country-code mapping. An open legal/sanctions catchall adds an unresolved conjunct, never a closed-list PASS. |
| LegalEntity / legal_entity.py | IN/LEGAL_FORM with exact generic entity classification; DATE_BETWEEN/INCORPORATION_DATE only for complete represented bounds. Unrepresented organization classes/representation conditions stay unresolved, not coerced into company. |
| ProjectPolicy / project_policy.py | BOOL_IS/NEW_PROJECT for supported new-work condition; temporal/reuse/disclosure limitations remain attached and unresolved if current subjects cannot represent them. Existing documented-original check remains final. |
| License / license.py | IN/LICENSE for explicit license-intent criteria; OR for genuine alternatives. An actual repository-license/publication requirement retains its typed allowed-license values but emits an unsupported compliance predicate: current LICENSE resolves intent and cannot prove publication. Do not use a mismatching intent to manufacture a hard compliance failure. |
| Technology / technology.py | IN/REQUIRED_TECHNOLOGY; AND of singleton requirements for all-required, OR/IN for sufficient alternatives. Optional scoring/deployment clauses are not mandatory rules; unsupported conditional applicability remains attached. |
| FinancialSupport / financial_support.py | BOOL_IS/FINANCIAL_SUPPORT only for source scope exactly represented by has_sponsor_support. Different actors/time/preferences add unresolved conditions, not an inferred broad true/false. |
| RewardCondition / reward_conditions.py | BOOL_IS/REWARD_CONDITIONS only for the declared fact's scope; individual verification/tax/discretion requirements retain unresolved conditions. Never compile prize-pool money into guaranteed individual reward or credits into cash. |

- [ ] RED: parameterize all families using independently authored generic positive/negative/alternative/conjunctive/qualified/exception clauses; assert resulting typed expressions and evidence, not a chosen overall verdict. Include open-ended geography, absent compliance/age subjects, optional technology, UTC-offset ambiguity, omitted exceptions, unsupported date shape, prize-pool confusion, and high-confidence UNKNOWN. Each unsupported source clause must yield a safe reason, not guessed authority.

```python
def test_required_technology_maps_to_existing_subject(grounded_candidate):
    from qualor.runtime.adapters import adapt_candidate
    from qualor.domain.enums import Operator, SubjectReference
    candidate = grounded_candidate("REQUIRED_TECHNOLOGY", "Requirements\nBuild an agent using Widget SDK.", "Widget SDK")
    result = adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)
    assert result.normalization_status == "SUPPORTED"
    assert result.rules[0].operator == Operator.IN
    assert result.rules[0].subject_reference == SubjectReference.REQUIRED_TECHNOLOGY
    assert result.rules[0].clause_context == candidate.context
    assert result.evidence[0].supporting_excerpt in candidate.source.text
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_canonical_adapters.py -q`; expected missing adapters, then source-to-expression assertions failing. Work one family at a time through RED/GREEN; do not treat an import-only failure as sufficient semantic coverage.
- [ ] GREEN: use small explicit generic recognizers per family, normalize candidate values only after source/context agreement, and build existing typed trees. Shared qualifier validation is scoped to applicability, not whole-document keyword presence. Reuse parse_absolute_deadline for ISO instants; implement named/date phrase interpretation only within DeadlineAdapter, preserving old normalizers. Branch only on semantic structure/category; complex unsupported shapes retain UNKNOWN.

Implementation grammar is family-local and compositional: recognize a mandatory/permission/prohibition clause and its named subject first, then its finite literal values or interval, then attach `and`/`or` only when their syntactic scope is explicit. Do not split a multiword proper value merely because it contains those substrings. Recognize generic imperatives (`build ... with/using ...`), permission lists (`open to ...`), temporal requirements (`newly created during ...`) and explicit license/technology alternatives. Preserve unparsed tail conditions as unsupported residual nodes, not ignored text. For dates, parse explicit English month/day/year plus time and offset or the documented named zone; an optional weekday must agree with the parsed date. Resolve a submission interval's endpoints independently; reject ambiguous numeric dates, DST folds/gaps and missing years/timezones. No source-date clock shifting, inferred year, country clearance lookup or broad abbreviation guessing is permitted.

```python
# A known prohibition with an unresolved catchall remains a conjunction.
combined = parent.model_copy(update={"operator": Operator.AND, "children": (explicit_rule, unresolved_rule), "subject_reference": None, "operands": ()})
# Never compute a RuleEvaluation or eligibility verdict in an adapter.
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_canonical_adapters.py tests/runtime/test_claim_normalization.py tests/eligibility/test_operators.py tests/eligibility/test_engine.py -q`; expected PASS without evaluator changes. Record per-family supported and unresolved cases.
- [ ] Review all nine families, exact context references, exception completeness, no license-intent/compliance conflation, no semantic weakening. Commit: `feat: compile typed opportunity rule candidates`. This task can use family-sized commits during execution only if each includes its tests and shared interfaces remain passing; no unrelated changes.

## Task 6 — Independent ApplicantFacts / ProjectFacts authority boundary

**Files:** Create `src/qualor/runtime/fact_authority.py`, `tests/runtime/test_fact_authority.py`. Do not change profile fields/stores, hosted input stripping, or provenance enum values.

**Interfaces:** Consume StudioInput, FounderProfile, ProjectDecisionInput/ProjectProfile and Fact. Produce `independent_decision_facts(inputs: StudioInput) -> tuple[FounderProfile, tuple[ProjectDecisionInput, ...]]` (identity-preserving validated access) and `fact_authority_class(fact: Fact, *, scope: Literal['OWNER', 'PROJECT', 'ACCOUNT'], verified_at: datetime | None) -> Literal['OWNER_PROVIDED','PROJECT_STATE','VERIFIED_ACCOUNT_STATE','UNKNOWN']` for internal diagnostics/tests only, never to rewrite provenance.

Exact mapping: USER_ASSERTED owner facts -> OWNER_PROVIDED; existing project facts with USER_ASSERTED or DOCUMENTED provenance -> PROJECT_STATE while retaining that provenance; DOCUMENTED account facts require evidence_refs and verified_at for VERIFIED_ACCOUNT_STATE. There is no automatic account fact ingestion. Missing values/provenance remain UNKNOWN. The scope parameter cannot upgrade USER_ASSERTED to DOCUMENTED. No runtime adapter receives founder/projects.

- [ ] RED: snapshot inputs before compiling hostile rules claiming residence, legal form, incorporation, newness, technology, license compliance and sponsor funding; assert snapshots unchanged and missing facts still missing. Also test documented-original requirements and that a login receipt cannot become financial eligibility evidence.

```python
def test_rules_cannot_fill_missing_residence(studio_inputs):
    from qualor.runtime.fact_authority import independent_decision_facts
    before = studio_inputs.model_dump_json()
    founder, projects = independent_decision_facts(studio_inputs)
    assert founder.country_of_residence.value is None
    assert projects == studio_inputs.projects
    assert studio_inputs.model_dump_json() == before
```

Add `studio_inputs` fixture in `tests/runtime/conftest.py` in this task: explicit synthetic independent FounderProfile with unknown residence and one ProjectDecisionInput with empty effort assumptions; no source-derived facts. That file is an additional exact modified path for Task 6.

- [ ] RED: `uv run --locked pytest tests/runtime/test_fact_authority.py -q`; expected missing fact boundary and provenance-class assertions.
- [ ] GREEN: return validated existing objects; classify without changing Fact contents. Enforce no source/RuleCandidate parameter in the fact boundary. Keep unsupported fact subjects absent rather than adding new profile stores.

```python
def independent_decision_facts(inputs):
    validated = StudioInput.model_validate(inputs)
    return validated.founder, validated.projects
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_fact_authority.py tests/domain/test_contracts.py tests/test_hosted_live_runs.py -q`; expected PASS, private facts still stripped by load_demo_profile.
- [ ] Review enum/provenance preservation and separate owner/project facts. Commit the two new files and fixture addition: `feat: preserve independent applicant fact authority`.

## Task 7 — Canonical rules integrated into the existing handoff

**Files:** Create `src/qualor/runtime/canonical_compilation.py`, `tests/runtime/test_section_handoff.py`. Modify `src/qualor/runtime/handoff.py` only at _compile_rules/compile_decision_bundle integration.

**Interfaces:** Consume AdapterResult, independent_decision_facts, existing RuleCandidate/EvidenceRecord/MatchingRequirements/RuntimeDecisionBundle. Produce `OpportunityRuleSet = tuple[RuleCandidate, ...]` alias, `CompiledSectionAuthority(Contract)` with rules (OpportunityRuleSet), evidence (`tuple[EvidenceRecord, ...]`), deadlines (`tuple[datetime, ...]` of supported closing instants only), supported_claim_count (bounded int); `compile_section_authority(results: tuple[AdapterResult, ...]) -> CompiledSectionAuthority`. DeadlineAdapter keeps both endpoints in DATE_BETWEEN operands, but the opening instant MUST NOT become an opportunity closing deadline. Handoff reads optional `run.section_results` (default empty for legacy callers), combines exact evidence and typed rules, and calls existing decide once. No new decision model.

- [ ] RED: feed adapters' results, not handcrafted final rules, into a SimpleNamespace run compatible with compile_decision_bundle. Cover formerly unmapped categories, deadline interval/effective_deadlines, open legal residuals, conjunction/alternatives, and qualifier persistence after bundle serialization. Patch `qualor.runtime.handoff.decide` with a wraps spy; assert one call and no evaluate_operator replacement.

```python
def test_compiled_rule_context_survives(grounded_candidate):
    from qualor.runtime.adapters import adapt_candidate
    from qualor.runtime.canonical_compilation import compile_section_authority
    candidate = grounded_candidate("REQUIRED_TECHNOLOGY", "Requirements\nBuild an agent using Widget SDK.", "Widget SDK")
    result = adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)
    authority = compile_section_authority((result,))
    assert authority.rules[0].evidence_ids
    assert authority.rules[0].clause_context == candidate.context
    assert authority.evidence[0].clause_context == candidate.context
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_section_handoff.py -q`; expected missing compilation integration and absent executable category/context data.
- [ ] GREEN: merge rules/evidence deterministically by immutable IDs; identical duplicates reuse objects, conflicts remain unresolved rather than last-write-wins. Preserve rule nesting and all supporting evidence. Derive opportunity deadlines only from supported absolute adapter values. Do not invent dates, metadata, rewards, matching inputs, founder facts or a N/A shortcut. Keep _compile_rules legacy behavior when section_results is absent; do not double-emit a rule for the same section candidate via legacy claims. Handoff passes the existing opportunity version resolver before decide.

```python
section = compile_section_authority(tuple(getattr(run, "section_results", ())))
founder, projects = independent_decision_facts(run.inputs)
# Merge section.rules/evidence with legacy results by their immutable IDs,
# then use the existing DecisionInput and RuntimeDecisionBundle construction.
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_section_handoff.py tests/runtime/test_live_opportunity_compilation.py tests/runtime/test_live_handoff.py tests/workspace/test_live_run_persistence.py tests/e2e/test_live_workspace_persistence.py -q`; expected PASS, unchanged terminal policy and selected decision.
- [ ] Review source/section contexts survive through persisted EvidenceRecord references, deadline freshness participates correctly, no duplicate rule/decision authority, and existing semantic versioning behavior unchanged. Commit: `feat: integrate canonical section rules into live handoff`.

## Task 8 — Activate acquisition and revision-cached evaluation

**Files:** Create `src/qualor/runtime/section_acquisition.py`, `tests/runtime/test_section_acquisition.py`. Modify `src/qualor/runtime/loop.py`, `src/qualor/runtime/agent.py`.

**Interfaces:** Consume Tasks 1–7 and existing OpportunityRun/BedrockClaimExtractor. Produce `SectionAcquisition(run: OpportunityRun)` with `drain(source_id: str) -> dict` and `authority_fingerprint(results: tuple[AdapterResult, ...]) -> str`; add `OpportunityRun.acquire_official_sections(source_id: str) -> dict` delegating to it. Add run.section_results tuple and acquisition state owned by the run; legacy non-section callers keep their behavior. No provider instance can bypass the existing LIVE isinstance/shared-budget checks.

- [ ] RED: fake client under existing concrete LIVE provider wrappers; assert source fetch triggers indexing/drain without a planner missing-field call; source/category pairs run once; semantic rejection never increments failures; three genuine operational errors still stop; no acquisition search pivot. Spy evaluation: changed canonical rules/contradictions reevaluate once; identical supported result, confidence-only change or repeated UNKNOWN observation does not recompute. A new unresolved evidence entry that changes DecisionInput is an authority revision even though it is not an authoritative fact; cached bundle evidence must never diverge.

```python
def test_authority_fingerprint_excludes_redundant_observation(grounded_candidate):
    from qualor.runtime.adapters import adapt_candidate
    from qualor.runtime.section_acquisition import authority_fingerprint
    candidate = grounded_candidate("REQUIRED_TECHNOLOGY", "Requirements\nBuild an agent using Widget SDK.", "Widget SDK")
    result = adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)
    assert authority_fingerprint((result,)) != authority_fingerprint(())
    assert authority_fingerprint((result, result)) == authority_fingerprint((result,))
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_section_acquisition.py -q`; expected absent controller and unchanged focus-driven behavior.
- [ ] GREEN: activate only the LIVE agent's successful fetch wrapper: acquire the first fetched source, then drain scheduler jobs through BedrockClaimExtractor.extract_section, adapters and compilation. Count each dispatched job against existing run steps; account candidate admissions once, not via a second legacy validation pass. Use existing failure()/semantic_rejection() and sticky stop reason. On source exhaustion return bounded NO_PROGRESS through existing handling, not an automatic second search. Keep the legacy extraction tool entry point but have LIVE requests consume scheduled work rather than accept arbitrary focus-based repeated windows. Non-LIVE tools retain existing behavior.

```python
fingerprint = authority_fingerprint(run.section_results)
if fingerprint != previous_fingerprint:
    run._authority_revision += 1
    run.evaluate_current_state()
# If no relevant unattempted section remains, stop with existing NO_PROGRESS;
# never replace REVIEW_REQUIRED with a successful terminal reason.
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_section_acquisition.py tests/runtime/test_autonomous_loop.py tests/runtime/test_agent.py tests/runtime/test_live_inference_efficiency.py tests/runtime/test_runtime_gate.py tests/workspace/test_live_run_persistence.py tests/test_hosted_live_runs.py -q`; expected PASS. No extra terminal model turn after deterministic stop. Completion remains only the existing all-candidate PASS/FAIL branches.
- [ ] Review no swallowed operational errors, no schema retries, all guard counts preserved, one bundle per authority revision, hosted status from persistence, and no source pivot activation. Commit: `feat: drive live acquisition from canonical coverage`.

## Task 9 — Bounded durable model/acquisition receipts

**Files:** Create `src/qualor/runtime/model_receipts.py`, `tests/runtime/test_model_receipts.py`, `tests/workspace/test_compiler_receipts.py`. Modify `src/qualor/runtime/agent.py`, `src/qualor/runtime/loop.py`, `src/qualor/runtime/section_acquisition.py`, `src/qualor/runtime/run_models.py`, `src/qualor/runtime/diagnostics.py`, `src/qualor/workspace/models.py`, `src/qualor/workspace/run_capture.py`; regenerate Task 9 companions.

**Interfaces:** Produce `ModelCallReceipt(Contract)` with call_slot, call_index (nullable), role (PLANNING/EXTRACTION), source_id/section_id (nullable constrained IDs), requested_categories, proposal_count, supported_count, conditional_count, ambiguous_count, unknown_count, unsupported_count, duplicate_count, rejection_codes, authority_revision_before/after, execution_state (PLANNED/DISPATCHED/COMPLETED/FAILED/BUDGET_BLOCKED), cost_reserved/cost_reconciled (nullable bounded Decimals).
`ReceiptLedger` methods: `plan(role, *, source_id=None, section_id=None, categories=(), authority_revision=0) -> int`, `dispatch(slot, *, reservation: Decimal)`, `complete(slot, *, outcomes: tuple[AdapterResult, ...], authority_revision: int, reconciled: Decimal | None)`, `fail(slot, *, code: str, budget_blocked: bool)`, `snapshot() -> tuple[ModelCallReceipt, ...]`. Use run-owned ledger with at most 24 planned slots, at most 9 dispatched model calls; stop safely if a bound is reached, never discard required receipts.

Add optional receipt payload to TraceEvent and RunEventPayload, and `MODEL_CALL_RECEIPT` event literal. Add bounded `model_receipts` tuple to AgentRunResult. Model receipts reference adapter counts but contain no candidate values. Store only final per-slot snapshots as run events before terminal capture; earlier PLANNED/DISPATCHED updates remain in ledger, with state distinctions preserved in final snapshot. Three states per call must not flood the existing 100-event run trace bound. Reserve terminal diagnostic capacity before admitting further jobs.

Add `AgentRunResult.section_observation_count` (default 0, range 0..18). OpportunityRun.finish derives it from unique section candidates retained with SUPPORTED/AMBIGUOUS/UNKNOWN normalization, excluding rejected UNSUPPORTED candidates and duplicate emissions. WorkspaceRunCapture.run_finished adds it to the legacy retained-claim count for existing verified_claim_count telemetry; neither that historical field nor UNKNOWN observations become the authoritative-fact count. Supported canonical yield is independently derived from adapter/receipt supported_count. Test that a section-path success does not incorrectly report zero retained observations and that old FIXTURE/REPLAY counts remain unchanged.

- [ ] RED: lifecycle, counter reconciliation, conditional subset, budget-blocked no call_index, failure after physical dispatch counted, missing usage retains reservation, max-size/extra-field rejection, and persistence reopen on failed run. Poison raw exception/prompt/source/profile inputs with sentinel secrets and assert none serialize into receipts or public RunEventView.

```python
def test_budget_blocked_slot_is_not_a_paid_call():
    from qualor.runtime.model_receipts import ReceiptLedger
    ledger = ReceiptLedger()
    slot = ledger.plan("PLANNING")
    ledger.fail(slot, code="BUDGET_EXHAUSTED", budget_blocked=True)
    receipt = ledger.snapshot()[0]
    assert receipt.execution_state == "BUDGET_BLOCKED"
    assert receipt.call_index is None
    assert receipt.cost_reconciled is None
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_model_receipts.py tests/workspace/test_compiler_receipts.py -q`; expected missing ledger and discarded payload on capture.
- [ ] GREEN: wire planning/extraction role context to BudgetedBedrockClient.converse. Plan slot before guard reservation; dispatch only after reserve succeeds immediately before client.converse; reconcile using existing actual-token calculation; failures never refund/retry. Feed adapter outcomes and exact safe codes after validation, before final capture. Counts partition proposals into supported/ambiguous/unknown/unsupported/duplicate; conditional is a subset of supported. Map receipt through WorkspaceRunCapture._payload, preserve observer isolation and require_persisted. Existing tables already store validated JSON: no migration/table is added. Do not expose receipt payload through public workspace projection.

```python
receipt_id = budget.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=reservation)
ledger.dispatch(slot, reservation=reservation)
response = client.converse(**request)
# Existing usage verification/reconciliation remains the cost authority.
# Never ledger.fail(..., code=str(exc)); use the bounded CODEBOOK vocabulary.
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_model_receipts.py tests/workspace/test_compiler_receipts.py tests/runtime/test_extraction_receipts.py tests/runtime/test_run_event_sink.py tests/workspace/test_run_capture.py tests/test_hosted_live_runs.py tests/test_hosted_approval.py -q`, then generated-contract commands. Expected PASS, <=4,096 bytes per RunEvent, no raw payload leak, failed-run receipts survive reopen.
- [ ] Review lifetime bounds, denied vs dispatched counts, privacy, last terminal event retention and no duplicate cost authority. Commit: `feat: persist bounded canonical acquisition receipts`.

## Task 10 — Hash-bound archived input harness

**Files:** Create `tests/runtime/archived_compiler_support.py`, `tests/runtime/test_archived_source_input.py`. Modify `tests/runtime/conftest.py`, `pyproject.toml` only to register `archived_source` marker.

**Interfaces:** Produce `load_archived_rules(directory: Path) -> SourceDocument`, `ArchiveInputError(ValueError)`, `deny_external_io(monkeypatch) -> None`, `ArchivedInput` dataclass (directory: Path, source: SourceDocument), `archived_source` fixture yielding ArchivedInput, and `archived_studio_input() -> StudioInput`. load_archived_rules validates the existing source-manifest.json rules entry, required filename, timestamp, SHA-256 and raw bytes, then calls production canonical_source_text. Reject path traversal/symlinks outside the supplied directory. Fix evaluation clock explicitly to the archived retrieval instant for offline freshness, without changing any deadline.

archived_studio_input builds one explicitly independent test FounderProfile and one ProjectDecisionInput named `Controlled compiler project`, all eligibility-relevant applicant/project facts initially UNKNOWN and empty EffortAssumptions. This is a disclosed test profile, not the owner's profile or a source-derived declaration of compliance. Use the manifest's official source host for admission only. Preserve this same input unchanged throughout archive coverage and completion diagnosis; do not tune facts after observing a verdict. Known-fact positive/negative rule tests remain the independently authored Task 5/6 cases.

Required archive directory for local acceptance:
`C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source`.
Rules raw hash: `e3f7640c0bd1e78e3858d7d5a2dfb78bb560cac9b7982c29c5e57796116794a5`, retrieved `2026-09-12T11:25:52Z`. Overview stays comparison-only with manifest hash `d7b4cd7f1c36e43631028da8a0a6a2c39fb47090d4cec1f1fe0e1fefdbd52dce`; it is not fetched or auto-admitted.

- [ ] RED: missing directory/file, changed raw byte, manifest hash mismatch, wrong filename/retrieval timestamp, unsafe path, and wrong canonical parse. Unit negatives use tiny temporary files, not committed page copies. Add explicit environment contract: `QUALOR_ARCHIVE_DIR` selects archive; `QUALOR_REQUIRE_ARCHIVE=1` makes missing input fail, never skip. Ordinary portable test runs may skip archive-dependent integration when not requested, but cannot report archived acceptance PASS. Dedicated acceptance commands always set REQUIRE=1.

```python
def test_missing_archive_fails_closed(tmp_path):
    from archived_compiler_support import load_archived_rules, ArchiveInputError
    import pytest
    with pytest.raises(ArchiveInputError, match="ARCHIVE_INPUT_UNAVAILABLE"):
        load_archived_rules(tmp_path)
```

- [ ] RED: `uv run --locked pytest tests/runtime/test_archived_source_input.py -q`; expected missing loader and input validation failures.
- [ ] GREEN: validate manifest/hash before parsing; no download fallback. Add network-denial sentinels at boto3 client/session creation and actual socket connection entry points; use already-injected controlled transports for all production-wrapper tests. Provide small fixture builders for independent public test profiles, not private owner JSON. Import helper in runtime tests using pytest's runtime test directory; workspace consumers in Task 14 use the explicit importlib loader described there, not an assumed tests package.

```python
actual = hashlib.sha256(raw).hexdigest()
if actual != expected_rules_hash or manifest_entry["CONTENT_SHA256"] != expected_rules_hash:
    raise ArchiveInputError("ARCHIVE_HASH_MISMATCH")
text, truncated = canonical_source_text(raw, "text/html")
```

- [ ] GREEN: `uv run --locked pytest tests/runtime/test_archived_source_input.py tests/runtime/test_sources.py -q`; then set the two environment variables and run the same file with `-m archived_source` for positive hash-bound parsing. Expected positive archive tests run, not skip; mismatch negatives pass by refusing input.
- [ ] Review no committed raw captures, no fresh content, no credentials, no archive-specific runtime branch. Commit: `test: bind compiler acceptance to archived official source`.

## Task 11 — End-to-end archived compiler acceptance

**Files:** Create `tests/runtime/test_archived_compiler_acceptance.py`; extend `tests/runtime/archived_compiler_support.py` only.

**Interfaces:** Produce `ArchivedCompilerReport` dataclass (source_hash, indexed_sections, attempted_pairs, reached_categories, section_results, result: AgentRunResult, receipts, request_sequence, gate_values) and `run_archived_compiler(directory: Path, *, sink=None) -> ArchivedCompilerReport`. Also produce `ControlledCandidateClient` implementing converse(**request) and returning the existing Bedrock structured-response envelope. It reads section capabilities and emits at most two SectionCandidateTransport proposals; it never creates rules/evaluations. Initial search/fetch transport injection uses concrete AgentCoreSearchProvider/OfficialSourceFetcher wrappers and the same LiveBudgetGuard, with archived body returned by the fetch transport and real network denied.

Use the real Strands BedrockModel serialization with an injected session double whose client returns ControlledCandidateClient, wrapped by the existing BudgetedBedrockClient and configured with the same model ID, temperature, streaming=False and output limits as live_model. Do not call live_model or _temporary_credentials. ControlledCandidateClient also returns bounded planner tool-use envelopes: search once, fetch its returned candidate once, then respect the production deterministic stop. Detect request role from the production schema/tool configuration, not a zero-cost test flag. A test-only wraps spy on BudgetedBedrockClient.converse captures every proposed request before its reservation, including planning and requests later blocked by the guard; the inner client records only dispatched requests. Keep raw request_sequence in memory, excluded from saved report serialization; serialize only safe size/role/cost metrics. Account for every dispatched request through the shared guard. Mark the report `OFFLINE_CONTROLLED_LIVE_PATH`; LIVE provider shapes in tests are not a claim of real AWS execution.

- [ ] RED: archived raw -> production parser/index/coverage/scheduler/candidate wire/validation/adapters/handoff/engine. Assert every spec section reachability and count; compare rule contexts against source-bound candidate conditions, not model confidence. No calls to WorkspaceStore.seed or replay loaders; no handcrafted final RuleSet. Use actual generic categories/clauses from the archive with candidate values derived solely from their exact quoted passages. Unsupported private/compliance facts stay absent. Do not assert APPLY/PREPARE/PASS.

```python
def test_archive_reaches_late_clauses(archived_source):
    from archived_compiler_support import run_archived_compiler
    report = run_archived_compiler(archived_source.directory)
    assert report.gate_values["DEFAULT_9KB_WINDOW_ONLY"] is False
    assert report.gate_values["DUPLICATE_SECTION_CATEGORY_ATTEMPTS"] == 0
    assert report.gate_values["AUTHORITATIVE_CANONICAL_FACTS"] > 0
    assert report.gate_values["EXECUTABLE_RULES"] > 0
    assert report.gate_values["QUALIFIERS_DROPPED"] == 0
    assert report.gate_values["EXCEPTIONS_DROPPED"] == 0
    expected = {
        "REPEATED_IDENTICAL_WINDOW": False,
        "NEW_PROJECT_SECTION_REACHED": True,
        "LICENSE_SECTION_REACHED": True,
        "TECHNOLOGY_SECTION_REACHED": True,
        "FINANCIAL_SUPPORT_SECTION_REACHED": True,
        "REWARD_CONDITIONS_SECTION_REACHED": True,
        "EXTRACTION_AFTER_SECTION_EXHAUSTED": 0,
        "MODEL_CALL_USED_ONLY_TO_DISCOVER_KNOWN_MISSING_FIELDS": 0,
        "SOURCELESS_RULES": 0,
        "OWNER_FACTS_INFERRED_FROM_RULES": 0,
        "PROJECT_FACTS_INFERRED_FROM_RULES": 0,
        "DECISION_DERIVED_FROM_CANONICAL_AUTHORITY": True,
    }
    for name, value in expected.items():
        assert report.gate_values[name] == value, name
```

Use the Task 10 ArchivedInput fixture and archived_studio_input unchanged. The injected fetch clock MUST preserve the original retrieval timestamp without rebasing any deadline; use the existing datetime boundary under test injection, not a runtime clock-shift feature. Candidate envelope usage fields are controlled test data and MUST be labeled as such; Task 12 evaluates worst-case reservations without relying on favorable synthetic token usage.

- [ ] RED command (PowerShell):

```powershell
$env:QUALOR_ARCHIVE_DIR='C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source\.qualor\local\killer-demo-real-source'
$env:QUALOR_REQUIRE_ARCHIVE='1'
uv run --locked pytest tests/runtime/test_archived_compiler_acceptance.py -q
```

Expected RED is a missing harness or a real coverage/authority assertion, not a desired-verdict failure. If budget blocks the sequence, retain that failure for Task 12; do not bypass the guard to call acceptance GREEN.

- [ ] GREEN: candidate oracle chooses source-bound clauses within the actual job only, preserves ALL governing qualifier/exception spans and may emit UNKNOWN. It cannot patch scheduler order or skip required sections to fit nine calls. Record reached section IDs, pair uniqueness, source hashes and exact outcome counts. Minimum authority is >0; explicitly report all six stronger-target families and three conditional families. A legitimate unrepresentable condition is recorded, not silently omitted.

```python
assert all(e.supporting_excerpt in source.text for r in results for e in r.evidence)
assert all(rule.evidence_ids and rule.clause_context for r in results for rule in r.rules)
# gate_values are calculated from these results and attempt records, never constants.
```

- [ ] GREEN: repeat the explicit archive command, plus `uv run --locked pytest tests/runtime/test_canonical_adapters.py tests/runtime/test_section_acquisition.py -q`. Require new-project/license/technology/financial/reward sections reached; zero duplicate pairs/extraction after exhaustion/mechanical missing-field calls; zero sourceless rules/inferred owner/project facts; decision derived from canonical authority. Record raw counts and truthful unresolved reasons.
- [ ] Review actual production-chain coverage, no disguised REPLAY, no final rule injection, generic runtime and independent facts. Commit: `test: prove archived canonical compiler authority` only when these offline gates genuinely pass; otherwise stop with evidence, no paid run.

## Task 12 — Production request call/cost simulation

**Files:** Create `tests/runtime/test_compiler_cost_simulation.py`; extend `tests/runtime/archived_compiler_support.py` with `simulate_request_sequence(report: ArchivedCompilerReport) -> CostSimulationReport` (dataclass: expected_live_calls, projected_reserved_cost, projected_worst_case_cost, remaining_headroom, admitted, blocked_slot).

**Interfaces:** Consume real request dictionaries built by build_section_extraction_request and the production Strands model request boundary, estimate_model_reservation, model_request_metrics, LiveBudgetGuard.reserve/commit/reconcile. No rate table or independent counter authority is introduced.

- [ ] RED: include both initial planner requests, all extraction requests, any terminal/planning response actually requested, fixed search reservation, fetch reservations and failure branches. Verify an extra tenth call is blocked, oversized request fails reserve, absent planning request invalidates the report, and no favorable mock reconciliation makes worst-case fit. Assert all model request sizes/output bounds and IDs are from current production builders. Use the Task 11 injected BedrockModel transport through BudgetedBedrockClient for planning serialization as well as extraction; compare requests against the actual planner tool-use envelopes rather than assigning them zero cost.

```python
def test_sequence_accounts_for_every_physical_call(archived_source):
    from archived_compiler_support import run_archived_compiler, simulate_request_sequence
    report = run_archived_compiler(archived_source.directory)
    costs = simulate_request_sequence(report)
    assert costs.expected_live_calls == len(report.request_sequence)
    assert costs.expected_live_calls <= 9
    assert costs.admitted
    from decimal import Decimal
    assert costs.projected_worst_case_cost <= Decimal("0.20")
    assert costs.remaining_headroom == Decimal("0.20") - costs.projected_worst_case_cost
```

- [ ] RED: with archive environment set, `uv run --locked pytest tests/runtime/test_compiler_cost_simulation.py -q`; expected missing simulation or guard-admission failure, never permission to change limits.
- [ ] GREEN: replay the ordered production requests against a fresh live_budget() guard without network. Reserve using estimate_model_reservation; commit worst-case reservations without token refunds. Include search's production estimated-cost constant by reading its existing reservation path, not a duplicated guessed tariff. Cover each bounded branch admitted by the harness, including errors/blocked attempts; no unmeasured branch can claim PASS. Compute totals/headroom from actual reservations. Model/provider output settings stay unchanged. If the conservative sequence cannot fit, stop implementation acceptance and report the measured blocker; no hardcoded desired cost or call omission.

```python
reservation = estimate_model_reservation(request)
receipt = guard.reserve(LiveCallKind.INFERENCE, estimated_cost_usd=reservation)
guard.commit(receipt)  # worst-case simulation: no assumed token refund
```

- [ ] GREEN: same focused command plus `uv run --locked pytest tests/runtime/test_live_budget.py tests/runtime/test_agent.py tests/runtime/test_live_inference_efficiency.py -q`. Report EXPECTED_LIVE_CALLS, PROJECTED_RESERVED_COST, PROJECTED_WORST_CASE_COST, REMAINING_HEADROOM and PROJECTED_SEQUENCE_FITS_USD_0_20_GUARD; no estimate is a paid result.
- [ ] Review request completeness, physical guard usage, worst-case branches and uncertainty. Commit: `test: verify canonical compiler call and cost envelope` only after measured GREEN.

## Task 13 — Full regressions and independent genericity review

**Files:** No new runtime/visual feature. Review all committed Task 5F changes and generated companions. Any defect fix names its exact affected path and receives its own RED/GREEN commit; no broad refactor.

**Interfaces:** Consume production/tests from Tasks 1–12; do not add domain or provider interfaces here.

- [ ] RED/review detection: execute the complete commands below fresh after focused GREEN. Existing test failures or review findings are the RED condition; do not intentionally break green code. For a found defect, add the smallest regression assertion to its owning task's test file, run that exact file to prove RED, then fix only its owning implementation and rerun. If no defect is found, record no new RED was needed for this verification-only task.

```powershell
uv run --locked pytest tests/runtime tests/workspace tests/e2e tests/test_hosted_live_runs.py tests/test_hosted_action_capability.py tests/test_hosted_approval.py -q
uv run --locked pytest -q
npm --prefix apps/web run test:run
npm --prefix apps/web run test:run -- src/a11y/accessibility.test.tsx
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
uv run --locked ruff check .
uv run --locked python -m qualor.schemas.export --check
node apps/web/scripts/generate-domain.mjs --check
Push-Location apps/web
npm run test:e2e
npm run test:e2e -- --config playwright.live.config.ts
npm run test:e2e -- --config playwright.task4.config.ts
Pop-Location
git diff --check
git diff --cached --check
```

- [ ] Verify each command's exit code immediately; a later command cannot mask an earlier failure. Keep archive REQUIRE=1 for this local acceptance run; report archive test count and zero skipped required archive checks. Browser configurations must use their existing controlled backends, never a real gateway/profile.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1` from a clean committed candidate. The script performs locked installs and local checks, not AWS. Inspect its current version before execution and do not add cloud gates. This intentionally repeats some suites because the owner requires the canonical script as well as explicit browser/a11y gates.
- [ ] Independent review must inspect: no frontend verdict policy, no weakened LOCAL/HOSTED boundary, no stale/duplicate approval, no second decision authority, no provider/semantic failure conflation, no hidden retries, no whole-source qualifier rejection shortcut, no exception dropping, no inferred facts, no contest-specific adapter/scheduler branches. Require CRITICAL=0 and IMPORTANT=0; unresolved findings block completion.
- [ ] Genericity scan changed runtime files for contest/domain/organizer literals, then manually distinguish prohibited implementation branches from generic semantic vocabularies. Require DEVPOST_SPECIFIC_BRANCHES=0, AWS_AGENTS_FOR_HUMANS_SPECIFIC_BRANCHES=0, CONTEST_NAME_MATCHING=0. Review schema diffs and production frontend bundle for secret patterns; no token/prompt/source-body capture may be introduced.
- [ ] GREEN means every required command and review passes with exact counts recorded in ignored local results. Commit step: no empty verification commit. Commit only demonstrated RED/GREEN fixes with a narrow message, then rerun affected gates and the final canonical verification script. No push.

## Task 14 — Existing completion-policy diagnostic gate

**Files:** Create `tests/workspace/test_compiler_completion_gate.py`. Consume `tests/runtime/archived_compiler_support.py` via `importlib.util.spec_from_file_location` using `Path(__file__).parents[1] / 'runtime' / 'archived_compiler_support.py'`; execute the module after registering it in sys.modules for its dataclasses. Do not assume `tests` is an installed package or edit production imports for a test helper.

**Interfaces:** Consume run_archived_compiler, ArchivedCompilerReport, WorkspaceRunCapture, Database, WorkspaceStore and existing terminal mappings only. Produce a diagnostic report with case, existing_completion_policy_can_persist_truthful_graph, fourth_paid_run_candidate, next_action. No new completion enum or terminal mapping is implemented.

- [ ] RED: run the real archived compiler with a temporary Database and WorkspaceRunCapture, not a manually seeded bundle. Patch decide only with a wraps spy, never a verdict stub. Check persisted state after closing/reopening Database; compare selected decision/version and evidence contexts if graph exists. If the truthful computed gate is REVIEW_REQUIRED and existing policy rejects successful capture, assert no fake Opportunity/Decision graph and preserved terminal run/receipts. This test is not expected to fail merely because Case B is the truthful outcome.

```python
def test_archive_completion_uses_existing_policy(archive_completion):
    report, persisted_run, opportunity_count, decision_count = archive_completion
    if report.result.termination_reason in {"SUFFICIENT_CRITICAL_EVIDENCE", "HARD_FAIL_CONFIRMED"}:
        assert persisted_run.opportunity_id is not None
        assert persisted_run.decision_id == report.result.decision.selected_decision.id
    else:
        assert persisted_run.opportunity_id is None
        assert persisted_run.decision_id is None
        assert opportunity_count == decision_count == 0
```

Define archive_completion locally in this new test file: import the Task 10/11 helper via the explicit importlib path, import Database from qualor.persistence, create database = Database(tmp_path / 'compiler.db'), construct WorkspaceRunCapture(database, mode='LIVE', run_id='compiler-completion', inputs=archived_studio_input(), budget=live_budget()), and call run_archived_compiler with that sink. The harness MUST use sink.budget when a sink is provided so capture and runtime share the exact guard. Call require_persisted, reopen through a new Database instance, and inside its transaction construct WorkspaceStore(connection), read store.runs.current('compiler-completion'), and count opportunity_versions/decisions with read-only SELECTs. Return the report, persisted run and counts. Apply the same explicit archive environment guard as Task 10, with no source substitution or graph seeding.

- [ ] RED command with archive environment set: `uv run --locked pytest tests/workspace/test_compiler_completion_gate.py -q`; expected missing gate test/readback proof or a genuine linkage failure, not an artificially required APPLY/PASS.
- [ ] GREEN implementation is test/report code only: derive Case A from actual successful capture/readback. Derive Case B only when compiler correctness passed and legitimate REVIEW_REQUIRED is what prevents completion. Budget, malformed output, or missing evidence is a separate acceptance blocker, not mislabeled Case B. Never modify OpportunityRun.evaluate_current_state, the module-level TERMINAL_STATES in src/qualor/workspace/run_capture.py, hosted completion mapping, or coverage policy in this task.
- [ ] GREEN: `uv run --locked pytest tests/workspace/test_compiler_completion_gate.py tests/workspace/test_live_run_persistence.py tests/e2e/test_live_workspace_persistence.py -q`. Report the actual result without a verdict target. Review with the Task 13 reviewer if any linkage issue was found.
- [ ] Commit only the new gate test: `test: audit compiler result against existing completion policy`. Run full Python and `scripts/verify.ps1` again from the final clean candidate because this task adds a test after Task 13. Inspect final Git status/diff; only ignored local result artifacts may remain outside commits.
- [ ] Case A plus every other gate: FOURTH_PAID_RUN_CANDIDATE=YES, but FOURTH_PAID_RUN_AUTHORIZED=NO until new owner authorization. Case B: FOURTH_PAID_RUN_CANDIDATE=NO and NEXT_ACTION=QUALOR-LIVE-PRODUCTION-TASK-5G-COMPLETION-SEMANTICS-DESIGN. Other failures: report their exact blocker; no paid execution, limit increase or policy repair.

## Spec-to-task coverage and execution stop conditions

| Normative spec section | Owning tasks / proof |
|---|---|
| Authority, baseline, canonical bytes, no implementation authorization | Global constraints; planning commit scope; Task 13 canonical hash verification |
| 1: historical evidence, zero authority vs retained UNKNOWN, missing receipts | Mapping; Tasks 9–12 receipts/counts/archive distinction |
| 2: invariants and non-goals | Global constraints; Tasks 5–9; Task 13 security/genericity review; Task 14 unchanged terminal policy |
| 3: one agent, deterministic pipeline, no URL-as-authority | Tasks 1–8 production chain; Tasks 10–12 offline transport proof |
| 4: stable full-document index, offsets, hashes, context children, fallback | Task 1 tests; Task 4 capability validation; Task 11 late-section reachability |
| 5: seven states, partial support, explicit UNKNOWN, exhaustion/revision | Task 2 transition tests; Tasks 3/8 scheduling and revision tests |
| 6: bounded job, dedup, pre-dispatch attempt, no mechanical model planning, no pivot execution | Tasks 3/8; Tasks 11/12 measured attempts and calls |
| 7: two candidates, complete exact spans, qualifiers/exceptions, confidence non-authority | Task 4; Task 5 scoped adapters; Task 11 clause integrity |
| 8: all nine adapters, existing rule contracts, separate facts, open-ended geography | Tasks 5/6/7; Task 11 independent-fact and source-context gates |
| 9: semantic/operational distinction, bounds, durable safe receipts, cost states/privacy | Tasks 8/9/12/13 and failed-run reopen |
| 10: Case A/B, no successful partial graph, selected bundle/persistence isolation | Tasks 7/8/9 regressions; Task 14 diagnostic only |
| 11: archived manifest/hash binding, no fresh remote source/full-page commit, candidate-only test | Task 10 loader negatives; Task 11 complete production chain |
| 12: all section/authority/integrity/fact/count/cost/genericity gates | Tasks 10–13, with exact metric names and guard accounting |
| 13: all fourth-paid-run prerequisites plus explicit owner authorization | Tasks 11–14 and final report; never automatic authorization |
| 14: context/cost/call/private-fact/archive/time risks and deferred work | Global constraints; failing gates in Tasks 1/4/10/11/12; Task 14 Case B stop |

Dependency order is 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12 -> 13 -> 14. Unit tasks 5/6 have only earlier dependencies; no earlier task imports a later module. Activation is deferred until Task 8 so intermediate commits remain runnable. Task 9 consumes AdapterResult from Task 5; Task 10 introduces ArchivedInput before Tasks 11/14 use it. Schema companion generation occurs with its owning contract change, not deferred until the last commit.

At every commit: stage only that task's named paths and verified generated companions, run `git diff --cached --check`, inspect the staged diff, then commit the task message. Never use blanket staging for ignored archives/reports. Save execution counts and gate receipts only under ignored `.qualor/local/`; do not commit private machine reports. Keep a clean worktree between tasks.

If a required source form cannot be represented without changing evaluator policy, or the fully covered sequence cannot meet the existing guard, stop with the measured blocker. The plan does not grant permission to relax requirements. A correct Case B is an explicit diagnostic outcome, not permission to claim full successful LIVE product acceptance.

The plan ends at owner review before execution. No fourth paid LIVE run, implementation, or deployment is authorized by the plan-document commit.
