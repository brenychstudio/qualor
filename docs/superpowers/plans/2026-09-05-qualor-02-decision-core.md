# QUALOR-02 implementation plan

> **For agentic workers:** Use Superpowers subagent-driven implementation, TDD, task review and final verification. The owner has authorized this plan's implementation, commits, push and PR; merging and QUALOR-03 are not authorized.

**Goal:** Deterministic project matching, strategy, effort, conflict and recommendation built on the existing eligibility authority.

**Architecture:** Explicit Pydantic input facts feed pure assessments; a composition layer invokes QUALOR-01 eligibility per project and derives every decision. No API/fixture may supply an authoritative score, gate, conflict result or recommendation. Pydantic schemas generate TypeScript; no duplicate frontend domain interfaces.

**Spec:** Owner's QUALOR-02 task and `docs/00_CANONICAL_BRIEF_UA.md`, especially sections 10–14. Canonical SHA-256 `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.

**Stack:** Existing Python 3.12/Pydantic/FastAPI/Typer/pytest/Ruff; existing React/TypeScript build, with one pinned schema-to-TypeScript development generator if needed.

## Global Constraints

- Root `C:\PROJECTS\qualor`; base `8f7fdeb0d34093085895537619d42cccfa1e06aa`; branch `qualor-02-decision-core`.
- Baseline: 180 tests, verify, AWS read-only preflight and eight-schema regeneration PASS; clean tree and canonical hash confirmed.
- No LLM, agent, inference, live fetch/search, MCP runtime tools, persistence, submission, AWS resources or paid calls. AWS bridge and IAM remain unchanged.
- `UNKNOWN != PASS`; missing facts never become average ratings or READY. Cash, credits, equity and reward pools retain distinct semantics.
- `domain -> eligibility -> matching / effort / conflicts / strategy -> decisions`; lower layers never import decisions.
- Existing domain `Record`, `Fact[T]`, exact decimals, UTC/date distinctions and immutable validation are reused. New input fields default to unknown, preserving all existing fixtures.
- Pure functions use supplied aware evaluation timestamps. CLI/API mode is FIXTURE only; development routes accept data, never server paths, and are disabled outside development.
- Weights 30/25/20/15/10; factors integer 0–4 or unknown. Scores are internal priorities, never probabilities.
- Strategy sum uses integer half-up rounding: `(sum(rating * weight) + 2) // 4`. Example 4/3/3/4/2 yields 84.
- Recommendation priority is exactly owner Rules 1–6. Rule 4 PREPARE does not add an affordability predicate absent from the task; in the full pipeline unknown affordability makes the required economic strategy factor unknown, triggering earlier WATCH.
- Portfolio selection uses comparable matching scores, not prize amounts. Any unknown candidate or tied top score leaves selection unresolved; no lexical tie-break.
- No real UI; retain the bootstrap shell. No proprietary data/repositories or third-party rules content.
- Use installed Node 24.13.0/npm 11.6.2 via process-local PATH `C:\Users\CONCEPT2048\AppData\Local\nvm\v24.13.0`; do not change the owner's global NVM selection.

## Contract and policy decisions

Matching is exact, normalized comparison of explicitly stated labels/sets; it does not pretend to understand prose semantically. Problem/audience compare normalized full labels against permitted labels. Set overlap supports explicit technology/feature requirements; no inferred synonyms. Known empty requirement sets mean no requirement; absent requirement facts mean UNKNOWN.

Readiness assesses eight material categories: REPOSITORY, LICENSE, DEMO, ARCHITECTURE_DIAGRAM, TECHNICAL_INTEGRATION, NARRATIVE, PUBLIC_AVAILABILITY, OTHER. Every category needs an explicit required true/false fact. Required material facts need ready true/false; known false with executable gap becomes GAPS_EXECUTABLE, known non-executable becomes NOT_READY, missing facts remain UNKNOWN. Unknown gaps outrank executable gaps.

