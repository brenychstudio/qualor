# QUALOR Real-Source Killer Demo Implementation Plan

> **For agentic workers:** execute ONE task per run. Stop after each task and return a Result
> Packet. The owner decides PASS, FIX or REVERT before the next task begins.

**Goal:** replace the synthetic W01 demo with a truthful real-source demo in which QUALOR
evaluates the real Agents for Humans Hackathon and decides whether QUALOR itself should be
entered in the Professional Agents track.

**Spec:** `docs/superpowers/specs/2026-09-12-qualor-killer-demo-real-source-design.md`

**Base:** `feature/qualor-killer-demo-real-source` from
`a2f92d9ab35815167c38f9b687c52de94465343f`.

**Tech stack:** existing only. No new dependency, no new route, no schema change, no
migration, no AWS call.

## Deadline reality

The official Submission Period closes **Monday, September 14, 2026, 5:00 pm Pacific Time**
(`2026-09-15T00:00:00Z`). This plan was written 2026-09-12. Roughly **two days** remain.

Task ordering is therefore by *unblocking value*, and Task 2 is deliberately sequenced so the
single cheapest competition-critical action — making the repository public — happens early
rather than last.

## Preflight facts this plan depends on

Verified during preparation, not assumed:

- `REPLAY` is already supported by `RuntimeMode`, `RecordedProviders`, the persistence CHECK
  constraints, the generated schemas and `DecisionInput`. `SourceDocument` already preserves
  `original_url`, `final_url`, `retrieved_at`, `content_hash` and `authority`.
- The frontend renders the recorded mode as data, so `REPLAY` surfaces with **no frontend
  change**. The only hardcoded `'FIXTURE'` in `apps/web/src` is the D02 design-preview label.
- `seed-workspace-fixture` is the only writer to `WorkspaceStore`. It pins
  `DecisionFixture.mode` to `FIXTURE` and applies `_rebased_observations`.
- `run-live-opportunity` persists nothing to the workspace.
- The truthful dry-run result today is `WATCH` / `ELIGIBILITY=REVIEW_REQUIRED` /
  `BEST_PROJECT=UNRESOLVED`.

## Rules binding every task

```text
FORCED_OUTCOME=NO
TEMPORAL_REBASE_FOR_REAL_SOURCE=PROHIBITED
REPLAY_LABELLED_FIXTURE=PROHIBITED
REPLAY_LABELLED_LIVE=PROHIBITED
READINESS_FABRICATION=PROHIBITED
RAW_SOURCE_COMMITTED=NO
AWS_PAID_CALLS=0
W01_TEST_FIXTURE=UNCHANGED
04B_PRESENTATION_CODE=FROZEN
```

No task may edit decision policy to reach a nicer recommendation. No task may record a
readiness material as ready because it is intended to be finished later.

---

## Task 1: REPLAY workspace ingestion

**The blocker.** Without this there is no path from real captured official source into the
browser demo at all.

**Files:**

- Modify: `src/qualor/domain/fixture.py` — admit `REPLAY` in the seeding envelope
- Modify: `src/qualor/decisions/fixture.py` — admit `REPLAY` in the seeding envelope
- Modify: `src/qualor/cli.py` — make `_rebased_observations` conditional on mode
- Add: tests covering both modes

`LIVE` stays refused by the seeding envelope. That boundary is not relaxed.

- [ ] RED: a test asserting a REPLAY envelope seeds a workspace whose recorded mode is
      `REPLAY`, and a test asserting REPLAY observations are **not** rebased — the official
      deadline instant read back from the store equals the instant in the envelope.
- [ ] Keep the existing FIXTURE behaviour green, rebase included: the W01 acceptance path is
      unchanged.
- [ ] Keep `LIVE` refused by the seeding envelope, with a test.
- [ ] Confirm no schema regeneration is required; if drift appears, STOP and report.
- [ ] Full verification; independent review; one commit.
- [ ] **STOP.**

**Acceptance:** a REPLAY workspace persists, reads back `REPLAY`, and its official temporal
facts are byte-identical to the source instants.

---

## Task 2: Real entrant and project facts, and the public repository

Two things the product cannot proceed without, and the cheapest competition-critical action.

**Owner-supplied inputs required before this task can complete** — these are facts, not
decisions, and nothing may be invented in their place:

- country of residence, legal form, team size, available hours to the deadline, cash
  commitment;
- AWS Builder ID status;
- whether any pre-existing code or work is incorporated and must be disclosed.

