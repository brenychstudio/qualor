# QUALOR — demo video plan

**Status:** pre-production plan only. Nothing is recorded or published by this document.

```text
TARGET_RUNTIME   = 02:20
PREFERRED_RANGE  = 02:10 – 02:20
HARD_MAX         = 02:30   (Official Rules allow 5:00; we are deliberately far under)
```

**Format:** screen recording with voiceover. No camera required.
**Destination:** YouTube or Vimeo, public.

## The principle

This is not a technical walkthrough. It is a compressed proof that the idea is real.

A judge must be able to answer **"what is QUALOR?"** by 00:15. Everything after that exists
only to prove the sentence they already heard. Nothing is included because it is interesting
to build; it is included because it proves the claim.

The rules require the video to demonstrate the working project and to pitch the problem, who
it is for, and why it matters. Segment 1 carries the pitch; segments 3–8 carry the demonstration.

---

## Before recording

| Prerequisite | State | For |
| --- | --- | --- |
| Real-source REPLAY database seeded | ready | 3–8 |
| Architecture diagram | ready | 2 |
| Browser 1440 × 900, clean profile, no extensions | to do | all |
| Capture at 1920 × 1080 | to do | the four-zone body needs ≥ 1280 CSS px |
| Audio: quiet room, one take per segment | to do | all |

**Record at the current truthful `PREPARE`.** It is the strongest thirty seconds available —
the agent refusing to rubber-stamp its own submission. If a later re-run truthfully returns
`APPLY`, only segments 4 and 9 need re-recording.

This is a historical `REPLAY` decision. It is separate from the later controlled `LIVE`-path
compiler acceptance, which truthfully ended `NO_PROGRESS` with `REVIEW_REQUIRED` / `WATCH`.
Do not substitute that verification result for the recorded PREPARE story.

---

## 1 · 00:00 – 00:15 · Hook — the whole product in one sentence

**Screen:** the populated Decision Workspace, immediately. **Do not open on a logo.**

**Narration intent** — all four ideas must land inside these fifteen seconds:

> "QUALOR is autonomous opportunity intelligence. It reads the **real rules**, **decides**
> whether an opportunity is worth pursuing, shows exactly **why** — and **stops** before
> anything consequential happens."

`REAL RULES` · `DECISION` · `PROOF` · `HUMAN BOUNDARY`. Wording may be tightened; all four
must survive.

## 2 · 00:15 – 00:30 · How it works

**Screen:** the architecture diagram, then **4–5 seconds maximum** on
`src/qualor/runtime/agent.py` — enough to see a real Strands `Agent`, its tools and the
Bedrock model. Do not scroll through the file.

**Narration intent:** Strands researches. Deterministic Python judges. The model decides what
to read, never what verdict to return.

Do not read the tool names or hook names aloud.

## 3 · 00:30 – 00:48 · A real opportunity, truthfully

**Screen:** the real AWS Agents for Humans row, the `REPLAY` marker, the real deadline.

**Narration intent:**

> "This is the real AWS Agents for Humans opportunity, using captured official Devpost
> evidence. REPLAY preserves the real source deterministically — it is neither fixture data
> nor fake live activity."

One phrase for REPLAY. Do not explain the mode architecture.

## 4 · 00:48 – 01:13 · The killer moment

**Screen:** the Decision Canvas — `BEST PROJECT = QUALOR`, `ELIGIBILITY = PASS`,
`CAPACITY = SUFFICIENT`, `RECOMMENDATION = PREPARE`.

**Narration intent:** QUALOR evaluated its own submission to this hackathon, and refused to
say APPLY — because at that moment required materials were still missing.

This is the conceptual centre of the video. Let it breathe. Do not walk through the scores.
Say *"strategy is prioritization, not a probability of winning"* only if it fits without
slowing the beat.

## 5 · 01:13 – 01:36 · Proof

