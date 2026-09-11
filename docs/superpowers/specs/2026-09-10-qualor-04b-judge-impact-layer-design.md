# QUALOR-04B Judge Impact Layer Design

**Status:** Owner-approved canonical design for QUALOR-04B

**Date:** 2026-09-10

**Frozen base:** `feature/qualor-04a-workspace` at `e18df659129791c17f427fb935a7c19c5ae960b1`

**Product:** QUALOR — Autonomous Opportunity Intelligence

QUALOR-04B is a **judge impact layer** over the accepted QUALOR-04A product. It refines
hierarchy, material and state-driven motion so a first-time viewer understands the product
faster. It is not a redesign, a new product architecture, a new backend phase, a new agent
system, a broad responsive redesign, or deferred hardening.

The 04A delivery boundary already states that 04B "may tune presentation and interaction
quality" but "may not require rewriting the four-zone wide-body architecture,
`Decision → Why → Proof`, recommendation hierarchy, evidence model, approval boundary,
application-pack structure, or responsive content order". This specification stays inside
that boundary.

## 1. Status, owner approval and frozen base

Owner-approved direction: `QUALOR-04B = JUDGE_IMPACT_LAYER`.

```text
PRIMARY_VIEWPORT=1280-1440px
A1_2_FOUR_ZONE_STRUCTURE=FROZEN
LAYOUT_ARCHITECTURE_REDESIGN=PROHIBITED
IMPLEMENTATION_AUTHORIZED_BY_THIS_DOCUMENT=NO
```

The canonical wide body remains the four zones recorded in
[ADR 0004](../../decisions/0004-a1-2-four-zone-workspace-body.md): Opportunity Inbox,
Decision Canvas, Why & Proof / Evidence Plane, Intelligence Rail. Header and top navigation
are not body zones. This document does not reconsider that ruling.

04B also inherits the
[A1.2 frozen visual baseline](2026-09-09-qualor-a1-2-visual-baseline-freeze.md), which
records `A1_2_SPATIAL_PRECISION_BASELINE=FROZEN` and `REDESIGN_ALLOWED=NO`. That closure
states it "authorizes no further polish" and that future work "may extend this system"
while "replacing or reinterpreting it requires explicit owner authorization". 04B's polish
authority therefore comes from the separate owner approval recorded here, and it is an
authority to **extend** A1.2, never to reinterpret it.

### Surfaces this specification is written against

This document is written against the frozen implementation at the base commit, not against
an older design assumption. The surfaces 04B may touch are:

- `apps/web/src/layout/WorkspaceShell.tsx`, which exports both `WorkspaceShell` and the
  `WorkspaceFrame` that owns the body grid;
- `apps/web/src/layout/DecisionTrace.tsx`;
- `features/inbox/OpportunityInbox.tsx` and `OpportunityRow.tsx`;
- `features/decision/DecisionCanvas.tsx`;
- `features/evidence/EvidenceSheet.tsx`, `EvidenceClaim.tsx`, `TechnicalProvenance.tsx`;
- `features/activity/IntelligenceRail.tsx` and `ActivityHistory.tsx`;
- `features/approval/ApprovalPanel.tsx`;
- `features/draft-pack/ApplicationPack.tsx` and `DraftPackSection.tsx`;
- `features/states/ProductStateSurface.tsx`;
- `styles/tokens.css`, `styles/base.css`, `styles/propagation.css`.

### The frozen D02 optical preview is inside the blast radius

The A1.2 closure pins a development-only preview frame at exactly 1440 × 810 with a
recorded SHA-256. That frame is rendered by `dev/DecisionPreview.tsx` and
`dev/decision-optical.css`, and it imports the same `index.css` and the same
`WorkspaceFrame` as the product.

**No shared stylesheet is a safe layer by default.** An earlier revision of this section
claimed that `propagation.css` guards every rule with `:not(.workspace--optical-preview)` and
that propagation-layer changes therefore cannot reach the frozen frame. That was measured
wrongly and is false. `propagation.css` holds a mixture: of its 150 rules only 56 carry the
guard and 94 do not, and 69 of the unguarded ones are workspace and decision selectors the
frozen frame actually renders — `.recommendation-surface`, `.opportunity-metadata`,
`.signal-lane dd strong`, `.signal-lanes`, `.opportunity-heading h2`, `.workspace-grid` and
`.decision-primary-action-row` among them.

The correct rule is therefore:

