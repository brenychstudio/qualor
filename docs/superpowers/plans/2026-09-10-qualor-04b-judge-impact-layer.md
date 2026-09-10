# QUALOR-04B Judge Impact Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.
> **Execute ONE task per run. Stop after each task and return a Result Packet
> plus visual evidence. The owner/controller decides PASS, FIX or REVERT before
> the next task begins.**

**Goal:** Make QUALOR's existing sophistication legible to a competition judge. After the
final submission it should be hard to justify placing QUALOR below Top-3 Professional
Agents. Primary target: Professional Agents Gold. Secondary maximum: Grand Prize.

**Architecture:** No architectural change. QUALOR-04A is frozen at
`e18df659129791c17f427fb935a7c19c5ae960b1`. This plan adds one scoped presentation layer
over the accepted A1.2 implementation and changes nothing else.

**Tech Stack:** Existing only — React, TypeScript, Vite, Tailwind v4, Vitest, Playwright,
the three current stylesheets. No new runtime dependency, and specifically no animation
library.

**Spec:**
`docs/superpowers/specs/2026-09-10-qualor-04b-judge-impact-layer-design.md`

## Sources and repository facts

This plan was written against the tree at
`92e91589255b47586db45e824f33e7c64a715212`, not from memory. The facts below were verified
in that tree and every task depends on them.

- Stylesheets load from `apps/web/src/index.css` in this order: `tailwindcss`,
  `styles/tokens.css`, `styles/base.css`, `styles/propagation.css`. Later files win at
  equal specificity.
- `WorkspaceFrame` is a **named export of** `apps/web/src/layout/WorkspaceShell.tsx`
  (line 34), not a separate file. It owns the body grid and is shared by the product shell
  and the frozen D02 optical preview.
- `WorkspaceFrame` renders the root element as
  `workspace [workspace--optical-preview] [reduce-motion] [proof-is-open]`. The
  `workspace--optical-preview` class is present **only** for the frozen frame.
- `propagation.css` already uses `.workspace:not(.workspace--optical-preview)` as its guard.
  Of its 70 rule lines, 61 carry that guard; the 9 that do not are Portfolio-only
  (`.portfolio-*`, `.profile-*`, `.dossier-*`) and lie outside the frozen decision frame.
- `base.css` and `tokens.css` carry **no** optical-preview guard. Any rule there reaches the
  frozen frame.
- The frozen D02 frame is `opticalPreview = calibrationFrame && selected === 0 && !view` in
  `dev/DecisionPreview.tsx`, i.e. the **decision** view of scenario 0 at 1440 × 810. Its
  SHA-256 is recorded in
  `docs/superpowers/specs/2026-09-09-qualor-a1-2-visual-baseline-freeze.md`.
- Classes the frozen frame renders, and which therefore sit in the blast radius when edited
  in `base.css`/`tokens.css`: `.workspace-grid`, `.zone-heading`, `.scenario-queue`,
  `.opportunity-row`, `.opportunity-row--selected`, `.queue-item-index`, `.queue-organizer`,
  `.queue-decision-axis`, `.queue-footnote`, `.decision-composition`,
  `.decision-convergence`, `.recommendation-surface`, `.recommendation-rule`,
  `.recommendation-strategy`, `.signal-bar`, `.signal-lane`, `.next-actions`,
  `.section-rule`, `.proof-peek`, `.proof-document-section`, `.rail-section`, `.event-axis`.
- Classes the frozen frame does **not** render: `.evidence-plane` (the invoked plane is
  closed in a static capture), and every `ApprovalPanel` and `ApplicationPack` class — the
  preview renders neither component.
- `dev/decision-optical.css` applies only under `.workspace--optical-preview` inside
  `@media (min-width: 1280px)`; it is FIX2.1 micro-polish owned by the preview.
- `.workspace-grid--four-zone` is applied in `WorkspaceShell.tsx` but has **zero** matching
  CSS rules anywhere. It is currently an unused hook, and it is applied to the preview too,
  so it does not scope the frozen frame away. Do not treat it as a scoping mechanism.
