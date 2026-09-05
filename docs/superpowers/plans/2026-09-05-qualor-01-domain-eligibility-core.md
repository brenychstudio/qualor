# QUALOR-01 implementation plan

> **For agentic workers:** Execute task-by-task using Superpowers TDD and verification-before-completion. The owner supplied the implementation specification and authorized execution in this checkout and task branch.

**Goal:** Pure, evidence-linked deterministic eligibility with no agent, network, storage or recommendation dependency.

**Architecture:** Pydantic is the contract authority. Explicit profile facts preserve provenance; discriminated scalar values avoid coercive comparisons. The engine resolves only enumerated profile references, checks supporting evidence and computes coverage and the final gate itself. Consumers supply candidates, never authoritative evaluations.

**Stack:** Existing Python 3.12, Pydantic v2, FastAPI, Typer, pytest and Ruff; unchanged dependency locks and frontend shell.

**Spec:** Owner's QUALOR-01 task and `docs/00_CANONICAL_BRIEF_UA.md`, especially sections 10–12. Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.

## Boundaries and baseline

- Base `919905ce5441c1d60dc4bbcc0559e5530b824239`; branch `qualor-01-domain-eligibility-core`.
- Baseline verify: 42 tests, Ruff, web build, canonical/secrets and clean tree PASS.
- AWS preflight PASS; AgentCore ListAgentRuntimes/ListGateways remain BLOCKED_PERMISSION. No IAM or MCP change.
- No paid AWS calls, inference, resources, live search, extraction, persistence, score, recommendation, agent, submission or real UI.
- Supplied timestamps, not wall-clock defaults, make fixtures repeatable. Exact timestamps reject naive values and normalize to UTC; dates remain dates.
- Schema/version/id/created/updated/provenance metadata required on persistent records. Extra fields forbidden; immutable validated models prevent accidental post-validation changes.
- Unknown facts cannot carry known values; known facts need provenance. No residence/citizenship or legal-form inference.
- Unsupported candidates use `supported=false`; unknown operator names fail validation. Invalid operator/operand combinations return UNKNOWN.
- Critical evidence must exist, match the rule category, have a reviewed extraction state, and come from official rules/FAQ/application or explicitly synthetic fixture sources. Hash alone is insufficient. Synthetic evidence is accepted only in FIXTURE mode.
- Freshness uses 24h normally, 6h with less than 72h remaining. Exact TTL boundary is stale. Unknown calendar deadline uses conservative 6h; future retrieval timestamps are unknown. Failed refresh metadata never replaces retrieved_at.
- All nine critical categories need evaluated rules or explicit, evidence-supported non-applicability. Non-critical unknowns are retained but cannot override critical results.
- OR/AND preserve three-valued semantics; a passing alternative may resolve an unknown alternative. A critical stale or contradiction marker remains visible and prevents aggregate PASS.
- API accepts validated JSON only, no paths, only in development; CLI accepts an explicit local synthetic fixture path. Both expose FIXTURE labels and the engine result.
- TypeScript codegen deferred to QUALOR-02; no duplicate handwritten domain types.

## Files and public interfaces

Create `src/qualor/domain/{__init__,base,enums,money,profiles,opportunity,evidence,rules,values,fixture}.py`.
Base owns immutable validation/record metadata and `Fact[T]`; enums own bounded statuses/categories; values owns tagged text/number/bool/date/instant scalar types; money owns Decimal Money and distinct Reward kinds; profiles owns FounderProfile/ProjectProfile; opportunity owns deterministic identity/URL normalization and date-or-instant deadlines; evidence owns snapshots; rules owns candidates/results/coverage/gate; fixture owns the validated synthetic input envelope.

Create `src/qualor/eligibility/{__init__,operators,freshness,coverage,subjects,engine}.py`.

```python
evaluate_operator(operator: Operator, actual: Scalar | None,
                  operands: tuple[Scalar, ...], statuses: tuple[RuleStatus, ...] = ()) -> RuleStatus
evaluate_freshness(retrieved_at: datetime, evaluated_at: datetime,
                   deadline: date | datetime | None = None) -> FreshnessStatus
evaluate_rule(rule: RuleCandidate, context: EvaluationContext) -> RuleEvaluation
evaluate_rules(rules: tuple[RuleCandidate, ...], context: EvaluationContext) -> tuple[RuleEvaluation, ...]
evaluate_coverage(rules: tuple[RuleCandidate, ...], evaluations: tuple[RuleEvaluation, ...]) -> tuple[CoverageEntry, ...]
aggregate_eligibility(rules: tuple[RuleCandidate, ...], context: EvaluationContext) -> EligibilityGate
```

EvaluationContext contains founder, project, opportunity, evidence, evaluated_at and mode=FIXTURE. RuleCandidate contains category, operator, operands, explicit subject reference or child candidates, criticality, evidence IDs, supported flag, summary, optional non-applicability reason and contradiction flag. No input evaluation/verdict field. Composite rules retain child evaluations. The aggregate function recomputes evaluations; it does not accept caller-supplied verdicts.

Create `src/qualor/schemas/{__init__,export}.py`, `scripts/export-schemas.ps1`, eight public `schemas/*.schema.json` files. `export_schemas(output_dir: Path) -> tuple[Path, ...]` writes sorted, deterministic JSON; `python -m qualor.schemas.export --check` verifies committed output without rewriting it.

Modify `src/qualor/{api,cli}.py` only for fixture adapters. Modify `scripts/verify.ps1` to check schemas. Create `docs/status/QUALOR-01.md`; update README with the implemented development commands. No canonical or AWS bridge edits.

## Task 1 — domain contracts