Effort assumptions distinguish the six submission-preparation categories from separately stated project adaptation hours. Never infer durations. Totals are min/max ranges; missing adaptation or category inputs hide total precision. Capacity compares conservative max effort with explicitly available hours and a known exact deadline horizon; calendar-only/absent deadline timing is UNKNOWN. No team-size multiplication of availability.

Affordability uses explicit complete participation cost coverage and founder cash budget. Entry fee/travel/cash spend add same-currency cash; incompatible currencies are UNKNOWN without FX. Credit requirements are separate and need explicit covered status; equity requirements need explicit consent. Rewards never increase cash budget or pay costs automatically.

Conflict coverage includes seven categories for the target and every explicitly supplied ActiveSubmission: NEW_PROJECT, EXCLUSIVE_SUBMISSION, LICENSE, SPONSOR_SUPPORT, SAME_PROJECT, EXISTING_PROJECT, DISCLOSURE. Rules require supported interpretation, explicit applicability and supporting reviewed evidence. Missing relevant external rules yield REVIEW_REQUIRED. No active submissions is an explicit input statement, not a claim to have searched all competitions.

## Task 1: Shared planning facts, readiness and project matching

**Files:** create `src/qualor/domain/planning.py`, `src/qualor/matching/{__init__,model,policy,readiness,engine}.py`, `tests/matching/test_matching.py`; modify `domain/profiles.py`, `domain/opportunity.py`; regenerate the existing eight schemas after additive contract changes. Do not change existing eligibility semantics or export additional schemas yet.

**Exact interfaces and shared types:**

```python
# domain.planning
HourRange(min_hours: NonNegativeDecimal, max_hours: NonNegativeDecimal)
MaterialKind  # eight values specified above
MaterialRequirement(kind: MaterialKind, required: Fact[StrictBool])
MaterialReadiness(kind: MaterialKind, ready: Fact[StrictBool],
                  gap_executable: Fact[StrictBool], reason: NonEmpty | None = None)
MatchingRequirements(problem_labels: Fact[tuple[NonEmpty, ...]],
    audience_labels: Fact[tuple[NonEmpty, ...]], technologies: Fact[tuple[NonEmpty, ...]],
    features: Fact[tuple[NonEmpty, ...]], stages: Fact[tuple[ProjectStage, ...]],
    licenses: Fact[tuple[NonEmpty, ...]], original_code_required: Fact[StrictBool],
    max_adaptation_hours: Fact[NonNegativeDecimal],
    materials: tuple[MaterialRequirement, ...])
# additive domain profile/opportunity fields, all default unknown/empty
FounderProfile.strategic_goals: Fact[tuple[NonEmpty, ...]]
ProjectProfile.material_readiness: tuple[MaterialReadiness, ...]
ProjectProfile.project_lineage: Fact[tuple[NonEmpty, ...]]
ProjectProfile.reused_components: Fact[tuple[NonEmpty, ...]]
ProjectProfile.reuse_disclosed: Fact[StrictBool]
OpportunityRecord.matching_requirements: MatchingRequirements | None
OpportunityRecord.strategic_benefits: Fact[tuple[NonEmpty, ...]]
# matching public API
assess_readiness(project: ProjectProfile, opportunity: OpportunityRecord,
                 evaluated_at: datetime) -> ReadinessAssessment
match_project(project: ProjectProfile, opportunity: OpportunityRecord,
              evaluated_at: datetime) -> ProjectMatch
select_best_project(matches: tuple[ProjectMatch, ...]) -> ProjectSelection
```

ReadinessAssessment has `state` (READY/GAPS_EXECUTABLE/NOT_READY/UNKNOWN), `gaps`, `missing_information`, `factor_results`, `evaluated_at`, `policy_version`. ProjectMatch has all task-required fields plus nullable `comparable_score` and nullable 0–4 `rating`. Factor results contain factor name, nullable integer rating, reasons and explicit requirement/fact references. ProjectSelection has nullable `best_project_id`, candidate matches and reasons; validate unique project IDs, one opportunity and at most five candidates.