- [ ] Make `github.com/brenychstudio/qualor` **public** and push the current branch. The
      repository is presently `PRIVATE` and `origin/main` is 41 commits behind. This is a
      submission requirement in its own right and it closes the `PUBLIC_AVAILABILITY`
      readiness material honestly.
- [ ] Record the real founder profile and the real QUALOR project profile as owned local
      input, with `DOCUMENTED` provenance only where an authority genuinely exists and
      `UNKNOWN` everywhere else.
- [ ] Normalize the official opportunity from the captured sources: every rule carries its
      verbatim excerpt, verified character-for-character before use.
- [ ] Record the `NOT_IN` operator gap rather than working around it: no `GEOGRAPHY` rule is
      authored from an invented inclusion list. If geography must be gated, that is a
      contract change and it STOPS for owner decision.
- [ ] Re-run the dry run and record the actual result.
- [ ] **STOP.** Report the new truthful recommendation.

**Acceptance:** the repository is public; the dry run runs against real recorded facts; the
recommendation is whatever the engines produce.

---

## Task 3: Close the real submission readiness gaps

These are simultaneously competition deliverables and `MaterialReadiness` inputs. They are
recorded as ready only once they actually exist.

- [ ] Architecture diagram — required by the Official Rules and currently absent (no diagram
      asset is tracked).
- [ ] Demonstration video, maximum 5 minutes, public on YouTube or Vimeo, covering the working
      project plus the problem, the audience and why it matters.
- [ ] Devpost text description and pitch narrative.
- [ ] Update `material_readiness` to match reality after each artifact exists, never before.
- [ ] Re-run the dry run; record the actual recommendation.
- [ ] **STOP.**

**Acceptance:** every readiness material recorded `ready` is independently verifiable. If the
recommendation is still not `APPLY`, that is reported, not engineered away.

**Note on the outcome:** `APPLY` is not a requirement of this plan. A truthful `PREPARE` with
named, source-grounded gaps is a legitimate and arguably stronger demo — it shows judgment
rather than a rubber stamp. The spec forbids forcing the result either way.

---

## Task 4: The canonical real-source REPLAY run

- [ ] Seed the REPLAY workspace from the captured official sources through the Task 1 path.
- [ ] Confirm in the browser that the Intelligence Rail and the decision context read
      `REPLAY` — never `FIXTURE`, never `LIVE`.
- [ ] Confirm the Evidence Reader shows the exact official excerpt with its
      `agentsforhumans.devpost.com` citation and the real retrieval instant.
- [ ] Confirm the displayed deadline equals `2026-09-15T00:00:00Z` and agrees with the quoted
      Submission Period text.
- [ ] Capture the canonical sequence at 1440 × 810 into `.qualor/local/killer-demo/`.
- [ ] **STOP.** Owner review of the sequence.

**Acceptance:** `STRUCTURED_FACT == SOURCE_EVIDENCE` holds for every displayed fact, verified
against the rendered page rather than asserted.

---

## Task 5: Killer-demo acceptance

- [ ] Extend the browser acceptance with the real-source guarantees only: mode reads `REPLAY`,
      the citation host is the official one, and the displayed deadline matches the source
      instant. Do not duplicate the 04B judge flow.
- [ ] Keep the W01 acceptance suite passing unchanged.
- [ ] Full verification once; independent review; one commit.
- [ ] **STOP.**

**Acceptance:** `CRITICAL=0`, `IMPORTANT=0`, full verification green, W01 unchanged.

---

## Deliberately not in this plan

The optional `builder.aws` blog bonus (up to 0.6 points) is recorded as available and is
**scheduled separately** after the demo path is safe. A live demo deployment and an AgentCore
deployment both strengthen the Technical Implementation score but neither is required; they
are out of scope unless time remains after Task 5.

## Plan self-review

```text
PLACEHOLDERS=0
TBD=0
TODO=0
SOURCE_AUTHORITY_AMBIGUITY=0
FORCED_OUTCOME=NO
FIXTURE_LEAK=NO
FAKE_LIVE=NO
TEMPORAL_REBASE=NO
BACKEND_SCOPE_MINIMAL=YES
SUBMISSION_SCOPE_MINIMAL=YES
TASK_COUNT=5
FRONTEND_CHANGE=NONE_EXPECTED
SCHEMA_CHANGE=NO
NEW_DEPENDENCY=NO
AWS_PAID_CALLS=0
IMPLEMENTATION_AUTHORIZED=NO
```