- [ ] Write `tests/domain/test_contracts.py` for A31–A40, fact provenance, enum strictness, unexpected fields, reward ranges, deadlines, identity, record versions and serialization.
- [ ] RED: `uv run pytest tests/domain -q`; new-contract import/assertion failures must identify absent behavior.
- [ ] Implement base/enums/values/money/profiles/opportunity/evidence/rules contracts and public exports.
- [ ] GREEN: repeat domain tests; Ruff; refactor only with tests green.
- [ ] Commit `feat: add QUALOR domain contracts` with this plan and tests.

## Task 2 — operators, freshness and engine

- [ ] Write `tests/eligibility/test_operators.py` A07–A19, invalid types, empty logical input, all truth-table combinations.
- [ ] RED, implement pure comparisons with same-kind operands and inclusive ranges, GREEN.
- [ ] Write `tests/eligibility/test_freshness.py` A28–A30 plus exact TTL/72h boundaries, future and naive times. RED, implement named version/TTL constants, GREEN.
- [ ] Write `tests/eligibility/test_engine.py` A01–A06, A20–A27 plus nested evidence, contradiction/stale priority, duplicate IDs, category mismatch, non-critical unknown and forged result rejection.
- [ ] RED, implement enumerated subject resolution, evidence checks, coverage, ordered FAIL/REVIEW/PASS aggregation, GREEN.
- [ ] Commit `feat: add deterministic eligibility engine` after focused tests and Ruff.

Test examples defining the safety outcomes:

```python
assert evaluate_operator(Operator.OR, None, (), (RuleStatus.PASS, RuleStatus.UNKNOWN)) == RuleStatus.PASS
assert evaluate_operator(Operator.AND, None, (), (RuleStatus.PASS, RuleStatus.UNKNOWN)) == RuleStatus.UNKNOWN
assert aggregate_eligibility((), context).state == GateState.REVIEW_REQUIRED
assert evaluate_freshness(now - timedelta(hours=24), now) == FreshnessStatus.STALE
```

## Task 3 — owned fixtures and adapters

- [ ] Author eight complete JSON envelopes under `tests/fixtures/F01_FULL_PASS.json` through `F08_NEW_PROJECT_PROVENANCE_UNKNOWN.json` using invented `.example` sources and owned short excerpts. Expected outcomes: PASS, FAIL, REVIEW_REQUIRED, REVIEW_REQUIRED, REVIEW_REQUIRED, PASS, REVIEW_REQUIRED, REVIEW_REQUIRED.
- [ ] Write `tests/eligibility/test_fixtures.py` validating all envelopes and exact states/reasons; `tests/test_fixture_adapters.py` tests CLI labels/result, malformed fixtures, API JSON-only input, non-development denial and absence of verdict overrides.
- [ ] RED adapters first; implement `FixtureInput`, CLI `evaluate-fixture`, API `/dev/evaluate-fixture`; GREEN including original health/doctor tests.
- [ ] Commit `test: add canonical eligibility fixtures` including fixture adapters.

## Task 4 — schemas and final gates

- [ ] Write `tests/domain/test_schema_export.py` for all eight schemas, repeat byte equality and checked-output drift detection. RED, implement exporter and PowerShell invocation, GREEN.
- [ ] Export and commit schemas; integrate `--check` in verify. No frontend types or UI changes.
- [ ] Update README/status with interfaces, fixtures, limitations, exact observed results and policy versions. Commit `feat: export canonical domain schemas` and checkpoint documentation as logical changes.
- [ ] Run `scripts/verify.ps1`, `scripts/aws-preflight.ps1`, `scripts/export-schemas.ps1`, independent Ruff/pytest/npm ci/build, `git diff --check`, every fixture CLI, secret/provenance scan and clean status.
- [ ] Review scope and acceptance matrix; push branch; create PR `QUALOR-01: Add deterministic eligibility core`; wait for CI on exact HEAD. Do not merge or start QUALOR-02.

## Acceptance-to-test matrix

| Requirements | Tests / gate |
| --- | --- |
| A01–A06 aggregation and empty input | test_engine + eight JSON acceptance fixtures |
| A07–A15 scalar operators | test_operators |
| A16–A19 logical uncertainty | test_operators + F06/F07 |
| A20 residence/citizenship | test_engine residency case |
| A21 sole trader/company | test_engine legal case + F02 |
| A22 geography silence | test_engine unsupported geography evidence |
| A23 new-project provenance | test_engine new-project case + F08 |
| A24 missing evidence | test_engine missing/mismatched evidence |
| A25 unsupported candidate | test_engine unsupported candidate |
| A26 contradiction | test_engine contradiction marker |
| A27 explicit N/A | test_engine N/A reason/evidence |
| A28–A30 freshness | test_freshness + F04 |
| A31–A34 rewards/money | test_contracts |
| A35–A36 identity | test_contracts |
| A37–A40 UTC/roundtrip/schema version | test_contracts |
| Fields, strict enums, provenance | test_contracts; schema export |
| Public APIs, coverage/policy versions | test_engine/test_freshness |
| FIXTURE CLI/API and no override | test_fixture_adapters |
| No network/LLM dependency | fixture tests deny network; import audit |
| Deterministic schema authority | test_schema_export + exporter --check |
| Bootstrap regressions | complete existing suite + verify.ps1 |
| Canonical, no secrets, clean Git | verify.ps1 + final tracked diff audit |
| No resources/inference | allowed read-only preflight only; source/scope audit |
| PR unmerged, exact CI | gh PR and check status for resulting HEAD |

The A01–A40 gold IDs will appear in pytest case names, making the matrix mechanically auditable. Policy limitations are recorded; passing synthetic tests is not proof of real-world legal interpretation.