MATCH_POLICY_VERSION=1. Factor ratings: exact categorical match 4/mismatch 0; explicit set coverage `4 * matched // required` (empty declared requirements=4); code/license combine conservatively; adaptation within declared maximum=4, above maximum=0; readiness READY=4, GAPS_EXECUTABLE=3, NOT_READY=0, UNKNOWN=None. Combined problem/audience factor uses their minimum. All seven factors must be known for a comparable score; equal-weight integer score is half-up `sum(ratings)*25/7`, rating is integer floor mean. STRONG >=75, PARTIAL >=50, otherwise WEAK; missing factor => INSUFFICIENT_EVIDENCE. Thresholds belong in policy.py.

- [ ] RED tests B24–B31, tied/unknown portfolio, missing requirement coverage, duplicate IDs, missing/non-executable material gaps, strict booleans/ranges and input revalidation. Run `uv run pytest tests/matching -q` and observe missing/new behavior fail.
- [ ] Implement the smallest typed facts/readiness/matching functions, then GREEN, Ruff and regenerate schemas. Existing 180 tests remain green.
- [ ] Commit `feat: add deterministic project matching`. Report exact interfaces and observed RED/GREEN results for downstream tasks. Task review gates spec compliance and quality.

## Task 2: Effort, capacity, affordability and strategy

**Files:** create `src/qualor/effort/{__init__,model,policy,engine,economics}.py`, `src/qualor/strategy/{__init__,policy,rubric,scoring}.py`, `tests/effort/test_effort.py`, `tests/strategy/test_strategy.py`. Consume Task 1 contracts without editing matching behavior.

**Interfaces:**

```python
EffortCategory  # INTEGRATION, EVIDENCE, REPO_LICENSE_CLEANUP, DEMO, NARRATIVE, SUBMISSION
EffortItem(category: EffortCategory, hours: HourRange | None,
           confidence: Confidence, reason: NonEmpty)
EffortAssumptions(items: tuple[EffortItem, ...])
estimate_effort(project: ProjectProfile, assumptions: EffortAssumptions,
                evaluated_at: datetime) -> EffortEstimate
assess_capacity(founder: FounderProfile, effort: EffortEstimate,
                opportunity: OpportunityRecord, evaluated_at: datetime) -> CapacityAssessment
ParticipationCost(kind: CostKind, amount: Money | None,
                  covered: Fact[StrictBool], accepted: Fact[StrictBool], reason: NonEmpty)
ParticipationCosts(complete: Fact[StrictBool], items: tuple[ParticipationCost, ...])
assess_affordability(founder: FounderProfile, costs: ParticipationCosts,
                     evaluated_at: datetime) -> AffordabilityAssessment
StrategyFactors(product_fit: Rating | None, readiness: Rating | None,
                time_feasibility: Rating | None, strategic_value: Rating | None,
                economic_affordability: Rating | None)
score_strategy(factors: StrategyFactors, evaluated_at: datetime) -> StrategyAssessment
derive_strategy(founder: FounderProfile, opportunity: OpportunityRecord,
    match: ProjectMatch, readiness: ReadinessAssessment, capacity: CapacityAssessment,
    affordability: AffordabilityAssessment, evaluated_at: datetime) -> StrategyAssessment
```

Rating is a StrictInt constrained 0–4. Confidence enum LOW/MEDIUM/HIGH/UNKNOWN. CostKind CASH_SPEND/ENTRY_FEE/TRAVEL/CLOUD_CREDIT/EQUITY_REQUIREMENT. Capacity and affordability states SUFFICIENT/INSUFFICIENT/UNKNOWN; use distinct named enums or assessment classes. Outputs carry state, reasons, missing information, supplied evaluated_at and version. EffortEstimate exposes breakdown, adaptation range, nullable min_total/max_total and missing items; explicit existing estimated_adaptation_hours is a stated point assumption `[x,x]`, never inferred if absent. Capacity uses maximum total and min(available_hours, exact remaining wall hours); an uncertain horizon or effort remains UNKNOWN. No availability multiplication.