- The browser acceptance asserts FIXTURE truthfulness through
  `getByLabel('Current decision state')` containing `FIXTURE` and not `LIVE`, plus a
  body-wide absence of `Bedrock|AgentCore`. The header chip reads `LOCAL` in the real
  product and `FIXTURE` only under a preview label, so **do not** rewire the FIXTURE
  assertion to the header.
- `.qualor/` is gitignored (`.gitignore` line 12) and is the established location for local
  visual QA evidence. Screenshots are never committed.
- Reduced motion is handled twice: a global `@media (prefers-reduced-motion: reduce)` block
  and a `.reduce-motion` class block, both of which disable all animation and transition.
- The accessibility suite (`apps/web/src/a11y/accessibility.test.tsx`) and the browser
  acceptance (`apps/web/e2e/workspace.spec.ts`) are the arbiters. Neither may be relaxed.

## Where 04B rules live

```text
WHERE_04B_RULES_LIVE=apps/web/src/styles/judge-impact.css
```

Task 1 creates `apps/web/src/styles/judge-impact.css` and appends one import to
`apps/web/src/index.css` after `propagation.css`. Every workspace-affecting rule in it is
prefixed `.workspace:not(.workspace--optical-preview)`, copying the guard convention
`propagation.css` already proves.

Why a dedicated layer rather than the alternatives:

- **Not `base.css`** — it is the shared foundation and reaches the frozen frame, so every
  edit there would be `OPTICAL_FRAME_BLAST_RADIUS=YES`.
