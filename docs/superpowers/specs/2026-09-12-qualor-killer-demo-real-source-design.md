# QUALOR Real-Source Killer Demo Design

**Status:** Canonical design for the QUALOR killer demo

**Date:** 2026-09-12

**Frozen base:** `feature/qualor-04b-judge-impact` at
`a2f92d9ab35815167c38f9b687c52de94465343f`

**Product:** QUALOR — Autonomous Opportunity Intelligence

QUALOR-04B delivered a judge-ready product experience over an owned synthetic fixture. This
document canonizes the demo that replaces that fixture with **real, current, official source
evidence**, and records what is and is not currently true so the implementation plan closes
real gaps rather than staging an outcome.

```text
IMPLEMENTATION_AUTHORIZED_BY_THIS_DOCUMENT=NO
```

## 1. The demo opportunity is real

The killer demo evaluates the **Agents for Humans Hackathon**, sponsored by Amazon Web
Services and administered by Devpost, Inc.

The candidate project QUALOR evaluates is **QUALOR itself**, entered against the
**Professional Agents** track.

This is not a narrative device. It is the actual opportunity this project is being submitted
to, which is what makes the demo defensible: the judge can open the cited source and check it.

## 2. Source authority

Only the official Devpost hackathon site is evidence.

| Source ID | Canonical source | Authority |
| --- | --- | --- |
| `SRC-OFFICIAL-RULES` | `https://agentsforhumans.devpost.com/rules` | Official Rules — primary |
| `SRC-OFFICIAL-OVERVIEW` | `https://agentsforhumans.devpost.com/` | Hackathon Overview — supporting |

Both were retrieved 2026-09-12, HTTP 200, and stored with their SHA-256 content hashes in the
gitignored local capture area. Raw captured pages are **never committed**.

The following are **not** evidence and may never become evidence: search snippets, Reddit,
blogs, social posts, third-party summaries, cached scraped copies, and model memory. A fact
not supported by an official page is recorded `UNKNOWN`. `UNKNOWN != PASS` continues to hold.

## 3. `STRUCTURED_FACT == SOURCE_EVIDENCE`

This is the rule the whole demo rests on, and the rule W01 could not satisfy.

Every structured fact the product displays must be provable by the exact source excerpt shown
beside it. The excerpt must be **verbatim** — not a paraphrase, not a tidied quotation, not a
reflowed one.

This is mechanically enforced, not asserted. The claim set is built by a script that verifies
each `EXACT_SOURCE_EXCERPT` occurs character-for-character in the captured source text and
fails closed otherwise. That check has already caught one real defect: a hand-typed excerpt
added a space after a bold label where the source runs the label straight into the sentence
(`New Projects Only:Projects must be...`). The excerpt was corrected to a bounded verbatim
span rather than the quotation being loosened.

Excerpts stay bounded to what proves the fact.

## 4. Temporal truth

**Absolute official dates are absolute.** The Submission Period closes Monday, September 14,
2026 at 5:00 pm Pacific Time — `2026-09-15T00:00:00Z`. That instant is what the source says
and it is what the product must show.

The killer demo must not inherit the fixture clock rebase. `_rebased_observations` in
`src/qualor/cli.py` slides every temporal fact in a workspace fixture onto the current clock
so a synthetic scenario keeps its intervals. That is correct for an owned scenario and
**fatal** for real source evidence: it would move a quoted official deadline away from the
quoted official text, reproducing exactly the mismatch this demo exists to eliminate.

```text
TEMPORAL_REBASE=PROHIBITED_FOR_REAL_SOURCE
```

Current time may affect freshness and time-to-deadline through ordinary runtime evaluation. It
may never rewrite source truth.

## 5. LIVE versus REPLAY truthfulness

The runtime mode the UI displays must be the mode that actually ran.

- **LIVE** means the run fetched the official source over the network during that run.
- **REPLAY** means the run deterministically replays a previously captured **real official
  source** interaction, preserving the original URL, the retrieval instant, the content hash
  and the exact excerpts.
- **FIXTURE** means owned synthetic content.

REPLAY is **not** FIXTURE. Captured real official evidence labelled `FIXTURE` would understate
the truth; labelled `LIVE` it would overstate it. Both are truthfulness defects.

```text
REPLAY_LABELLED_FIXTURE=PROHIBITED
REPLAY_LABELLED_LIVE=PROHIBITED
```

### Current execution reality

`RuntimeMode`, `RecordedProviders` (`src/qualor/runtime/replay.py`), the persistence CHECK
constraints and the generated schemas all already support `REPLAY`, and `RuntimeBoundary`
fails closed by refusing live providers in REPLAY. `SourceDocument` already retains
`original_url`, `final_url`, `retrieved_at`, `content_hash` and `authority`, which is
everything citation truth needs. The frontend renders the recorded mode string as data, so
`REPLAY` would surface in the Intelligence Rail and the decision context with **no frontend
change**.