STRATEGY_POLICY_VERSION=1 and EFFORT_POLICY_VERSION=1. StrategyAssessment fields `score: int|None`, breakdown (including weights, rating and contribution), missing_strategy_factors, `semantics='PRIORITIZATION_NOT_WIN_PROBABILITY'`, evaluated_at, policy_version. No probability field names. Derive product_fit from match.rating; readiness 4/3/0/None; time SUFFICIENT=4, INSUFFICIENT=0, UNKNOWN=None; affordability SUFFICIENT=4, INSUFFICIENT=0, UNKNOWN=None; strategic_value is explicit normalized founder-goal coverage by opportunity benefits using integer 0–4. Missing goals/benefits => None, known empty goals=>0. No reward input participates in affordability or scoring.

- [ ] RED B14–B23 and B32–B34: bounds/strict types, unknown factors, weighted example=84, repeatability, exact range totals, missing adaptation/category, currency mismatch, credits cannot enlarge cash budget, equity requires consent, unknown deadline/capacity.
- [ ] GREEN pure implementations with constants; no dependency additions needed. Ruff and focused tests.
- [ ] Commit `feat: add strategy and effort policies`; report exact output field names and tests, then review.

## Task 3: Explicit active-submission conflicts

**Files:** create `src/qualor/conflicts/{__init__,model,policy,engine}.py`, `tests/conflicts/test_conflicts.py`.

**Interfaces:**

```python
ConflictCategory  # seven categories listed in contract decisions
ConflictRule(id: NonEmpty, category: ConflictCategory, applies: Fact[StrictBool],
             supported: StrictBool, evidence_ids: tuple[NonEmpty, ...],
             allowed_licenses: Fact[tuple[NonEmpty, ...]])
ActiveSubmission(Record)  # all owner-required fields below
assess_conflicts(project: ProjectProfile, opportunity: OpportunityRecord,
    rules: tuple[ConflictRule, ...], submissions: tuple[ActiveSubmission, ...],
    evidence: tuple[EvidenceRecord, ...], evaluated_at: datetime) -> ConflictAssessment
```

ActiveSubmission contains contest, project_id, project_lineage Fact[tuple[str,...]], code_origin Fact[CodeProvenance], sponsor_support Fact[bool], submission_dates tuple[CalendarDate|UtcInstant,...], license Fact[str], reused_components Fact[tuple[str,...]], rules_evidence_refs tuple[str,...], facts_provenance Provenance, and `conflict_rules: tuple[ConflictRule,...]`. Unknown facts stay unknown; source/provenance cannot be fabricated.

ConflictAssessment.status is exactly BLOCKED_BY_EXPLICIT_RULE / REVIEW_REQUIRED / NO_CONFLICT_DETECTED_IN_CHECKED_RULES. Track checked/missing categories with contest scope, evidence_ids, reasons, evaluated_at and version. Evidence must exist, have reviewed extraction and acceptable official/synthetic source, appropriate normalized category, and be fresh (conservative unknown deadline). Map NEW_PROJECT/EXCLUSIVE_SUBMISSION/SAME_PROJECT/EXISTING_PROJECT/DISCLOSURE to PROJECT_POLICY; LICENSE to LICENSE; SPONSOR_SUPPORT to FINANCIAL_SUPPORT. Unresolved or unsupported source/legal interpretation => review. Confirmed explicit violation dominates review.

With applies=true: NEW_PROJECT checks original/new project and no reused lineage/components; EXCLUSIVE_SUBMISSION blocks any other explicitly active submission; LICENSE checks declared project license against explicitly allowed licenses; SPONSOR_SUPPORT forbids known financial support; SAME_PROJECT blocks matching project ID or explicitly intersecting lineage; EXISTING_PROJECT forbids known existing project; DISCLOSURE requires known disclosure when reused components exist. Applies=false is explicit non-applicability, still evidence-supported. Missing categories or unavailable relevant external contest rules => review, even if current contest rules are complete. Check external rules against the proposed new submission as well as current restrictions against existing submissions; never claim global clearance.

