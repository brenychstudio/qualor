# QUALOR — Devpost submission narrative

**Track:** Professional Agents
**Status:** draft for owner review. Every claim below describes behaviour that exists in this
repository today. Anything not yet built is marked explicitly as future work.

---

## What it does

QUALOR is autonomous opportunity intelligence for professionals.

It takes an opportunity — a grant, a programme, an award, a call for proposals — reads the
official rules itself, and works out whether *you* should actually pursue it. Not "here are
some results". A decision: **APPLY**, **PREPARE**, **WATCH** or **SKIP**, with the exact
sentence from the official rules that justifies each part of it.

Then it stops. Before anything consequential happens, a human approves. Only then does QUALOR
prepare an application pack — locally, for you to review. It never submits anything anywhere.

## The problem

Deciding whether to pursue an opportunity is repetitive, judgment-heavy work that eats
professional time. Every opportunity means reading dense official rules, checking eligibility
against your actual situation, working out what you'd have to build, estimating whether you
can finish before the deadline, and deciding whether it's worth it at all.

Most of that work ends in "no". The work still has to be done to find out.

Generic AI tools make this worse, not better. They summarise confidently, and a confident
summary of eligibility rules is exactly the wrong artifact: you cannot act on it, because you
cannot check it. What a professional needs is a decision they can audit.

## How it works

```
Official sources → Strands agent research → evidence → deterministic judgment
                 → human approval → prepared application pack
```

**A Strands agent does the research.** It searches, fetches official pages, extracts claims
and re-evaluates what it still needs. Every call is budgeted before it runs.

**Deterministic engines make the judgment.** Eligibility, matching, conflicts, effort,
capacity, readiness and strategy are pure Python. The same inputs always produce the same
verdict. The model never authors the recommendation — that separation is the point.

**Evidence is exact.** Every fact carries the verbatim excerpt that proves it, plus the source
URL, the retrieval instant, the content hash and the source authority. If a structured fact
and its quoted excerpt ever disagreed, that would be a defect — so it is checked mechanically.

**UNKNOWN is never PASS.** If a rule cannot be evaluated from the evidence, QUALOR says so and
the decision reflects it. It does not guess, and it does not fill gaps to look decisive.

**The human boundary is real.** Approval is version-bound, expiring and single-use. If the
opportunity, the project or the policy version changes, the approval is invalidated rather
than silently reused.

## How we built it

Python 3.12, Pydantic v2 and FastAPI on the backend; React, TypeScript and Vite on the front.
SQLite for persistence with full provenance. Domain contracts are defined once in Pydantic,
exported as 42 JSON Schemas, and generate the frontend's TypeScript types — no domain
interface is hand-maintained on either side.

The verification gate runs Ruff, the Python suite, schema and type drift checks, the frontend
suite, typecheck, build, a canonical-document hash and a secret scan, and refuses to pass on a
dirty worktree. Current state: **1050 Python tests, 312 frontend tests, 27 browser end-to-end
tests**, all green.

The browser tests drive the real API against a real database. Nothing is stubbed, and no test
asserts a value it supplied itself.

## How Strands Agents is used

`src/qualor/runtime/agent.py` is one Strands `Agent` with four tools:

| Tool | Role |
| --- | --- |
| `search_web` | find candidate official sources, host-restricted |
| `fetch_official_source` | retrieve a candidate over HTTPS with DNS-pinned, allowlisted destinations |
| `extract_official_claims` | pull claims with their exact supporting excerpts |
| `evaluate_current_state` | ask the deterministic engine what is still missing, and plan from that |

It runs with a `SequentialToolExecutor` and three lifecycle hooks — `BeforeModelCallEvent`,
`BeforeToolCallEvent` and `AfterToolCallEvent` — wired to a budget guard. Every model and tool
call is *reserved* before it runs and *committed* after it returns, against a physical cap.
When the budget is exhausted the run stops and records why.

The model is `BedrockModel`, wrapped so its `converse` calls pass through the same guard.

The interesting part is the last tool. `evaluate_current_state` lets the agent ask the
deterministic engine what it still doesn't know, and plan its next retrieval from that answer.
The agent decides *what to go and read*. It never decides *what the answer is*.

## Human control and safety

- The agent stops at an explicit human approval boundary before any consequential step.
- Approvals are version-bound, expiring and single-use.
- **Nothing is ever submitted externally.** There is no code path that submits an application.
- Runtime mode is fail-closed: `LIVE`, `REPLAY` and `FIXTURE` are distinct, a run gets exactly
  one, and the mode the product displays is the mode that actually ran.
- Action tokens never reach the browser.
- The prepared pack is immutable and fully attributed.

## What makes QUALOR different

Most agent projects end at an answer. QUALOR ends at a **decision you can audit**, and stops
short of acting on it.

Three things follow from that, and they are the parts we'd point a judge at:

1. **The model researches; deterministic code judges.** Re-running the same inputs gives the
   same verdict, every time.
2. **Every displayed fact is backed by the exact source sentence**, with its URL, retrieval
   time and content hash — one click away in the Evidence Reader.
3. **It will tell you "not yet".** Which brings us to the demo.