- `base.css`, `tokens.css`, `propagation.css`, `WorkspaceFrame` and every other shared
  presentation layer **may** carry optical-frame blast radius. Whether a given change does
  depends on the concrete selector's rendered reach, never on which file it lives in;
- `judge-impact.css` is the one deliberate 04B isolation mechanism, and it isolates only
  because every workspace-affecting rule in it explicitly excludes
  `.workspace--optical-preview` — not because of where the file sits in the cascade;
- **blast radius is determined from actual rendered selector reach, and is proved
  empirically, never inferred from a stylesheet name.**

Consequently the implementation plan must state, for each change, whether it alters the
frozen D02 frame, and must prove that claim by re-capturing the recorded 1440 × 810 frame and
comparing its SHA-256 and region metrics. Where a change does alter the frame, the recorded
frame and hash must be re-captured and re-accepted by the owner as part of that task; a
silently stale recorded hash is a truthfulness defect, not a cosmetic one. A task must never
reclassify itself from blast radius `NO` to `YES` silently, and must never re-baseline the
frozen frame on its own authority.

## 2. Goal

QUALOR should communicate one story visually:

**Find → Understand → Prove → Human controls → Prepare**

04B optimises comprehension and perceived product quality around that story at the demo
viewport. It adds no authority, no data, and no new product capability.

## 3. Non-goals

04B does not:

- change the zone count, the body grid, or the responsive breakpoints as an act of design;
- restructure persistence, workspace services, API contracts, routing, selected-opportunity
  authority, evidence flow, approval flow, or the Draft Pack lifecycle;
- introduce a new theme system, a component kit, or an animation dependency;
- start a separate mobile or tablet redesign;
- begin any item listed in section 16 as deferred;
- convert synthetic fixture evidence into live-looking content.

Any proposed backend, API, schema, migration or security change is a **design blocker** that
returns to the owner. It is never absorbed into polish.

## 4. Judge experience strategy

Three nested comprehension budgets govern every 04B decision.

| Budget | The viewer must understand | Carried by |
| --- | --- | --- |
| ~5 seconds | What QUALOR recommends for the selected opportunity, and why it matters | Decision Canvas hierarchy |
| ~30 seconds | Decision → Why / source-grounded Proof → Activity | Canvas, Evidence Plane, Intelligence Rail |
| ~60–90 seconds | Opportunity → Decision → Why → Proof → Activity → Human Approval → Application Pack | The whole canonical path |

When a refinement improves one budget at another's expense, the shorter budget wins. When a
refinement improves none of them, it is deferred — this restates the existing 04A rule that
no visual decision may be added merely because it looks impressive.

## 5. Frozen architecture and authority

04B may not change, restate, duplicate or visually contradict any of these:

- `UNKNOWN != PASS`;
- strategy is prioritisation, never probability of winning;
- deterministic recommendation, eligibility and priority authority;
- `presentation_state`, `ProductState` and `ActionCapability` authority;
- run state authority, and the separation of run state from decision state;
- LIVE / FIXTURE / REPLAY truthfulness;
- evidence and provenance authority;
- version-bound approval, its expiry and its revocation;
- action-token handling and idempotency;
- Draft Pack immutability and attribution;
- no external submission.

**No 04B visual need justifies duplicating policy in React.** Where a refinement appears to
require a value the server does not already expose, the refinement is dropped or returned to
the owner as a blocker; it is never reconstructed in the browser. Neither the Evidence Plane
nor the Intelligence Rail may be styled so as to imply it owns deterministic decision policy.

## 6. Wide four-zone visual hierarchy

At 1280 px and above the four zones keep their accepted authority weighting.

| Zone | Authority | Visual weight | Material |
| --- | --- | --- | --- |
| Opportunity Inbox | Selection and priority queue | Supporting | Dark workspace |
| Decision Canvas | Dominant deterministic judgment | **Dominant** | Dark workspace |
| Why & Proof / Evidence Plane | Source-grounded proof | Supporting, subordinate until invoked | Warm light proof |
| Intelligence Rail | Persisted operational telemetry | Supporting | Dark workspace |

04B may adjust optical weight — type scale, spacing, tonal separation, rule weight — but may
not invert this ordering, promote a supporting zone to dominance, or let the Decision Canvas
compete with a neighbour. The 85 % dark workspace / 15 % light proof dominance and the "dark
is where QUALOR thinks, light is where QUALOR proves" distinction are preserved.

## 7. The six judge-visible moments

### 01 — Opportunity selection

*Goal:* the selected opportunity and its priority and state are obvious, while the Inbox
stays supporting rather than competing with the Decision Canvas.