- [ ] RED B35–B38 plus all seven categories, external missing rules, unknown lineage/support/disclosure, mismatched/stale evidence, explicit rule precedence, duplicate IDs/categories and no absolute NO_CONFLICT enum.
- [ ] GREEN minimal supported checks; no legal inference or repo reads. Commit `feat: add submission conflict engine` after Ruff/tests and review.

## Task 4: Decision composition, policy, owned fixtures and adapters

**Files:** create `src/qualor/decisions/{__init__,model,policy,engine,fixture}.py`, `tests/decisions/test_decisions.py`, `tests/decisions/test_decision_fixtures.py`, `tests/test_decision_adapters.py`, and twelve `tests/fixtures/decisions/D*.json`; modify `src/qualor/{api,cli}.py` only for the new adapter.

**Interfaces:**

```python
Recommendation  # exactly APPLY/PREPARE/WATCH/SKIP
recommend(eligibility: GateState, conflict: ConflictStatus, score: int | None,
    readiness: ReadinessState, capacity: CapacityState, affordability: AffordabilityState,
    *, closed_or_expired: bool) -> RecommendationResult
ProjectDecisionInput(project: ProjectProfile, effort: EffortAssumptions)
DecisionFixture(schema_version: Literal['1'], mode: Literal['FIXTURE'], founder: FounderProfile,
    opportunity: OpportunityRecord, projects: tuple[ProjectDecisionInput,...],
    eligibility_rules: tuple[RuleCandidate,...], evidence: tuple[EvidenceRecord,...],
    conflict_rules: tuple[ConflictRule,...], active_submissions: tuple[ActiveSubmission,...],
    participation_costs: ParticipationCosts, evaluated_at: UtcInstant)
decide_fixture(fixture: DecisionFixture) -> DecisionResult
```

DecisionRecord extends Record and includes every owner field: opportunity/project IDs+versions, profile_version, eligibility_gate, conflict_status, project_match, strategy_score, strategy_breakdown, readiness, capacity, effort, recommendation, reason_codes, missing_information, next_action, freshness_status, policy_versions. Include full conflict and affordability assessments for explanations. DECISION_POLICY_VERSION=1; all threshold/next-action mappings reside in policy.py. Ratings/results supplied by fixtures are forbidden extras; only explicit source facts/assumptions are accepted. Revalidate inputs at public boundaries.

For each candidate recompute QUALOR-01 aggregate_eligibility using the supplied rules and that exact project/profile/opportunity/evidence/time. Compute matching, readiness, effort, capacity, affordability, conflict and strategy, then the six ordered recommendation rules. Do not trust an input EligibilityGate. Opportunity CLOSED or an exact elapsed deadline => SKIP; unknown opportunity status/timing cannot yield an actionable decision. Calendar-only deadlines remain uncertain rather than invented UTC midnight.

DecisionResult contains nullable best_project_id, selection, candidate DecisionRecords, selected_decision (nullable), overall recommendation, reasons and missing information, mode=FIXTURE. An unresolved portfolio yields WATCH (or SKIP if every candidate is SKIP); never choose the first tied candidate. Candidate decisions are conditional per-project analyses, not automatic portfolio selection. Selection compares matching only; explanations retain eligibility/conflict outcomes for every candidate.

Policy Rules 1–6 must be implemented in exact order: closed/expired OR eligibility FAIL OR explicit conflict -> SKIP; eligibility REVIEW_REQUIRED OR conflict REVIEW_REQUIRED OR score unknown -> WATCH; eligibility PASS + score>=75 + sufficient capacity + confirmed affordability + READY + checked-no-conflict -> APPLY; eligibility PASS + score>=60 + executable readiness gaps + sufficient capacity + checked-no-conflict -> PREPARE; PASS+score>=60 with capacity insufficient/unknown OR affordability unknown OR readiness unknown -> WATCH; otherwise SKIP. Next actions: prepare application package / close listed readiness gaps / resolve listed unknowns / record reason without action. No external action is executed.