- **Not `tokens.css`** — same reach, and the spec forbids broad token redesign.
- **Not `propagation.css`** — it carries its own recorded meaning ("A1.2 field / anchor /
  plane propagation"). Mixing 04B judge polish into it would blur two separate accepted
  records and make either one hard to revert alone.
- **A dedicated layer** keeps 04B diffable, revertable per task, and
  `OPTICAL_FRAME_BLAST_RADIUS=NO` by construction, while sitting last in the cascade so it
  can refine without `!important`.

One documented exception: `ApprovalPanel` and `ApplicationPack` classes are not rendered by
the D02 preview at all, so Task 4 may edit their existing rules in `base.css` where that is
genuinely cleaner than a scoped override. That remains `OPTICAL_FRAME_BLAST_RADIUS=NO`
because the frozen frame does not render those classes — the task must state this
explicitly rather than assume it.

## Optical frame safety protocol

Every task below declares `OPTICAL_FRAME_BLAST_RADIUS`. All five are planned as `NO` by
construction.

A task **must not** silently change its classification. If an executor concludes that the
approved judge impact genuinely cannot be achieved inside the scoped layer — because it
requires changing `WorkspaceFrame` markup, a `base.css` rule the frozen frame inherits, or
a `tokens.css` value the frozen frame consumes — then it must **stop before making that
change** and escalate. Do not contort the implementation into something worse merely to stay
at `NO`; escalate honestly instead.

When the owner authorises crossing the boundary, that task performs all six steps:

1. capture the pre-change 1440 × 810 D02 frame and confirm it still matches the recorded
   A1.2 SHA-256;
2. state in writing why crossing the boundary is worth the judge impact;
3. capture the post-change 1440 × 810 D02 frame;
4. compare it against the frozen A1.2 frame and describe every visible difference;
5. obtain explicit owner/controller visual acceptance;
6. only then record the new accepted frame and its SHA-256, amending
   `docs/superpowers/specs/2026-09-09-qualor-a1-2-visual-baseline-freeze.md` through the
   approved documentation process.

A stale recorded hash is a truthfulness defect. Never leave the recorded value describing a
frame that no longer renders.

## Visual review gates

Visual acceptance is a first-class gate. **No task may claim visual acceptance from unit
tests alone.**

Captures use the existing Playwright stack against the real local W01 flow — the same
`apps/web/playwright.config.ts` webServer pair that already seeds W01 through the production
workspace services. Captures are written to `.qualor/local/04b-taskN/` (gitignored) and are
never committed. Adding a capture script is a local development affordance, not a product
feature; it must not ship a route, a component, or a dependency.

| Task | Required canonical capture at 1440 × 810 |
| --- | --- |
| 1 | W01 selected Decision view |
| 2 | W01 with the Evidence Plane open, plus the reduced-motion equivalent |
| 3 | W01 populated Intelligence Rail |
| 4 | `PENDING_APPROVAL` state, and the finished Application Pack |
| 5 | The complete judge sequence, plus 1280 / 1024 / 768 / 320 regression frames |

## Quality bar — the Top-3 / Gold rule

A change is **not accepted merely because it is visually nicer.** To enter or stay in this
plan a change must materially improve at least one of:

- time-to-understand the recommendation;
- evidence comprehension;
- autonomous-agent comprehension;
- human-control comprehension;
- premium product credibility;
- end-to-end presentation clarity;

while preserving every frozen authority and accessibility contract.

If a task's `WHY_THIS_CAN_MOVE_JUDGE_SCORE` reads as weak or speculative when the executor
reaches it, the correct action is to **drop that change and report it**, not to implement it
anyway. 04B does not fake additional technical sophistication; it makes existing
sophistication legible.

Desired final impression: this is not a hackathon dashboard. It is a coherent, credible
decision-intelligence product whose autonomous agent work, deterministic judgment, evidence,
and human-control boundaries are immediately understandable.

## Frozen contracts binding every task

```text
BACKEND_CHANGE=NO
PUBLIC_API_CHANGE=NO
SCHEMA_CHANGE=NO
MIGRATION_CHANGE=NO
SECURITY_BOUNDARY_CHANGE=NO
NEW_RUNTIME_DEPENDENCY=NO
ANIMATION_LIBRARY=NO
ZONE_COUNT=4
```

No task may weaken `UNKNOWN != PASS`, the strategy/probability boundary, deterministic
recommendation, eligibility or priority authority, `presentation_state`, `ProductState`,
`ActionCapability`, run-state authority, LIVE/FIXTURE/REPLAY truthfulness, evidence and
provenance authority, version-bound approval, action-token handling, idempotency, Draft Pack
immutability, or the prohibition on external submission. No task may duplicate server policy
in React. If a desired visual behaviour requires backend work, the behaviour is dropped or
deferred — polish does not become a backend project.

Excluded from 04B entirely, and not to be started by any task here: `?technical=true` query
support, in-flight run persistence, Draft Pack `source_citations` contract work, DraftPack
key-union tightening, normalizer expansion, and `NO_RESULTS` local-filter architecture.

## Delivery order and review rule

Execute the five tasks in order, one per run. Each task that changes behaviour uses
RED → GREEN → REFACTOR, ends with independent review, fixes Critical and Important findings
before commit, and produces one coherent commit. **No task automatically starts the next
one.** Before every commit run `git diff --check`; every task ends with the full 04A
verification.

---

## Task 1: Selection and Decision Hierarchy

**Judge goal:** within roughly 5 seconds a first-time viewer identifies the selected
opportunity, the recommendation, the primary reason, and the primary next action.

Judge moments 01 and 02 are implemented together because they are one visual hierarchy
system: making the Inbox quieter is what makes the Decision hero dominant, and doing either
alone risks an unbalanced frame.

```text
OPTICAL_FRAME_BLAST_RADIUS=NO
JUDGE_CRITERIA_IMPACT=Design, Presentation, Potential Impact comprehension
```

**WHY_THIS_CAN_MOVE_JUDGE_SCORE:** the first populated frame is the only one every judge
certainly sees. If the recommendation, its reason and its action resolve instantly, every
later moment is read as confirmation; if the Inbox competes with the canvas, the judge
spends the opening seconds parsing layout instead of understanding the product.

**Files:**

- Create: `apps/web/src/styles/judge-impact.css`
- Modify: `apps/web/src/index.css` (one import line, after `propagation.css`)
- Modify: `apps/web/src/features/inbox/OpportunityRow.tsx` *only if a class hook is missing*
- Modify: `apps/web/src/features/decision/DecisionCanvas.tsx` *only if a class hook is
  missing*
- Test: `apps/web/src/layout/WorkspaceShell.test.tsx` (extend, never relax)
- Test: `apps/web/src/features/decision/DecisionCanvas.test.tsx` (extend)

Do **not** modify `WorkspaceShell.tsx`, `base.css` or `tokens.css` in this task. If a needed
class hook genuinely does not exist, adding one to a feature component is permitted; adding
markup to `WorkspaceFrame` is an escalation.

**Interfaces:**

- Consumes: the existing `InboxItem` fields already rendered, including
  `presentation_state`, and the existing `DecisionCanvas` view model.
- Produces: no new props, no new data, no new component.

The Inbox becomes quieter and more scannable; the selected row becomes unmistakable without
becoming decorative. The Decision Canvas recommendation becomes the dominant hero, and
reason, Strategy, the four core facts and the primary action gain a clearer reading order.
`priority_rank` is never rendered as a score, ordering stays the server's
`QUALOR_INBOX_PRIORITY_CONTRACT_V1` total order, and no ranking logic moves into React. No
gauge, no radar chart, no probability language, no new metric.

**Motion:**

| Field | Value |
| --- | --- |
| `TRIGGER` | selected opportunity changes (React state change already rendered) |
| `PROPERTY` | opacity, and a restrained translate on the recommendation block |
| `DURATION` | 420 ms |
| `EASING` | existing `--motion-easing` |
| `REDUCED_MOTION_BEHAVIOR` | immediate final state; both existing reduced-motion paths already suppress it, and the test asserts the content is identical |
| `JUDGE_COMPREHENSION_PURPOSE` | marks that the decision was *resolved for this selection*, so the canvas reads as a response to the click rather than a static panel |

No other motion is authorised in this task.

- [ ] Write RED tests asserting the selected row is distinguishable by an accessible,
      non-colour-only means; that the Decision Canvas reading order is recommendation →
      reason → strategy → four facts → primary action; that `priority_rank` never renders as
      a number; and that reduced motion yields identical text content. Confirm they fail.
- [ ] Run `npm --prefix apps/web run test:run -- WorkspaceShell DecisionCanvas` and confirm
      the expected failure.
- [ ] Create `judge-impact.css` with every rule prefixed
      `.workspace:not(.workspace--optical-preview)`, add the single import to `index.css`,
      and implement the hierarchy refinement.
- [ ] Run focused tests and confirm PASS.
- [ ] Refactor repeated values into local custom properties **inside** `judge-impact.css`.
      Do not add or alter a token in `tokens.css`.
- [ ] Capture the W01 selected Decision view at 1440 × 810 into `.qualor/local/04b-task1/`.
- [ ] Capture the D02 frame at 1440 × 810 and confirm it still matches the recorded A1.2
      SHA-256, proving `OPTICAL_FRAME_BLAST_RADIUS=NO` rather than asserting it.
- [ ] Run all web tests, the accessibility suite, typecheck, build, the browser acceptance,
      and `./scripts/verify.ps1`.
- [ ] Independent review; fix Critical and Important findings.
- [ ] Commit as `feat: sharpen selection and decision hierarchy`.
- [ ] **STOP.** Return the Result Packet with the two captures. Await owner PASS/FIX/REVERT.

---

## Task 2: Decision-to-Proof Signature Transition

**Judge goal:** without explanation the viewer understands *this is QUALOR's decision*,
*this is why*, *this is the official proof*. This is the highest visual-impact bar in 04B.

```text
OPTICAL_FRAME_BLAST_RADIUS=NO
JUDGE_CRITERIA_IMPACT=Design, Presentation, Creativity & Originality, Technical Implementation comprehension
```

**WHY_THIS_CAN_MOVE_JUDGE_SCORE:** source-grounded proof is QUALOR's genuine differentiator
against a plausible-sounding LLM wrapper. A judge who watches the dark workspace recede and
a document-material evidence plane take authority — carrying an exact excerpt and a real
citation — has seen the claim demonstrated rather than asserted.

**Files:**

- Modify: `apps/web/src/styles/judge-impact.css`
- Modify: `apps/web/src/features/evidence/EvidenceSheet.tsx` *only if a class hook is
  missing*
- Modify: `apps/web/src/features/evidence/EvidenceClaim.tsx` *only if a class hook is
  missing*
- Test: `apps/web/src/features/evidence/EvidenceSheet.test.tsx` (extend)
- Test: `apps/web/src/a11y/accessibility.test.tsx` — **read only; never edited**

`.evidence-plane` is not rendered in the frozen D02 static frame, and `.proof-peek` /
`.proof-context` are — so proof-zone refinement stays inside the scoped layer while the
plane itself may be refined more freely, still within `judge-impact.css` for consistency.

**Interfaces:**

- Consumes: the existing `EvidenceSheetView`, its section groups, exact excerpts, citation
  URLs, freshness, and the five evidence states.
- Produces: no new props, no new data, no change to the technical-provenance contract.

Refine workspace recession while the plane is open, the plane's material authority, source
excerpt hierarchy, citation visibility, transition pacing, and the visual separation between
QUALOR's interpretation of a claim and the exact source text. Evidence data, exact excerpt
text, the original URL, the focus trap, Escape, focus return, and the narrow-viewport scroll
lock are all untouched.

**Motion:**

| Field | Value |
| --- | --- |
| `TRIGGER` | `proofOpen` becomes true, i.e. `Why this decision` activated |
| `PROPERTY` | plane opacity and translate (extending the existing `plane-enter` keyframe); workspace recession via opacity on `.proof-is-open .workspace-canvas` / `.workspace-rail`, which already exists |
| `DURATION` | 520 ms plane entry; 300 ms workspace recession, starting together so the recession reads as cause, not lag |
| `EASING` | existing `--motion-easing` |
| `REDUCED_MOTION_BEHAVIOR` | plane appears in final position immediately, recession applied without transition; every state and action identical, asserted by test |
| `JUDGE_COMPREHENSION_PURPOSE` | the dark surface yielding to the document *is* the argument that judgment is subordinate to evidence; a cut would state it, the transition demonstrates it |

- [ ] Write RED tests for the open/closed proof states asserting exact excerpt preservation,
      citation target and safe link attributes, all five evidence states, and that focus
      trap, Escape and focus return still behave. Add a reduced-motion assertion that the
      plane's content and actions are identical.
- [ ] Run `npm --prefix apps/web run test:run -- EvidenceSheet accessibility` and confirm the
      expected failure and that accessibility currently passes unmodified.
- [ ] Implement the transition entirely in `judge-impact.css`, extending the existing
      `plane-enter` behaviour rather than replacing it.
- [ ] Run focused tests and confirm PASS. Run the accessibility suite **unmodified** and
      confirm PASS.
- [ ] Capture W01 with the Evidence Plane open at 1440 × 810, and a reduced-motion
      equivalent, into `.qualor/local/04b-task2/`.
- [ ] Capture the D02 frame and confirm the recorded A1.2 SHA-256 still matches.
- [ ] Run all web tests, typecheck, build, the browser acceptance, and `./scripts/verify.ps1`.
- [ ] Independent review; fix Critical and Important findings.
- [ ] Commit as `feat: strengthen the decision-to-proof transition`.
- [ ] **STOP.** Return the Result Packet with both captures. Await owner PASS/FIX/REVERT.

---

## Task 3: Truthful Intelligence Presence

**Judge goal:** the judge sees that QUALOR actually performed structured agent work, rather
than displaying a static result.

```text
OPTICAL_FRAME_BLAST_RADIUS=NO
JUDGE_CRITERIA_IMPACT=Technical Implementation comprehension, Presentation
```

**WHY_THIS_CAN_MOVE_JUDGE_SCORE:** the autonomous work already happened and is already
persisted as `RunRecord` and `RunEvent`. Today it reads as a flat list, so a judge can miss
that discovery, source location, verification and evaluation were distinct bounded steps.
Making the causal chain legible converts existing engineering into visible engineering — the
one thing 04B can do for the Technical Implementation criterion without faking anything.

**Files:**

- Modify: `apps/web/src/styles/judge-impact.css`
- Modify: `apps/web/src/features/activity/IntelligenceRail.tsx` *only if a class hook is
  missing*
- Test: `apps/web/src/features/activity/IntelligenceRail.test.tsx` (extend)
- Test: `apps/web/e2e/workspace.spec.ts` (extend the FIXTURE assertion only)

**Interfaces:**

- Consumes: persisted `RunRecord`/`RunEvent` and the existing presenter output.
- Produces: no new event type, no new field, no client-side inference.

Refine event hierarchy, rhythm, causal readability, phase and mode legibility, and the
visual relation between recorded events and the current decision. `.rail-section` and
`.event-axis` are rendered by the frozen frame, so all of this stays in the scoped layer.

**Truthfulness is the hard constraint.** Never invent a LIVE state, a running timer,
progress, a model call, a search, a verification, or any AWS/Bedrock/AgentCore activity.
Motion may occur **only** from an actual rendered event or state change — never from a
timer, and never to fill a quiet rail. No chat UI. In-flight run persistence stays deferred.

**Motion:**

| Field | Value |
| --- | --- |
| `TRIGGER` | the rendered event list changes, or the selected decision changes |
| `PROPERTY` | opacity on newly rendered event rows only |
| `DURATION` | 260 ms |
| `EASING` | existing `--motion-easing` |
| `REDUCED_MOTION_BEHAVIOR` | rows appear immediately; identical content and order |
| `JUDGE_COMPREHENSION_PURPOSE` | distinguishes *a new recorded observation arrived* from *the list re-rendered*; deliberately short, because anything longer would start to imply ongoing work |

No timer-driven motion is authorised. If the rail is static because the run is complete, it
looks static — that is the truthful result.

- [ ] Write RED tests for event order, phase and mode legibility, degraded states
      (`BUDGET_STOPPED`, `PARTIAL`, `FAILED`, disconnected provider), and no chat vocabulary.
- [ ] Write the explicit RED test that **polish cannot hide FIXTURE mode**: with the rail
      refinement applied, `Current decision state` still contains `FIXTURE`, never `LIVE`,
      and the body still contains no `Bedrock|AgentCore`. Extend the existing browser
      assertion rather than relocating it to the header, which reads `LOCAL` in the real
      product.
- [ ] Run `npm --prefix apps/web run test:run -- IntelligenceRail` and confirm the expected
      failure.
- [ ] Implement in `judge-impact.css`, adding a class hook only if one is genuinely missing.
- [ ] Run focused tests and confirm PASS.
- [ ] Capture the W01 populated Intelligence Rail at 1440 × 810 into `.qualor/local/04b-task3/`.
- [ ] Capture the D02 frame and confirm the recorded A1.2 SHA-256 still matches.
- [ ] Run all web tests, the accessibility suite, typecheck, build, the browser acceptance,
      and `./scripts/verify.ps1`.
- [ ] Independent review; fix Critical and Important findings. Reject any change that could
      let a viewer read recorded fixture history as live work.
- [ ] Commit as `feat: make recorded agent work legible`.
- [ ] **STOP.** Return the Result Packet with the capture. Await owner PASS/FIX/REVERT.

---

## Task 4: Approval and Preparation Payoff

**Judge goal:** the consequential transition — machine recommendation, then deliberate human
confirmation, then a prepared document — reads as controlled, premium and safe.

Judge moments 05 and 06 are implemented together because they are one transition; splitting
them would review the approval without its payoff.

```text
OPTICAL_FRAME_BLAST_RADIUS=NO
JUDGE_CRITERIA_IMPACT=Design, Presentation, Potential Impact comprehension
```

**WHY_THIS_CAN_MOVE_JUDGE_SCORE:** an autonomous-agent judge is trained to look for where
the human stays in control and whether the system can act unilaterally. QUALOR's answer is
already strong — version-bound, expiring, one-time approval and no external submission — but
it currently reads as a form. Making the boundary feel deliberate turns a safety property
into a visible product virtue, and the finished pack gives the demo an ending.

**Files:**

- Modify: `apps/web/src/styles/judge-impact.css`
- Modify: `apps/web/src/styles/base.css` — **permitted only** for existing `.approval-*`,
  `.pack-*` and `.document-*` rules, which the D02 preview does not render. The task must
  state this exemption explicitly and verify the D02 hash afterwards regardless.
- Modify: `apps/web/src/features/approval/ApprovalPanel.tsx` *only if a class hook is
  missing*
- Modify: `apps/web/src/features/draft-pack/ApplicationPack.tsx` *only if a class hook is
  missing*
- Test: `apps/web/src/features/approval/ApprovalPanel.test.tsx` (extend)
- Test: `apps/web/src/features/draft-pack/ApplicationPack.test.tsx` (extend)

**Interfaces:**

- Consumes: the existing approval view model with its bindings, expiry and reason codes, and
  the existing `DraftPack` with its seven server-ordered sections.
- Produces: no new action, no new state, no new field.

Approval should read as controlled, consequential, premium, calm and version-bound; the
Application Pack as finished, editorial, reviewable, and materially distinct from the dark
workspace. Approval state and validity, action-token handling, idempotency, the absence of
external submission, the seven sections in server order, immutability, missing-field truth,
and the draft-versus-evidence distinction are all preserved exactly. No editor, no autosave,
no submit button, and no submit or send vocabulary anywhere.

**Motion:**

| Field | Value |
| --- | --- |
| `TRIGGER` | approval state transitions to `PENDING_APPROVAL`, and later to `DRAFT_READY` |
| `PROPERTY` | opacity and a restrained material/tonal transition into the light document |
| `DURATION` | 600 ms on the pack entry; 320 ms on the approval state change |
| `EASING` | existing `--motion-easing` |
| `REDUCED_MOTION_BEHAVIOR` | both states render immediately in final form; every control remains reachable and identically named |
| `JUDGE_COMPREHENSION_PURPOSE` | the dark-to-light material shift is the product's own punctuation for *the human authorised this and preparation began*; without it the pack looks like another screen |

- [ ] Write RED tests asserting the approval surface names the action, the bound versions and
      the expiry; that confirmation remains reachable and keyboard-operable; that no
      submit/send vocabulary appears; that the pack renders exactly seven sections in server
      order; and that missing fields stay visible.
- [ ] Run `npm --prefix apps/web run test:run -- ApprovalPanel ApplicationPack` and confirm
      the expected failure.
- [ ] Implement, preferring `judge-impact.css` and using the `base.css` exemption only where
      it is genuinely cleaner.
- [ ] Run focused tests and confirm PASS.
- [ ] Capture the `PENDING_APPROVAL` state and the finished Application Pack at 1440 × 810
      into `.qualor/local/04b-task4/`.
- [ ] Capture the D02 frame and confirm the recorded A1.2 SHA-256 still matches, proving the
      `base.css` exemption did not reach the frozen frame.
- [ ] Run all web tests, the accessibility suite, typecheck, build, the browser acceptance
      including direct pack reload, and `./scripts/verify.ps1`.
- [ ] Independent review; fix Critical and Important findings. Reject any change that softens
      the approval boundary or implies submission.
- [ ] Commit as `feat: strengthen the human control and preparation payoff`.
- [ ] **STOP.** Return the Result Packet with both captures. Await owner PASS/FIX/REVERT.

---

## Task 5: Gold-Bar Judge Experience Acceptance

**This is not another visual task.** It integrates and verifies Tasks 1–4 against the
acceptance bar and corrects only actual failures.

```text
OPTICAL_FRAME_BLAST_RADIUS=NO
JUDGE_CRITERIA_IMPACT=Presentation, Design
```

**WHY_THIS_CAN_MOVE_JUDGE_SCORE:** four individually good moments can still add up to an
incoherent sequence. This task is the only one that evaluates the product the way a judge
actually meets it — as one continuous run — and it is where a pacing or hierarchy conflict
between tasks would otherwise ship unnoticed.

**Files:**

- Modify: `apps/web/src/styles/judge-impact.css` — corrections only
- Modify: `apps/web/e2e/workspace.spec.ts` — extend the judge flow only, never relax it

**Do not add features because final inspection reveals unused space.** Correct only actual
04B acceptance failures. If a moment fails the bar and cannot be corrected within the frozen
contracts, report it as a finding rather than expanding scope.

**Motion:** this task plans **no new motion** and therefore carries no motion table. It may
only retune the duration or easing of a transition already approved in Tasks 1–4, and only
to resolve a measured pacing conflict between them. Any such retune restates the amended
row of the original task's motion table in this task's Result Packet.

**Acceptance:**

`JUDGE_5_SECOND_TEST` — at the initial populated decision view a first-time viewer
immediately identifies the opportunity, the recommendation, and the primary reason and
action.

`JUDGE_30_SECOND_TEST` — the product itself visually communicates Decision → Why / Proof →
Activity, without narration doing the work.

`JUDGE_90_SECOND_TEST` — the complete flow communicates Opportunity → Decision → Why →
Grounded Proof → Activity → Human Approval → Application Pack, with no authority confusion,
no fabricated activity, and no implication of external submission.

- [ ] Walk the real populated local W01 flow end to end and record, per moment, whether the
      bar is met and what the failure is if not.
- [ ] Capture the complete judge sequence at 1440 × 810 into `.qualor/local/04b-task5/`.
- [ ] Capture regression frames at 1280, 1024, 768 and 320, plus a reduced-motion pass.
- [ ] Confirm at 1280 that the body still projects `queue canvas proof rail`; at 1024 and 768
      the frozen intermediate projection with its user-invoked rail; at 320 the single-column
      sequence with every action still reachable.
- [ ] Run the accessibility suite unmodified, plus the contrast assertions, and confirm no
      regression in landmarks, heading order, keyboard completeness, roving focus, focus
      trap and return, Escape, visible focus, or non-colour status.
- [ ] Apply corrections for actual failures only, in `judge-impact.css`.
- [ ] Extend the browser acceptance with any genuinely new judge-visible guarantee 04B now
      makes. Do not delete or relax an existing assertion.
- [ ] Capture the D02 frame and confirm the recorded A1.2 SHA-256 still matches.
- [ ] Run the full browser judge flow, all web tests, typecheck, build, and
      `./scripts/verify.ps1`. Confirm no paid AWS calls.
- [ ] Independent review; fix Critical and Important findings.
- [ ] Commit as `test: accept the QUALOR judge experience`.
- [ ] **STOP.** Return the final Result Packet with the full visual sequence.

---

## Commit sequence

The intended implementation history is:

1. `feat: sharpen selection and decision hierarchy`
2. `feat: strengthen the decision-to-proof transition`
3. `feat: make recorded agent work legible`
4. `feat: strengthen the human control and preparation payoff`
5. `test: accept the QUALOR judge experience`

## Testing required by every task

| Gate | Command |
| --- | --- |
| Focused unit tests | `npm --prefix apps/web run test:run -- <names>` |
| Full frontend tests | `npm --prefix apps/web run test:run` |
| Accessibility regression | included above; the suite is **never edited** |
| Reduced-motion regression | both the media-preference and `.reduce-motion` paths |
| Typecheck and build | `npm --prefix apps/web run build` |
| Browser acceptance | `npm --prefix apps/web run test:e2e` |
| Full 04A verification | `./scripts/verify.ps1` |
| Whitespace | `git diff --check` |

Task 5 additionally requires the complete judge-flow E2E and the full responsive and
reduced-motion capture set. No task makes a paid AWS call or creates a cloud resource.

Note for executors: `apps/web/tsconfig.json` includes only `src` and `vite.config.ts`, so
`npm run typecheck` does **not** typecheck `e2e/`. A change to the browser spec is validated
by running it, not by the typecheck gate.

## Plan self-review

```text
SPEC_COVERAGE=COMPLETE
PLACEHOLDERS=0
TBD=0
TODO=0
TYPE_CONSISTENCY=PASS
FILE_BOUNDARY_CONSISTENCY=PASS
OPTICAL_FRAME_CLASSIFICATION_COMPLETE=YES
MOTION_PURPOSE_COMPLETE=YES
JUDGE_SCORE_MAPPING_COMPLETE=YES
DEFERRED_SCOPE_LEAK=0
BACKEND_SCOPE_LEAK=0
04A_AUTHORITY_RISK=NONE
TASK_COUNT=5
WHERE_04B_RULES_LIVE=apps/web/src/styles/judge-impact.css
OPTICAL_FRAME_YES_TASKS=NONE
OPTICAL_FRAME_NO_TASKS=1,2,3,4,5
NEW_ANIMATION_LIBRARY=NO
TOKENS_CHANGED=NO
ZONE_COUNT=4
```

All six judge-visible moments from the design specification are covered: moments 01 and 02
by Task 1, moment 03 by Task 2, moment 04 by Task 3, moments 05 and 06 by Task 4, with
Task 5 integrating all of them. Every task carries an optical-frame classification, a motion
table with a comprehension purpose, and a judge-score rationale.

This plan introduces no implementation code, no backend change, no schema or migration, no
security change, and no product-concept change. It converts the approved 04B design into the
five reviewable execution slices above, and authorises none of them to begin without owner
review between tasks.
