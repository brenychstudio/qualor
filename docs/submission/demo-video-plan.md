# QUALOR — demo video plan

**Status:** pre-production plan only. Nothing is recorded or published by this document.

**Target runtime:** 4:10 (hard ceiling 5:00 per the Official Rules)
**Format:** screen recording with voiceover. No camera required.
**Destination:** YouTube or Vimeo, public.

The rules require the video to demonstrate the working project and to pitch the problem, who
it is for, and why it matters. Both halves are covered below.

---

## Before recording

| Prerequisite | State | Needed for |
| --- | --- | --- |
| Real-source REPLAY database seeded | ready (`killer-demo.db`) | segments 3–8 |
| Architecture diagram | ready (`docs/architecture/qualor-architecture.svg`) | segment 2 |
| Browser at 1440 × 900, clean profile, no extensions | to do | all |
| Demo recorded at PREPARE state, before closing readiness gaps | decision | see note |
| Audio: quiet room, pop filter, single take per segment | to do | all |

**Recording resolution:** capture at 1920 × 1080; the workspace is a wide composition and the
four-zone body needs ≥ 1280 CSS px to project `queue canvas proof rail`.

**One decision to make first.** The demo can be recorded at the current truthful `PREPARE`, or
after the four readiness gaps close and the engine is re-run. `PREPARE` is the stronger story —
the agent declining to rubber-stamp its own submission — and this plan is written for it. If
the re-run later returns `APPLY`, segment 4 and segment 9 need re-recording, nothing else.

---

## Sequence

### 1 · 00:00 – 00:25 · The problem, and what QUALOR is

**Screen:** QUALOR wordmark, then the populated Decision Workspace at rest.

**Narration intent:** professionals lose hours deciding whether an opportunity is worth
pursuing — reading dense rules, checking eligibility, estimating effort — and most of that
work ends in "no". QUALOR is autonomous opportunity intelligence: it does that work and
returns a decision you can audit.

**Capture needed:** workspace at 1440 × 810, decision view at rest.

---

### 2 · 00:25 – 00:50 · Architecture and the agent system

**Screen:** `qualor-architecture.svg`, held still, with slow highlight on band 03.

**Narration intent:** a Strands agent does the research — four tools, sequential execution,
every model and tool call budgeted before it runs. Deterministic Python makes the judgment.
That separation is the whole design: the model decides what to read, never what the answer is.

**Capture needed:** the SVG. No screen recording.

---

### 3 · 00:50 – 01:30 · A real opportunity enters, truthfully

**Screen:** Opportunity Inbox showing the real AWS Agents for Humans Hackathon row. Point out
`REPLAY` in the mode marker. Open the opportunity.

**Narration intent:** this is the actual hackathon, read from the official Devpost rules page.
The badge says REPLAY, not LIVE and not FIXTURE — the run is deterministically replaying a
captured real official source, and the product shows the mode that actually ran. The deadline
on screen is the real deadline from the official rules; it is never shifted onto today's clock.

**Capture needed:** inbox row; mode marker close-up; deadline `2026-09-15T00:00:00Z`.

**Do not say:** that QUALOR fetched this live during the recording. It did not.

---

### 4 · 01:30 – 02:15 · The decision

**Screen:** Decision Canvas. Hero recommendation, the four causal signals converging, the
reason line, Strategy.

**Narration intent:** QUALOR selected itself as the best-fit project, eligibility passes on
nine rules, capacity is sufficient — and the recommendation is **PREPARE**, not APPLY, because
four required submission materials do not exist yet. Name them. This is the point of the
product: it did not rubber-stamp the answer its owner wanted.

**Narration intent (Strategy):** say explicitly that Strategy is prioritization, not a
probability of winning.

**Capture needed:** decision hero; readiness gaps; the PREPARE reason codes.

---

### 5 · 02:15 – 02:55 · Why — the exact official evidence

**Screen:** click *Why this decision*. The dark workspace recedes; the warm evidence document
takes authority. Scroll to the deadline claim.

**Narration intent:** every fact is backed by the exact sentence from the official rules —
verbatim, not a summary — with the source URL, the retrieval time and the content hash. Read
the quoted Submission Period line aloud and point at the matching structured deadline. Note
the `OFFICIAL RULES` source authority.

**Capture needed:** Evidence Reader open; the verbatim excerpt block; `View original` citation.

**This is the most important 40 seconds in the video.** Let the excerpt sit on screen long
enough to be read.

---

### 6 · 02:55 – 03:25 · The recorded agent work

**Screen:** close the proof, move to the Intelligence Rail. Scroll it.

**Narration intent:** the rail is the persisted operational trail — what the run actually
recorded, in order, with its own counters. Point out that the retrieval counters read zero for
this replayed run and that the rail says so plainly, rather than inventing activity.

**Capture needed:** rail with recorded events; "Recorded in this run" counters; the stop reason.

**Do not say:** that the agent is working live on screen.

---

### 7 · 03:25 – 03:55 · Where the human takes control

**Screen:** click *Approve application*. The Human Approval checkpoint.

**Narration intent:** the agent stops here. A person approves one bounded action — prepare a
draft pack — bound to specific opportunity, project and policy versions, expiring, single-use.
Read the boundary line aloud: nothing is submitted externally, no organizer is contacted, no
external form is filled. Then confirm.

**Capture needed:** checkpoint with bindings; the no-submission statement **before** confirm;
the state moving to `DRAFT_READY`.

---

### 8 · 03:55 – 04:25 · The payoff

**Screen:** open the Application Pack. Show section 01 in the first viewport, then scroll
through the seven sections.

**Narration intent:** a prepared local document — seven immutable sections, fully attributed,
traceable back to the evidence. Say plainly: this is prepared *for review*. Nothing has been
submitted anywhere.

**Capture needed:** pack first viewport; the seven section headings; the attribution block.

---

### 9 · 04:25 – 04:40 · Close

**Screen:** back to the decision view, PREPARE hero held.

**Narration intent:** QUALOR turns repetitive, judgment-heavy opportunity triage into a
decision a professional can audit — grounded in the real source, deterministic, and stopped at
human control. It told us to prepare rather than apply, and it was right.

---

## Transitions

Straight cuts throughout. The product's own state transitions carry the motion — proof
opening, approval confirming, the pack arriving — so no editing effects are needed and none
should be added.

## Claim audit for narration

| Line the narration may say | Basis | Status |
| --- | --- | --- |
| "a Strands agent with four tools" | `src/qualor/runtime/agent.py` | VERIFIED |
| "every model and tool call is budgeted" | budget hooks in the same file | VERIFIED |
| "deterministic Python makes the judgment" | `decisions/`, `eligibility/`, `matching/` | VERIFIED |
| "this is the real hackathon's official rules page" | captured source, sha256 recorded | VERIFIED |
| "the deadline is never shifted onto today's clock" | REPLAY ingestion, asserted by test | VERIFIED |
| "eligibility passes on nine rules" | task2c result | VERIFIED |
| "PREPARE because four materials are missing" | task2c readiness gaps | VERIFIED |
| "nothing is submitted externally" | no such code path; asserted in browser tests | VERIFIED |
| "QUALOR fetched this live just now" | false for a REPLAY run | **MUST NOT SAY** |
| "deployed on AgentCore" | not deployed | **MUST NOT SAY** |
| "try it live at …" | no hosted demo exists | **MUST NOT SAY** |