- [ ] RED B01–B13, B21, B39–B40 and all direct unsafe-APPLY regressions, priority cross-product, duplicate/over-five projects, forged outputs, unknown/expired opportunity, tied portfolio.
- [ ] GREEN policy/composition with existing modules. Then author all twelve owned fixtures: D01 ready/high APPLY; D02 medium/executable PREPARE; D03 FAIL/high prize SKIP; D04 eligibility review WATCH; D05 explicit conflict SKIP; D06 unknown score WATCH; D07 insufficient capacity WATCH; D08 low score SKIP; D09 two candidates clear best; D10 tied unresolved; D11 cloud credits not cash; D12 unknown open-source conflict REVIEW/WATCH. Source excerpts must be owned and hashes match UTF-8 snapshot bytes.
- [ ] RED CLI `decide-fixture` and JSON-only `/dev/decide-fixture`, invalid/LIVE/forged/path inputs; GREEN with structured fields requested by owner. CLI prints MODE, ELIGIBILITY, BEST_PROJECT, STRATEGY_SCORE, CONFLICT, READINESS, CAPACITY, RECOMMENDATION; unknown/tied values explicitly UNKNOWN/UNRESOLVED. API exposes assessments and missing information, not only a label.
- [ ] Commit logical engine and fixture/adapters changes; run every D fixture and unchanged F fixtures. Review spec and quality.

## Task 5: Canonical schema expansion and TypeScript generation

**Files:** modify `src/qualor/schemas/export.py`, `tests/domain/test_schema_export.py`, `scripts/verify.ps1`, `apps/web/package.json`, `apps/web/package-lock.json`; create `scripts/generate-types.ps1`, a focused Node generator under `apps/web/scripts/`, `tests/test_type_codegen.py`, generated `apps/web/src/generated/domain.ts`; regenerate `schemas/*.schema.json`.

Export original eight contracts plus ProjectMatch, ProjectSelection, ReadinessAssessment, EffortEstimate, CapacityAssessment, AffordabilityAssessment, StrategyAssessment, ActiveSubmission, ConflictAssessment, DecisionRecord, DecisionFixture, DecisionResult. The authoritative registry drives schema tests; confirm every required contract and prevent drift.

Use a maintained JSON Schema -> TypeScript development package, inspect official package/repository documentation/current version, pin the exact compatible version in npm lockfile. Do not implement a homegrown partial JSON Schema translator. Assemble a deterministic schema bundle preserving refs/recursive types and avoiding colliding shared definitions; fail explicitly on incompatible collisions. No manually duplicated type bodies.

`scripts/generate-types.ps1` generates `domain.ts`; `-Check` compares without mutation and returns nonzero for drift. Build/typecheck must include generated types. Add codegen drift to verify after npm ci, and schema drift remains checked. Document serialization-schema/runtime-validator distinction.

- [ ] RED tests for all new public exports, deterministic bytes, stale-output detection, recursive references, no probability field names, and frontend compilation against representative valid/invalid contracts.
- [ ] GREEN generator, lockfile, regenerated schemas/types; run npm ci/build and Python tests. No UI changes.
- [ ] Commit `feat: generate frontend domain types`; task review verifies generation authority and no hand-written duplicate interfaces.

## Task 6: Final evidence, scope/security audit and PR

**Files:** create `docs/status/QUALOR-02.md`; update README and this plan's execution evidence. Add ADR only if a new non-trivial architecture decision exceeds the already documented canonical boundaries.