The blocker is the ingestion boundary, not the runtime:

- `seed-workspace-fixture` is the **only** command that writes to `WorkspaceStore`;
- it validates through `DecisionFixture`, whose `mode` is pinned to `Literal["FIXTURE"]`, so a
  REPLAY workspace cannot be expressed;
- it applies `_rebased_observations`, so absolute official dates would be moved;
- `run-live-opportunity` prints its result and persists nothing to the workspace, so a LIVE
  run cannot reach the browser demo either.

```text
KILLER_DEMO_MODE_CANDIDATE=REPLAY
LIVE_SUPPORTED_TRUTHFULLY=NO
REPLAY_SUPPORTED_TRUTHFULLY=RUNTIME_ONLY
STATUS=BLOCKED_REAL_SOURCE_EXECUTION_CONTRACT
```

LIVE is additionally out of scope for the demo because it requires Bedrock model calls and
AgentCore search — **paid AWS calls** — and because its output never reaches the workspace the
browser reads.

### The smallest correction

A real-source ingestion path that persists a REPLAY workspace from captured official sources:

1. a REPLAY-capable workspace envelope, widening only the seeding envelope's pinned mode to
   admit `REPLAY` while continuing to refuse `LIVE`;
2. temporal rebasing made conditional — applied to owned FIXTURE scenarios, never to REPLAY,
   so official instants stay absolute.

No frontend change, no schema change, no new route, no new dependency, no AWS call.

## 6. No forced recommendation

The demo shows whatever the deterministic engines actually produce.

```text
FORCED_OUTCOME=NO
```

Decision policy is never edited to reach `APPLY`. If the truthful recommendation is `WATCH`,
the demo either shows `WATCH` or the **real readiness gaps are closed first** so that `APPLY`
becomes truthful on the merits.

### The current truthful result

A dry run of the deterministic stack against the real official facts and the audited real
project facts, on a temporary local database with zero AWS calls, produced:

```text
MODE=REPLAY
BEST_PROJECT=UNRESOLVED
ELIGIBILITY=REVIEW_REQUIRED
RECOMMENDATION=WATCH
STRATEGY=UNKNOWN
READINESS=UNKNOWN
CONFLICT=REVIEW_REQUIRED
CURRENT_APPLY_READY=NO
```

Reason codes: `ELIGIBILITY_MISSING_FACT`, `ELIGIBILITY_INCOMPLETE_COVERAGE`,
`ELIGIBILITY_UNVERIFIED_EVIDENCE`, `STRATEGY_SCORE_UNKNOWN`, `CONFLICT_REVIEW_REQUIRED`.
Explanation: *Matching does not identify a unique best project.*

This is the honest state of the product against its own real opportunity, and it is the
starting point the plan works from.

## 7. Two different kinds of gap

These must never be conflated.

**A. Demo project readiness gaps** — what stops QUALOR's deterministic stack from reaching a
truthful `APPLY` for itself. These are inputs the product needs.

**B. Final submission gaps** — what stops the actual Devpost entry from being complete. These
are competition deliverables.

A missing video is both: it is a genuine competition deliverable *and* a recorded
`MaterialReadiness` input. It must never be recorded as an already-completed project fact in
order to improve the demo.

```text
READINESS_FABRICATION=PROHIBITED
```

## 8. Real readiness gaps, as audited

Verified against the repository, git history and the authenticated GitHub API on 2026-09-12.

| Fact | Status | Authority |
| --- | --- | --- |
| Strands Agents used | VERIFIED | `pyproject.toml`; `src/qualor/runtime/agent.py` |
| Created during Submission Period | VERIFIED | first commit `bae6df2`, 2026-09-05 |
| MIT license present | VERIFIED | `LICENSE`; GitHub `licenseInfo.key = mit` |
| README present | VERIFIED | `README.md` |
| Testing instructions present | VERIFIED | `README.md`, "Local development" |
| **Public repository** | **NOT_READY** | visibility `PRIVATE`; anonymous fetch 404 |
| **Remote currency** | **NOT_READY** | `origin/main` 41 commits behind |
| **Architecture diagram** | **NOT_READY** | no diagram asset tracked |
| **Demo video** | **NOT_READY** | no video artifact or published URL |
| **Live demo** | **NOT_READY** | no deployment target |
| **Founder profile** | **NOT_READY** | residence, legal form, team size, hours, budget unrecorded |
| AWS Builder ID | UNKNOWN | owner-held account fact |
| Pre-existing code disclosure | UNKNOWN | no reuse disclosure recorded |
| AgentCore deployed | NOT_READY | provider exists; no deployment (and not required) |