*May refine:* selected-row clarity; hierarchy within the row; scan rhythm; the transition
into the selected state; the visual relationship between queue and canvas.

*Must not:* turn the Inbox into cards; add decorative ranking visualisation; introduce
ranking logic; render `priority_rank` as a score; redesign filter or search architecture.
Ordering remains the server's `QUALOR_INBOX_PRIORITY_CONTRACT_V1` total order, and
`presentation_state` remains the server's answer.

### 02 — Decision resolves

*Goal:* the primary visual hero. `APPLY`, `PREPARE`, `WATCH` or `SKIP` reads immediately.

*May refine:* typographic hierarchy; a restrained resolution transition; the relationship
between recommendation, reason line, Strategy and the four core facts; visual pacing; the
dominance of the single recommendation-specific action.

*Must not:* add circular gauges, speedometers or radar charts; introduce probability
language; animate fake AI thinking; accumulate a metrics wall. Strategy stays a restrained
number with its explicit boundary copy and shows `Not enough evidence` rather than an
invented value. Exactly four first-level facts remain: Best project, Eligibility, Effort,
Deadline.

The A1.2 baseline specifically accepted four causal decision signals converging into a
**rectangular** recommendation surface, and specifically excluded any orb, polygon, ring or
decorative sci-fi centrepiece. The existing small signal icons do not authorise a new
centrepiece or visual metaphor. 04B refines that geometry; it does not replace it.

### 03 — Why → Proof

*Goal:* QUALOR's signature judge interaction. The dark intelligence workspace recedes, the
warm proof material becomes authoritative, and source proof becomes easy to inspect.

The transition must communicate, in order: *this is the decision*, *this is why*, *this is
the evidence*.

*May refine:* spatial and opacity hierarchy during entry; proof-plane entry choreography;
the document material transition; citation emphasis; the visual separation between QUALOR's
interpretation of a claim and the exact source excerpt.

*Must not alter:* evidence authority; exact excerpt text; citation truth; the five evidence
states `PASS`, `FAIL`, `UNKNOWN`, `CONFLICT`, `STALE`; focus mechanics; accessibility;
technical-provenance scope. The deferred `?technical=true` work stays out of scope.

The frozen implementation exposes proof twice — a persistent subordinate Why & Proof zone
carrying a proof preview and the trigger, and the invoked full Evidence Plane above the
workspace. 04B refines both and preserves the rule that proof stays subordinate to the
decision until invoked or contextually exposed.

### 04 — Intelligence Rail

*Goal:* make actual persisted telemetry easier to understand, and productively alive,
without fabricating agent behaviour.

*May refine:* event hierarchy; pacing; phase legibility; quiet state changes; the
relationship between the current decision and prior run events.

Motion here may occur **only because real UI or event state changed.** 04B must never
fabricate `LIVE`, progress, timers, model calls, source verification, or Bedrock/AgentCore
activity, and never insert decorative events between real states. FIXTURE and REPLAY remain
visibly truthful, and a disconnected provider, budget stop, partial, failed or cancelled run
keeps its canonical state. Persisted in-flight run visibility remains deferred.

### 05 — Human approval

*Goal:* the consequential human boundary feels deliberate, premium and trustworthy.

The viewer must clearly understand what action is being approved, which opportunity, project
and policy versions it is bound to, that confirming starts bounded preparation, and that
nothing is submitted externally.

*May refine:* hierarchy; staging; focus treatment; readability of bindings and expiry; a
serious control-boundary material treatment.

*Must not:* weaken any approval check; alter action-token handling or idempotency; create
new approval authority; use submit or send vocabulary. The V1 approval presentation states
and the `GENERATE_DRAFT_PACK` boundary are unchanged.

### 06 — Application Pack

*Goal:* the payoff — dark judgment gives way to light editorial preparation.

*May refine:* document rhythm; section hierarchy; attribution readability; evidence and
source-reference clarity; missing-field treatment; a sense of completion that does not imply
submission occurred.

*Must preserve:* the seven canonical sections in server order; pack immutability and
complete attribution; direct route reload of `/draft-packs/:packId`; the distinction between
draft prose and evidence; truthful missing-field state. No editor, no autosave, no external
submission.

## 8. Motion language

Motion is restrained and state-driven. Where motion adds comprehension the transition
completes in roughly **400–700 ms**, consistent with the 04A motion contract.

