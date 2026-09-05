# QUALOR-02 — Project Matching, Strategy & Decision Core

Date: 2026-09-05. Repository: `brenychstudio/qualor` (private).

Baseline: `8f7fdeb0d34093085895537619d42cccfa1e06aa` on `main`, verified clean before branching. Task branch: `qualor-02-decision-core`.

Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`. Canonical bytes remain unchanged. The [implementation plan](../superpowers/plans/2026-09-05-qualor-02-decision-core.md) was committed before implementation.

Implementation checkpoint tested: `675e9bf9b373c0b9730f36ae9d41ec2bd5273e87`. Final publication HEAD, PR and CI state are reported separately in the Result Packet after documentation and final verification.

## Implemented

- `domain/planning.py` and additive profile/opportunity facts preserve unknown defaults and existing eligibility behavior.
- `matching/` assesses seven explicit factors and eight material categories. It selects a unique best comparable project from at most five candidates. Ties or unevidenced candidates leave selection unresolved.
- `effort/` retains six preparation ranges plus the existing explicit adaptation estimate, assesses conservative capacity and separates cash, credit coverage and equity consent.
- `strategy/` calculates integer prioritization from known ratings. No rating is imputed.
- `conflicts/` checks seven explicit rule categories across current and supplied active contests, with scoped evidence coverage and qualified results.
- `decisions/` recomputes QUALOR-01 eligibility for each project and applies the six ordered recommendation rules. DecisionRecord includes versioned assessments, reason codes, a bounded explanation and next action.
- `decide-fixture` and development-only `POST /dev/decide-fixture` consume structured source facts. The API accepts no filesystem path or authoritative supplied score/gate/recommendation. Output is always FIXTURE.
- Twenty canonical schemas generate `apps/web/src/generated/domain.ts`; no dashboard or handwritten domain interfaces were added.

## Policies

MATCH_POLICY_VERSION, STRATEGY_POLICY_VERSION, EFFORT_POLICY_VERSION, CONFLICT_POLICY_VERSION and DECISION_POLICY_VERSION are all **1**. Existing eligibility/freshness policies remain unchanged.

| Strategy factor | Weight |
| --- | ---: |
| product_fit | 30 |
| readiness | 25 |
| time_feasibility | 20 |
| strategic_value | 15 |
| economic_affordability | 10 |

Ratings are strict integers 0–4 or unknown. Any unknown factor hides the aggregate. Known scores use integer half-up rounding: `(sum(rating * weight) + 2) // 4`. Ratings 4/3/3/4/2 produce **84**. The exported semantics are `PRIORITIZATION_NOT_WIN_PROBABILITY`.

Recommendation order is fixed: hard blockers produce SKIP; eligibility/conflict review or unknown score produce WATCH; fully confirmed high-priority readiness produces APPLY; executable gaps meeting Rule 4 produce PREPARE; the specified remaining uncertainty produces WATCH; otherwise SKIP. Rule 4 retains the owner's exact predicate. In the full pipeline, unknown affordability makes the strategy score unknown and reaches WATCH earlier.

## Acceptance evidence

At the implementation checkpoint, `scripts/verify.ps1` passed with **395 tests**, zero failures/skips, Ruff, schema/type drift checks, frontend typecheck/build, canonical/secret checks and a clean worktree. The two test warnings are dependency deprecations involving Starlette/httpx and AnyIO; dependencies were not changed to hide them.

The suite covers all **40 gold decision concepts** B01–B40, plus input validation and composition regressions. These are acceptance concepts, not an inflated count of pytest cases.

| Gold cases | Evidence surface |
| --- | --- |
| B01–B13, B39 | Decision threshold cases and a 3,888-combination priority matrix |
| B14–B19 | Strict ratings, unknown propagation, repeatability and all 3,125 known rating combinations |
| B20 | Python/schema public property-name checks and generated contract compilation |
| B21 | Real eligibility FAIL with a large synthetic prize remains SKIP |
| B22–B23 | Cash budget, cloud credit and equity-consent tests |
| B24–B28 | Match strengths, missing facts, unique selection and ties |
| B29–B31 | Complete readiness, explicit gaps and unknown material facts |
| B32–B34 | Ordered ranges, missing adaptation and deterministic totals |
| B35–B38 | Explicit conflicts, missing external coverage and qualified clearance |
| B40 | DecisionRecord/DecisionResult deterministic JSON roundtrips |

