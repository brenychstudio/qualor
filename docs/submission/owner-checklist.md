# QUALOR — owner pre-submission checklist

Every item here needs a person. Nothing on this list can be completed by an agent, and nothing
on it has been completed on the owner's behalf.

**Official deadline:** Monday, September 14, 2026, 5:00 pm Pacific Time (`2026-09-15T00:00:00Z`).
**Owner's internal target:** 2026-09-13.

---

## Blocking — required by the Official Rules

| # | Item | State | Notes |
| --- | --- | --- | --- |
| 1 | **Make the repository public** | NOT DONE | `github.com/brenychstudio/qualor` is `PRIVATE`; an anonymous fetch returns 404. Required: *"Provide a PUBLIC URL to your code repository"*. |
| 2 | **Push the current branch** | NOT DONE | `origin/main` is 41 commits behind. A judge must be able to see and run the code that the video shows. |
| 3 | **Verify the AWS Builder ID** | **UNKNOWN** | Listed as a submission requirement. Cannot be checked from the repository — this is an account-side fact only the owner can confirm. Do not assume it is in place. |
| 4 | **Record and publish the demo video** | NOT DONE | Maximum 5 minutes, public on YouTube or Vimeo. Plan: [`demo-video-plan.md`](demo-video-plan.md). |
| 5 | **Write the Devpost text description** | DRAFT READY | Source: [`devpost-narrative.md`](devpost-narrative.md). Needs owner review before pasting. |
| 6 | **Attach the architecture diagram** | READY | [`docs/architecture/qualor-architecture.svg`](../architecture/qualor-architecture.svg). Verified legible at Devpost column width. |
| 7 | **Confirm the pre-existing-code disclosure** | OWNER CONFIRMED | Owner states no code or assets predating 2026-08-10 are incorporated. Re-confirm at submission time. |
| 8 | **Select the Professional Agents track** | NOT DONE | On the Devpost submission form. |

Already satisfied, verified in the repository: MIT `LICENSE` detectable by GitHub, `README`
with working local-development and testing instructions, and the project built with Strands
Agents.

## Optional — scores better, not required

| Item | State | Notes |
| --- | --- | --- |
| Live demo link | none | *"(Optional) Include a live demo link — this will help your Project score better in the Technical Implementation Judging Criteria"*. No deployment exists. |
| AgentCore runtime deployment | none | *"a smart architectural choice … but it's not required"*. AgentCore web search is used in LIVE mode; the runtime is not deployed. Do not claim otherwise. |
| `builder.aws` blog post | not written | Up to 0.6 bonus points, 0.2 each. Must be public on `builder.aws.com` before the submission deadline and use *Agents for Humans* in the title. |

## Not obtainable

| Item | Why |
| --- | --- |
| $50 AWS promotional credits | The request window closed: *"by September 11th at 12pm PT"*. |

---

## Before making the repository public

The publication audit for this commit found **no secrets** in the tracked tree and **none in
any of the 702 blobs in git history** — no AWS keys, tokens, private keys, ARNs, account IDs or
credential assignments. `.qualor/` captures, the owner's applicant facts and the real-source
profile are all gitignored and untracked.

Two hygiene items were corrected in this commit:

- a local Windows account name appeared in one historical planning note, now generalized;
- the `README` described the project as early-stage with agents *not implemented*, which was
  false and would have misled a judge. It now describes what actually exists and explains how
  to run the real decision workspace rather than only the bootstrap shell.

One thing to confirm yourself before flipping visibility: that you are comfortable publishing
the full `docs/superpowers/` planning and specification history. It contains no secrets and no
personal data, but it is a candid internal record of how the project was built — including
defects found and corrected. It is defensible and arguably a strength; it is still your call.

## Demo state decision

The truthful decision today is **PREPARE**, because items 1, 4, 5 and 6 above are the exact
readiness gaps the engine found. Once they close, re-running the decision may truthfully move
it to **APPLY**.

Either is a good demo. `PREPARE` is the more distinctive story — the agent declining to
rubber-stamp its own submission — and the video plan is written for it. Decide before
recording, because segments 4 and 9 depend on it.