Preferred tools: opacity, restrained translate, restrained scale, tonal and material
transition, and typographic hierarchy change. The existing `--motion-duration`,
`--motion-easing` and `--motion-reduced` tokens and the existing `plane-enter` keyframe are
the starting point.

```text
NO_NEW_ANIMATION_LIBRARY=DEFAULT
```

A dependency may be proposed only if this specification is first amended to demonstrate a
compelling, non-replaceable requirement. Absent that amendment the implementation plan must
not add one.

Prohibited: continuous ambient motion; pulsing AI glow; cyberpunk effects; decorative
parallax; gaming loaders; fake reasoning animation; any animation that delays access to
content.

Reduced motion must preserve every state and action without loss of meaning. The frozen
implementation already disables animation and transition under both
`prefers-reduced-motion: reduce` and the `.reduce-motion` class; 04B keeps both paths
complete rather than introducing motion that carries meaning nothing else carries.

## 9. Material and typography direction

04B is polish, not style replacement. The established A1.2 identity is preserved: the
blue-carbon and graphite intelligence workspace, restrained tonal hierarchy, mineral
warm-light proof material, the editorial Application Pack, semantic recommendation tones,
typography-led meaning, and quiet premium composition.

Refinement happens through the existing semantic tokens — workspace, surface, divider, text
hierarchy, proof paper and ink, citation, focus, the four recommendation tones, spacing,
motion, and the document scale. 04B may retune token *values* and may add a semantic token
where a role genuinely exists. It may not rename roles that components and tests depend on,
and it may not reintroduce raw colour values into components.

Prohibited: neon gradients; glassmorphism redesign; generic Tailwind dashboard composition;
card-wall redesign; bright success or error treatment; any new theme system. Recommendation
meaning must continue to appear as text, never as tone alone.

## 10. Responsive preservation

The primary polish target is 1280–1440 px. The frozen responsive projection is preserved
exactly:

- **≥ 1280 px** — four persistent body zones, `queue canvas proof rail`;
- **768–1279 px** — the Opportunity Inbox remains a persistent column, the Why & Proof plane
  sits below the canvas, and the Intelligence Rail becomes a user-invoked contextual panel;
- **< 768 px** — a single-column sequence retaining all required content and actions.

04B may make the **smallest** responsive correction required by an approved desktop change,
and must say so explicitly when it does. It must not begin a separate mobile or tablet
redesign. Every production change preserves content reachability and the accessibility
baseline at 320, 768, 1024 and 1440 px.

## 11. Accessibility preservation

The Task 15 baseline is binding and non-negotiable. 04B may not regress semantic landmarks
or their accessible names, heading order, keyboard completeness, the skip link, Inbox roving
focus with exactly one row in Tab order, the Evidence Sheet focus trap and focus return,
Escape behaviour, approval keyboard behaviour, visible focus, status meaning that does not
rely on colour alone, contrast, or reduced motion.

**Any visual refinement that conflicts with accessibility is rejected**, not negotiated. The
committed accessibility suite is the arbiter; a refinement that can only pass by weakening
one of its assertions is a design blocker.

Accessible names are load-bearing for both the accessibility suite and the browser
acceptance — `Opportunity inbox`, `Why & proof`, `Workspace context`, `Human approval`,
`Application pack` among them. 04B must not rename them for aesthetic reasons.

## 12. FIXTURE versus real-demo truth

04B visual development may use the owned `W01_DECISION_TO_DRAFT_PACK` fixture as a
repeatable populated reference.

**W01 proves product integration** — persistence, decision flow, evidence flow, approval,
drafting, and the browser experience. **W01 does not prove current official AWS source
truth.** Its evidence uses owned synthetic `.example` sources.

Real judge-visible official evidence belongs to the later killer-demo and submission
preparation work. 04B must not restyle synthetic fixture evidence to read as live or
official, must not remove or soften the FIXTURE mode label, and must not present the
development-only D02 preview as product data.

## 13. Considered approaches

**A. Judge Impact Layer — SELECTED.** Targeted hierarchy, material and state-driven motion
polish over the frozen product architecture. Best impact-to-risk ratio: it strengthens the
comprehension budgets in section 4 without touching authority, layout architecture or the
accessibility baseline.

**B. Cinematic 04B — REJECTED.** More aggressive motion and a larger visual transformation.
Rejected because it risks clarity, accessibility and frozen-layout stability, and because
motion that outruns real state would collide with the truthfulness rules in moment 04.

