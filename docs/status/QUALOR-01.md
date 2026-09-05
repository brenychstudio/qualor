# QUALOR-01 — Domain contracts and deterministic eligibility core

Date: 2026-09-05. Repository: `brenychstudio/qualor` (PRIVATE).
Base: `919905ce5441c1d60dc4bbcc0559e5530b824239`.
Task branch: `qualor-01-domain-eligibility-core`.

Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`; unchanged, matching 62,438 bytes.

## Implemented contracts and boundaries

Pydantic v2 owns FounderProfile, ProjectProfile, OpportunityRecord, EvidenceRecord, Reward, RuleCandidate, RuleEvaluation and EligibilityGate. Persistent records require schema version, ID, positive version, UTC timestamps and provenance. Models are immutable and reject unexpected fields; evaluation revalidates inputs. Calendar-only dates retain their precision. Money uses Decimal and rejects float input; reward kind and total-pool flag remain separate.

Facts preserve USER_ASSERTED / DOCUMENTED / UNKNOWN provenance. Missing citizenship is never inferred from residence. Sole traders remain distinct from incorporated companies. New-project checks require documented original-code provenance and documented new-work status; recent record creation is insufficient.

The task's conceptual operand is stored as a typed `operands` tuple, with discriminated text, number, boolean, date and instant values. Supported operators: EQ, IN, GTE, LTE, BETWEEN, DATE_BETWEEN, BOOL_IS, AND, OR. Bounds are inclusive. Invalid combinations and unsupported candidates become UNKNOWN; unrecognized operator names fail input validation. Technology membership can require one of a stated set; use AND of individual membership rules for all-required technologies.

Evidence references must exist, match the category and assert reviewed extraction. Search snippets, third-party sources and marketing announcements cannot support hard eligibility. Synthetic evidence is restricted to the explicit FIXTURE context. Original/final evidence URLs are preserved. Fixture snapshots are owned short excerpts with SHA-256 computed from their UTF-8 bytes; no third-party pages were imported.

## Versioned policy

```text
ELIGIBILITY_POLICY_VERSION=1
COVERAGE_POLICY_VERSION=1
FRESHNESS_POLICY_VERSION=1
```

Coverage contains all nine canonical categories: deadline, entrant type, geography, legal entity, new/existing project, license, technology, financial support and material reward conditions. Each entry is EVALUATED, NOT_APPLICABLE_WITH_REASON, UNKNOWN or MISSING. Explicit non-applicability requires a reason and supporting evidence and cannot override an executable expression.

Critical confirmed FAIL has first priority. Missing coverage, unresolved critical unknowns, stale evidence or contradiction markers prevent PASS. Empty rules never pass. Non-critical unknowns remain in evaluations without overriding critical results. Nested composites preserve three-valued logic, including confirmed FAIL through AND/OR composition. The aggregate API recomputes evaluations; no fixture/API input can supply a final verdict.

Freshness TTL is 24h normally, 6h when less than 72h remains; exact TTL boundary is stale. The tightest deadline from opportunity metadata and nested deadline rules controls freshness. Unknown/calendar-only deadline timing uses a conservative 6h TTL. Failed refresh metadata never replaces retrieved_at; future snapshot timestamps remain unverified. No live refresh exists.

## Acceptance evidence

| Fixture | Expected and observed |
| --- | --- |
| F01_FULL_PASS | PASS; all nine categories evaluated |
| F02_HARD_LEGAL_FAIL | FAIL |
| F03_UNKNOWN_LEGAL_STATUS | REVIEW_REQUIRED |
| F04_STALE_CRITICAL_EVIDENCE | REVIEW_REQUIRED |
| F05_INCOMPLETE_COVERAGE | REVIEW_REQUIRED |
| F06_OR_ALTERNATIVE_PASS | PASS |
| F07_OR_UNRESOLVED | REVIEW_REQUIRED |
| F08_NEW_PROJECT_PROVENANCE_UNKNOWN | REVIEW_REQUIRED |

All 40 gold acceptance IDs A01–A40 are mapped to tests in the implementation plan. Eight fixture files were independently executed with `uv run qualor evaluate-fixture`; all outcomes matched. Observed critical-UNKNOWN false PASS count: 0; critical-FAIL false PASS count: 0 in the acceptance suite. These are synthetic deterministic test results, not real-world eligibility accuracy claims.

Local verification on the completed implementation:

```text
RUFF=PASS
PYTEST=PASS
TEST_COUNT=178
QUALOR_CODE_WARNINGS=0
BASELINE_TESTS=42_PASS
WEB_TYPECHECK=PASS
WEB_BUILD=PASS
VERIFY_SCRIPT=PASS
SCHEMA_EXPORT=PASS
SCHEMA_FILES=8
FIXTURE_CLI=PASS
FIXTURE_API=PASS
SECRETS_SCAN=PASS
CANONICAL_HASH_MATCH=PASS
```

Commands: `scripts/verify.ps1`, `scripts/aws-preflight.ps1`, `scripts/export-schemas.ps1`, Ruff, pytest and all eight fixture CLI invocations. Verification includes dependency locks, schema drift, unchanged bootstrap health/doctor, frontend typecheck/build, canonical/secret audit and clean Git state. Independent reviewer: 136 focused tests PASS after regression fixes; no remaining important blockers.

The eight committed schemas are deterministic Pydantic serialization schemas. Runtime cross-field validators remain necessary; valid JSON is not semantic proof. Schema regeneration leaves no diff, and CI checks drift through the existing verification script. TypeScript generation is explicitly deferred to QUALOR-02; no handwritten duplicate frontend domain interfaces were added.

## AWS and provenance

Read-only preflight passed with `qualor-dev`, `us-east-1`, temporary IAM_USER authentication and no root agent access. Bedrock control plane and Sonnet 4.6 discovery PASS; inference NOT_TESTED. AgentCore Runtime/Gateway remain BLOCKED_PERMISSION for `bedrock-agentcore:ListAgentRuntimes` and `bedrock-agentcore:ListGateways`; Web Search remains UNVERIFIED. No permissions, profiles, MCP configuration or AWS bridge code changed.

```text
BEDROCK_INFERENCE_CALLS=0
AGENTCORE_RESOURCES_CREATED=0
AWS_PAID_CALLS=0
AWS_ESTIMATED_TASK_COST=USD_0
ACCOUNT_IDS_COMMITTED=NONE
PRIVATE_ARNS_COMMITTED=NONE
AWS_TOKENS_COMMITTED=NONE
PROPRIETARY_CODE_IMPORTED=NO
THIRD_PARTY_FULL_RULES_PAGES_COMMITTED=NO
```

## Limits and deferred work

Eligibility PASS means conformity to supplied reviewed facts and rules under policy v1, not legal certification or organizer approval. Source review/provenance assertions are explicit inputs; no text interpretation, extraction, source selection or live authenticity verification is implemented. Fixed fixture evaluation timestamps make reproduction possible and do not represent a live current-time decision.

No strategy score, recommendation, conflict checker, agent, Strands behavior, inference, search, fetching, persistence, approval, submission or real product UI exists in this task. The JSON-only development route is disabled outside development and has no side effects. Domain schemas support future persistence but do not implement it.

No new ADR is required: the canonical architecture remains unchanged. Exact final HEAD, PR URL, CI and worktree results are recorded in the Result Packet and Git/PR evidence. PR is to remain unmerged; QUALOR-02 requires a separate task.

## QUALOR-01M protected merge correction

Fresh protected review reproduced a deadline-policy gap: EQ/IN comparisons against the evaluation instant could return PASS without supplying a bound to the near-deadline freshness policy. Two regression cases first returned false PASS. V1 deadline leaves now accept only DATE_BETWEEN; other temporal shapes return UNKNOWN/UNSUPPORTED. Logical AND/OR of supported deadline intervals remains available. The scalar operator API and other rule categories are unchanged.

After this correction, the full suite contains 180 passing tests. The original 178-test checkpoint above is historical. Complete pre/post-merge gates and CI must be verified against the corrected HEAD under QUALOR-01M before reporting merge completion. No canonical, schema, AWS configuration or feature-scope changes are needed.