## The demo: QUALOR evaluates itself

For the demonstration we pointed QUALOR at the real AWS Agents for Humans Hackathon — this
one — and asked it to evaluate QUALOR as the candidate project.

It read the official rules, extracted the submission requirements, checked them against the
repository as it actually is, and returned:

```
BEST_PROJECT  = QUALOR
ELIGIBILITY   = PASS        (nine rules, each citing the official rules page)
CAPACITY      = SUFFICIENT  (5.5–13 h estimated against 35 h available)
READINESS     = GAPS_EXECUTABLE
STRATEGY      = 75
RECOMMENDATION = PREPARE
```

**PREPARE, not APPLY** — because at evaluation time four required submission materials did not
yet exist: the public repository, the architecture diagram, the demo video and the written
narrative.

That is the behaviour we most want judged. QUALOR had every reason to say APPLY about its own
submission, and it did not, because the deterministic engine found real gaps. An agent that
rubber-stamps the answer its owner wants is not doing the job. This one names what is missing
and how long it will take.

## Professional Agents fit

The track asks for an agent that makes someone dramatically better at the work they already
do, targeting the repetitive, judgment-heavy tasks that eat their day.

Opportunity triage *is* that task. It recurs, it demands judgment, it is mostly unrewarded,
and it is done badly under time pressure. QUALOR handles it end to end — discovery, evidence,
judgment, human approval, prepared output — rather than chatting about it.

## Challenges

**Keeping the model out of the verdict.** The easy build puts an LLM in the decision path and
gets a fluent answer nobody can check. Splitting research from judgment meant the agent needed
a way to ask what was still unknown, which is what `evaluate_current_state` exists for.

**Making "unknown" survive.** It is remarkably easy for a missing fact to become a default, a
default to become an assumption, and an assumption to read as a finding. Keeping UNKNOWN
distinct from PASS all the way to the screen shaped the contracts more than anything else.

**Time as a source fact.** Our owned test scenarios slide onto the current clock so they keep
deciding the way they were authored. Real captured sources must *never* do that — moving a
quoted deadline away from the sentence quoting it is precisely the defect the product exists
to prevent. The ingestion boundary now distinguishes the two, and only owned scenarios move.

**Saying things the source did not say.** Our own excerpt checker caught us adding a space
after a bold label where the official page runs the label into the sentence. Small, and
exactly the class of drift that turns a quotation into a paraphrase.

## Accomplishments

- A working separation between agent research and deterministic judgment.
- Evidence that is exact by construction, verified mechanically rather than by inspection.
- A human approval boundary with real version binding, expiry and single use.
- A judge-ready decision workspace: inbox, decision, evidence reader, activity trail,
  approval, application pack.
- 1050 Python tests, 312 frontend tests, 27 browser end-to-end tests against the real stack.
- An agent that returned PREPARE about its own submission when APPLY would have been easier.

## What we learned

That the hard part of an agent product is not getting it to act — it is getting it to stop,
and to be checkable when it does. Most of the engineering went into provenance, mode
truthfulness and the approval boundary, and that is what makes the output worth trusting.

## What's next

- Close the four readiness gaps and re-run the decision to see whether QUALOR truthfully
  reaches APPLY about itself.
- Persisted in-flight run visibility, so a long research run is watchable as it happens.
- Broaden beyond the current profile shape to other professional verticals — creators,
  studios, independent researchers. The domain contracts are general; the verticals are not
  yet built, and we are not claiming them as current functionality.
- Optional AgentCore deployment. QUALOR uses AgentCore web search in LIVE mode today, but it
  is **not** deployed on AgentCore runtime, and we are not presenting it as such.

---

## Claim audit

Recorded so a reviewer can check this document against the repository.

| Claim | Evidence | Status |
| --- | --- | --- |
| Strands `Agent`, 4 tools, `SequentialToolExecutor`, 3 hooks | `src/qualor/runtime/agent.py` | VERIFIED |
| `BedrockModel` with budget-guarded `converse` | `src/qualor/runtime/agent.py`, `runtime/budget.py` | VERIFIED |
| Deterministic engines, no model in the decision path | `src/qualor/{eligibility,matching,conflicts,effort,strategy,decisions}` | VERIFIED |
| 1050 / 312 / 27 tests green | `scripts/verify.ps1`, `npm run test:e2e` | VERIFIED |
| 42 exported schemas generate frontend types | `schemas/`, `apps/web/src/generated/domain.ts` | VERIFIED |
| Version-bound, expiring, single-use approval | `src/qualor/workspace/approval.py` | VERIFIED |
| No external submission path exists | repository-wide; asserted in browser tests | VERIFIED |
| LIVE / REPLAY / FIXTURE fail-closed | `src/qualor/runtime/mode.py` | VERIFIED |
| Real-source run returned PREPARE | `.qualor/local/killer-demo-real-source/task2c-result.json` | VERIFIED |
| AgentCore **runtime deployment** | none exists | NOT CLAIMED |
| Live hosted demo | none exists | NOT CLAIMED |
| Creator / studio verticals | not built | MARKED FUTURE |