Measured unsafe APPLY counts in the policy matrix are **0** for eligibility FAIL, eligibility REVIEW_REQUIRED, explicit conflict, unknown score, unknown capacity and unknown affordability. Existing critical UNKNOWN/FAIL false-PASS regressions remain green. Unknown-factor imputation, probability field names, an absolute NO_CONFLICT status, cloud-credit cash conversion and automatic tie selection are absent.

## Owned synthetic fixtures

All twelve D fixtures and the eight original F fixtures executed through the real CLI successfully. No live data or external rules content was imported. Short synthetic evidence snapshots have matching UTF-8 SHA-256 hashes; hashes establish bytes, not semantic truth.

| Fixture | Recommendation | Selected score | Key outcome |
| --- | --- | ---: | --- |
| D01 | APPLY | 100 | Ready, eligible and affordable |
| D02 | PREPARE | 71 | Executable readiness gap |
| D03 | SKIP | 100 | Hard eligibility failure survives high prize |
| D04 | WATCH | 100 | Eligibility requires review |
| D05 | SKIP | 100 | Explicit license conflict |
| D06 | WATCH | UNKNOWN | Missing strategic goal facts |
| D07 | WATCH | 80 | Insufficient capacity |
| D08 | SKIP | 38 | Weak fit and non-executable readiness |
| D09 | APPLY | 100 | Unique best match; other candidate scores 93 |
| D10 | WATCH | UNKNOWN | Tied candidates; no selected project |
| D11 | SKIP | 90 | Credits do not pay the cash fee |
| D12 | WATCH | 100 | Unknown permitted licenses require conflict review |

D10 retains two conditional score-100 candidate assessments, each conditionally APPLY, but exposes no chosen assessment or automatic portfolio action.

## Reproducibility and boundaries

The pinned compiler is `json-schema-to-typescript@16.0.0`, with the npm lockfile committed. Generation consumes canonical exported schemas, deduplicates identical shared definitions, rejects incompatible collisions and preserves recursive references. File/HTTP reference resolution is disabled. `generate-types.ps1 -Check` fails on drift without rewriting output. Tests compile representative valid and invalid TypeScript contracts. Frontend dependencies are installed before Node-dependent pytest tests in clean CI.

Generated TypeScript describes serialization shapes. Python runtime validators still enforce integer bounds, decimal/date formats, uniqueness, evidence/freshness and cross-field consistency. Large bounded arrays may be approximated by the compiler.

Matching uses exact normalized explicit labels, not semantic inference. Matching selection does not rerank candidates by recommendation; every candidate retains its own eligibility/conflict result. Effort is only as complete as the supplied assumptions; the original scalar adaptation fact is displayed as an explicit point range. Calendar-only deadlines do not become invented instants. Conservative rule bounds constrain capacity, while unsupported rules do not establish authoritative expiry.

Cash arithmetic requires the same currency; there is no FX conversion. Credits, equity and prizes never expand cash budget. Conflict checking evaluates the proposed entry against supplied rules and active submissions, not global legal clearance or an audit of all past contest compliance. V1 requires distinct active contest scopes. Missing rules, unsupported interpretation, stale evidence or relevant same-project fact disagreements require review; confirmed explicit violations retain priority.

## Security, AWS and deferred work

No proprietary product source, third-party full rules content, credentials or private account metadata was imported. Runtime modules remain deterministic and offline. AWS resource creation, paid AWS calls and Bedrock inference calls: **0**. Estimated task AWS cost: **USD 0**.

The existing development bridge/profile/MCP/IAM configuration was not changed. Baseline read-only preflight passed; Bedrock and Sonnet 4.6 discovery were available, inference remained NOT_TESTED. AgentCore runtime/gateway listing permission gaps and Web Search UNVERIFIED remain intentionally deferred. Discovery is not deployment or invocation permission.

Deferred to later tasks: Strands behavior, LLM matching/scoring/effort, live discovery/search/fetch, persistence, real dashboard, authentication, cloud deployment and external submission. QUALOR-03 was not started. This checkpoint is prepared for review through an unmerged PR.