**C. Static polish only — REJECTED.** Typography and spacing refinement without meaningful
transition polish. Rejected because it underuses QUALOR's strongest asset for competition
judging — the Decision → Proof → Approval story — and leaves the 30- and 90-second budgets
carried by narration.

## 14. Success criteria

`JUDGE_5_SECOND_TEST` — at a populated wide desktop, a first-time viewer identifies the
selected opportunity, the recommendation, and the primary reason and action, without opening
secondary detail.

`JUDGE_30_SECOND_TEST` — the demo visibly communicates Decision → Why / source-grounded
Proof → Activity without narration carrying the entire explanation.

`JUDGE_90_SECOND_TEST` — the canonical browser path communicates Opportunity → Decision →
Why → Proof → Activity → Human Approval → Application Pack with no authority confusion.

`VISUAL_HIERARCHY` — the Decision Canvas remains dominant; Inbox, Proof and Intelligence
remain supporting or contextual according to their authority.

`MOTION` — state-driven only; no fabricated agent activity; the reduced-motion equivalent
remains complete.

`REGRESSION` — the existing browser judge flow remains functional, all 04A verification
remains green, and no backend, API, schema or security mutation occurs.

## 15. Testing and acceptance expectations

Every 04B change is verified against gates that already exist. The plan must not weaken an
assertion to accommodate a visual change.

- `scripts/verify.ps1` stays green in full: Ruff, the Python suite, schema and type drift,
  the frontend unit suite, typecheck, build, the canonical hash, the secret scan, and the
  clean-worktree gate.
- `npm --prefix apps/web run test:e2e` stays green, including the four-zone body assertion
  that pins the computed `grid-template-areas` to `queue canvas proof rail`.
- The accessibility suite stays green unmodified; it is the arbiter of section 11.
- Reduced-motion behaviour is exercised in both the media-preference and `.reduce-motion`
  paths.
- Verification makes no paid AWS calls and creates no cloud resources.

Where a change alters the frozen D02 optical frame described in section 1, that task
re-captures the frame and records the new SHA-256 for owner acceptance, rather than leaving
the recorded value stale.

Where 04B adds a genuinely new judge-visible guarantee it may add a test. It may not delete
or relax an existing one. A change that can only pass by editing a frozen assertion is a
design blocker.

## 16. Explicitly deferred work

Outside 04B, and not to be started by it: richer `?technical=true` provenance and query
support; persisted in-flight run visibility; guaranteed typed Draft Pack `source_citations`;
DraftPack key union tightening; the `NO_RESULTS` local-filter distinction while no local
filter exists; normalizer coverage expansion including
`QUALOR-05-HARDEN-CLAIM-NORMALIZER-COVERAGE`; billing and pricing; subscription
implementation; the Art vertical; a generalized workflow engine; and external submission.

**04B does not become QUALOR-05.**

## 17. Implementation boundary for the later plan

The later 04B implementation plan may sequence work only within these bounds:

- production change concentrated in the existing frontend presentation and style surfaces
  named in section 1;
- no new route, no new API call, no new generated type, no migration;
- no new runtime dependency, and specifically no animation library;
- each change traceable to one of the six moments in section 7 and to at least one success
  criterion in section 14;
- each change verified by section 15 without relaxing an existing assertion;
- each change declaring whether it alters the frozen D02 optical frame.

This document is a design specification. It contains no implementation sequence, task
breakdown, component code, or implementation authorization. A separate owner-approved plan
is required before any 04B production change.

## 18. Self-review record

```text
PLACEHOLDERS=0
TBD=0
TODO=0
CONTRADICTIONS=0
AUTHORITY_WEAKENING=0
REDESIGN_REQUIREMENTS=0
BACKEND_REQUIREMENTS=0
DEFERRED_SCOPE_LEAK=0
A1_2_FOUR_ZONE_STRUCTURE=FROZEN
WIDE_BODY_ZONE_COUNT=4
PRIMARY_VIEWPORT=1280-1440
SIX_JUDGE_MOMENTS=DEFINED
MOTION_LANGUAGE=STATE_DRIVEN
NEW_ANIMATION_LIBRARY=NO
ACCESSIBILITY_BASELINE=BINDING
RESPONSIVE_BASELINE=PRESERVED
FIXTURE_TRUTHFULNESS=PRESERVED
FIXTURE_OFFICIAL_NETWORK_PROOF=NO
FROZEN_D02_FRAME_BLAST_RADIUS=DECLARED
APPROACH_SELECTED=A_JUDGE_IMPACT_LAYER
IMPLEMENTATION_AUTHORIZED=NO
```