**Screen:** *Why this decision* → Evidence Reader → the exact official excerpt → the citation
and *View original*.

**Narration intent:** every source-derived opportunity fact can be checked against the exact
supporting official text, with its source and retrieval time.

**Let the excerpt sit still long enough to read.** This is the single most persuasive frame
in the video; do not cut away early.

## 6 · 01:36 – 01:43 · Operational trace

**Screen:** a brief glimpse of the Intelligence Rail. **Seven seconds, hard.**

**Narration intent:** "The operational trace records what this run actually did."

Then move on. Do not narrate the counters. Do not call it live agent work.

## 7 · 01:43 – 02:00 · Human control

**Screen:** the Human Approval checkpoint. Show the no-submission boundary **before** clicking
Confirm, then confirm.

**Narration intent:**

> "The agent stops here. A person approves one bounded action. Nothing is submitted externally."

## 8 · 02:00 – 02:13 · Payoff

**Screen:** the Application Pack with Section 01 visible immediately. No long scroll.

**Narration intent:** QUALOR prepares a reviewable application pack, traceable back to the
decision and the evidence behind it.

## 9 · 02:13 – 02:20 · Close

**Screen:** a strong final Decision Workspace frame.

**Narration intent:** QUALOR turns repetitive opportunity triage into an auditable
professional decision.

End there. No outro, no credits, no logo animation.

---

## Timing

| # | Segment | In | Out | Length |
| --- | --- | --- | --- | --- |
| 1 | Hook | 00:00 | 00:15 | 0:15 |
| 2 | How it works | 00:15 | 00:30 | 0:15 |
| 3 | Real opportunity | 00:30 | 00:48 | 0:18 |
| 4 | Killer moment | 00:48 | 01:13 | 0:25 |
| 5 | Proof | 01:13 | 01:36 | 0:23 |
| 6 | Operational trace | 01:36 | 01:43 | 0:07 |
| 7 | Human control | 01:43 | 02:00 | 0:17 |
| 8 | Payoff | 02:00 | 02:13 | 0:13 |
| 9 | Close | 02:13 | 02:20 | 0:07 |
| | **Total** | | | **2:20** |

Transitions are straight cuts. The product's own state changes — proof opening, approval
confirming, the pack arriving — carry the motion. Add no effects.

## Deliberately not in this video

Belongs in the narrative, the README, the diagram or the source, not here:

the four tool names · hook names · schema generation · SQLite · test counts · the frontend
framework · each readiness gap individually · a long FIXTURE-versus-REPLAY explanation · the
zero counters · a full Intelligence Rail walkthrough · challenges · lessons learned · the
roadmap · other verticals · AgentCore detail · README instructions.

## Success test

| By | The judge can answer |
| --- | --- |
| 00:15 | What is QUALOR? |
| 01:00 | What did it decide? |
| 01:36 | Why should I trust the decision? |
| End | Where does the human take control, and what useful output is produced? |

## Claim audit for narration

| The narration may say | Basis | Status |
| --- | --- | --- |
| "a Strands agent researches; deterministic Python judges" | `runtime/agent.py`; `decisions/`, `eligibility/`, `matching/` | VERIFIED |
| "the real AWS Agents for Humans opportunity" | captured official source, sha256 recorded | VERIFIED |
| "captured official Devpost evidence, replayed deterministically" | REPLAY ingestion; run mode persisted as REPLAY | VERIFIED |
| "eligibility passes" | nine rules, each citing the official rules page | VERIFIED |
| "refused to say APPLY because materials were missing" | recorded PREPARE verdict and its readiness gaps | VERIFIED |
| "nothing is submitted externally" | no such code path; asserted in browser tests | VERIFIED |
| "QUALOR fetched this live just now" | false for a REPLAY run | **MUST NOT SAY** |
| "deployed on AgentCore Runtime" | not deployed | **MUST NOT SAY** |
| "try it live at …" | no hosted demo exists | **MUST NOT SAY** |