## 9. Contract gaps found during preflight

Recorded because they constrain what the demo can truthfully assert, not as work to start now.

- **No `NOT_IN` operator.** `Operator` offers `EQ, IN, GTE, LTE, BETWEEN, DATE_BETWEEN,
  BOOL_IS, AND, OR`. The official eligibility section is an **exclusion** list of countries
  and territories. It cannot be faithfully encoded, and inventing an inclusion list would be
  fabrication, so no `GEOGRAPHY` rule was authored and the gap is reported instead.
- **`OpportunityRecord.edition` is a required non-empty string.** Neither official page
  publishes an edition label. `2026` is recorded as **derived** from the stated Submission
  Period, explicitly not quoted as a label.
- **`LEGAL_ENTITY` eligibility is a disjunction** (individuals, teams, or organizations) that
  `EQ` cannot express.

## 10. Professional Agents fit, source-grounded

The official track text is the left column; only capabilities proven by the repository appear
on the right.

| Official track requirement | QUALOR capability | Project evidence |
| --- | --- | --- |
| "makes someone dramatically better at the work they already do" | End-to-end opportunity evaluation producing a prepared application pack | `src/qualor/decisions/engine.py`; `src/qualor/workspace/`; `apps/web/src/features/draft-pack/` |
| "professionals, makers, creators, small-business owners" | Founder/entrant profile and portfolio matching | `src/qualor/domain/profiles.py`; portfolio matching in `decisions/` |
| "Target the repetitive, judgment-heavy tasks" | Deterministic eligibility, conflict, effort, readiness and strategy evaluation over evidence | `src/qualor/decisions/policy.py`; `src/qualor/conflicts/` |
| "Build a new AI agent with Strands Agents" | Strands information-planning agent with budgeted Bedrock calls | `src/qualor/runtime/agent.py` |
| "handle it end to end, not just chat about it" | Discovery through approval to a persisted Draft Pack | `src/qualor/workspace/service.py`; browser judge flow in `apps/web/e2e/workspace.spec.ts` |
| "Design: a complete, coherent product experience" | The accepted QUALOR-04B judge experience | `a2f92d9`, 04B acceptance record |

Evidence verification and the human approval boundary are additionally proven by
`src/qualor/domain/evidence.py` and `src/qualor/workspace/` approval authority.

## 11. Functional demo story contract

Narration is not written here. This is the functional sequence only.

- **ACT 1 — PROBLEM.** Professionals lose time discovering and evaluating opportunities.
- **ACT 2 — AGENT WORK.** QUALOR evaluates the real Agents for Humans opportunity.
- **ACT 3 — JUDGMENT.** QUALOR determines whether QUALOR itself is the right project to pursue.
- **ACT 4 — PROOF.** The judge sees exact official-rule evidence with its citation.
- **ACT 5 — HUMAN CONTROL.** QUALOR stops before consequential preparation.
- **ACT 6 — PAYOFF.** The human approves and QUALOR prepares the Application Pack.

## 12. W01 is excluded from the final demo

`W01_DECISION_TO_DRAFT_PACK` remains the owned acceptance fixture for tests and regression. It
is **not** the public final competition demo and must not appear as one.

```text
W01_IN_PUBLIC_FINAL_DEMO=NO
W01_AS_TEST_FIXTURE=RETAINED
```

The 04B browser acceptance keeps using W01 unchanged. Nothing in this work weakens it.

## 13. Frozen surfaces

This work changes no QUALOR-04B production presentation code. The accepted judge experience at
`a2f92d9` is the surface the real-source demo runs through.

```text
BACKEND_SCOPE_MINIMAL=YES
SUBMISSION_SCOPE_MINIMAL=YES
FRONTEND_CHANGE=NONE_EXPECTED
SCHEMA_CHANGE=NO
MIGRATION_CHANGE=NO
SECURITY_BOUNDARY_CHANGE=NO
NEW_DEPENDENCY=NO
AWS_PAID_CALLS=0
```

## 14. Self-review record

```text
PLACEHOLDERS=0
TBD=0
TODO=0
SOURCE_AUTHORITY_AMBIGUITY=0
FORCED_OUTCOME=NO
FIXTURE_LEAK=NO
FAKE_LIVE=NO
TEMPORAL_REBASE=NO
EXCERPTS_VERBATIM_VERIFIED=29/29
OFFICIAL_SOURCE_COUNT=2
CURRENT_APPLY_READY=NO
KILLER_DEMO_MODE_CANDIDATE=REPLAY
RAW_SOURCE_COMMITTED=NO
IMPLEMENTATION_AUTHORIZED=NO
```