- [ ] Map B01–B40 and all unsafe-APPLY counters to executed tests. Record versions, fixture count, exact test count, limits, no-probability semantics, all zero AWS/inference/resource counts.
- [ ] Stage intended files, run existing canonical/secret-pattern audit against staged/worktree bytes, inspect actual tracked diff and dependency direction; no proprietary source or third-party rules content. Commit checkpoint documentation.
- [ ] On clean committed tree run verify.ps1, aws-preflight.ps1, export-schemas.ps1, generate-types.ps1; independent Ruff/pytest/npm ci/build; every D fixture CLI; unchanged F fixture acceptance; git diff --check and clean status. Use only existing non-root AWS profile, no IAM/config changes.
- [ ] Broad independent whole-branch review; resolve blocking findings with tests and re-review. Push branch, create PR `QUALOR-02: Add project strategy and decision core` against main and wait for CI on exact resulting HEAD. Do not merge. Return exactly the owner Result Packet and stop.

## Acceptance mapping

| Owner cases / invariant | Owning test surface |
| --- | --- |
| B01–B13, B39 recommendation precedence and boundaries | decisions/test_decisions.py |
| B14–B19 valid/invalid/unknown factors, integer score | strategy/test_strategy.py |
| B20 score fields not probability | strategy tests + type_codegen |
| B21 FAIL survives prize | decisions tests + D03 |
| B22–B23 credits/equity not cash | effort/test_effort.py + D11 |
| B24–B28 match strength, unknowns, ties | matching/test_matching.py + D09/D10 |
| B29–B31 readiness completeness | matching/test_matching.py |
| B32–B34 effort bounds/unknowns/totals | effort/test_effort.py |
| B35–B38 conflicts and qualified clearance | conflicts/test_conflicts.py + D05/D12 |
| B40 decision roundtrip | decisions/test_decisions.py + D fixtures |
| All unsafe APPLY counters zero | decision priority matrix + pipeline adversarial fixtures |
| No imputation/tied auto-selection/credit cash conversion | matching/strategy/effort/decision tests |
| Existing eligibility invariants and 180-test baseline | full pytest and unchanged F fixtures |
| CLI/API fixture isolation, no paths/live/output overrides | test_decision_adapters.py |
| Schema/TS generation authority and drift | schema/codegen tests + verify + build |
| Secrets, canonical, clean worktree | verify + tracked audit |
| No agent/network/persistence/proprietary import | source/dependency audit + offline fixture tests |
| PR unmerged and exact-head CI | GitHub CLI validation |

## Execution evidence

Baseline gates completed before branching: canonical hash, 180 tests, Ruff, web build, verify, AWS read-only preflight and eight-schema regeneration PASS. AgentCore read permission gaps remain intentionally deferred. Task implementation/review outcomes will be recorded here and in the final status document.

Tasks 1–5 completed with observed RED/GREEN steps and independent spec/quality review. Matching added 21 tests; effort/strategy added 52; conflicts added 54; decisions/adapters added 84; schema/codegen added four. The resulting suite contains 395 passing tests. Reviews corrected an unrequested currency allowlist and a same-project lineage disagreement gap, each with a failing regression before its fix. No eligibility behavior or canonical bytes changed.

Implementation commits: `0d289f0` matching; `4b88280` effort/strategy; `3eb5d32` same-currency correction; `bb8d8be` conflicts; `d8e6c41` lineage correction; `cde323b` decision composition; `5d2a97c` fixture adapters; `675e9bf` schema/TypeScript generation. All five task reviews approved their final implementation. The full verification script passed on `675e9bf9b373c0b9730f36ae9d41ec2bd5273e87` with 20 schemas and deterministic generated types. All twelve D and eight F fixtures ran through the real CLI. Independent review compared all 3,888 policy combinations with the six-rule oracle.

The [checkpoint status](../../status/QUALOR-02.md) records implementation facts and limitations. Final documentation, whole-branch review, fresh verification and remote publication gates are controller-owned; the final Result Packet records the exact publication HEAD and CI result. No PR merge or QUALOR-03 work is authorized in this task.
