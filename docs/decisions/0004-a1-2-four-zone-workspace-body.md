# ADR 0004: QUALOR-04A A1.2 wide workspace body is a four-zone layout

Date: 2026-09-10. Status: Owner-approved. Change record:
`QUALOR-04A-A1_2-CANONICAL-RULING-01B`. Canonical specification:
`docs/00_CANONICAL_BRIEF_UA.md` (unchanged).

## Context

The QUALOR-04A design specification and implementation plan were written before the
A1.2 Spatial Precision pass. They described the wide desktop body as three zones —
supporting inbox, dominant canvas, and one combined `Live Intelligence / Evidence Rail`
carrying both contextual activity and source status.

Implementation separated those two surfaces. The owner accepted and froze the resulting
A1.2 visual baseline, in which the wide body carries a light document-material proof
plane and a dark telemetry rail as distinct zones. Canonical documentation still asserted
the earlier three-zone wording, so the documents contradicted the frozen implementation.

## Decision

`SUPERSEDED_RULE`: QUALOR-04A wide desktop is a three-zone body layout.

`NEW_RULE`: the QUALOR-04A A1.2 wide desktop body at 1280 px and above is a four-zone
layout — Opportunity Inbox, Decision Canvas, Why & Proof / Evidence Plane, Intelligence
Rail. Header and top navigation are not body zones.

`IMPLEMENTATION_SOURCE`: the owner-accepted A1.2 Spatial Precision baseline.
`IMPLEMENTATION_CHANGE_REQUIRED=NO`. `REDESIGN_ALLOWED=NO`. This ruling reconciles
canonical documentation with an already frozen implementation; it authorizes no
application change.

`RATIONALE`: Evidence/Proof and Activity/Intelligence hold separate product authority
and separate material semantics, and therefore occupy separate wide-body zones. The Why &
Proof / Evidence Plane is the authority for source-grounded evidence, citations,
uncertainty, conflicts, and proof, expressed in warm light document material. The
Intelligence Rail is the authority for persisted operational telemetry, run activity, and
runtime state, expressed in the dark intelligence workspace material. Collapsing them
into one rail merged two authorities and two materials into a single surface.

This is not a generic four-column dashboard. Decision Canvas remains dominant; Opportunity
Inbox, Why & Proof, and Intelligence Rail remain supporting. Proof remains subordinate to
the decision until invoked or contextually exposed. `Decision → Why → Proof` progressive
intelligence, the dark-workspace/light-proof material distinction, and the 85/15 visual
dominance all remain unchanged.

## Consequences

Section 3 of the design specification and the corresponding normative statements in the
implementation plan record four wide-body zones. Historical task descriptions continue to
describe what was originally planned; this record, not a rewritten history, explains the
evolution.

No product authority changes. `UNKNOWN != PASS`, strategy as prioritization rather than
win probability, recommendation and eligibility authority, `presentation_state`,
`ProductState`, `ActionCapability`, evidence/provenance authority, LIVE/FIXTURE/REPLAY
truthfulness, the human approval boundary, the prohibition on external submission, and
Draft Pack immutability are untouched. Neither the Evidence Plane nor the Intelligence
Rail owns deterministic decision policy; the deterministic engines retain it.

No production file, style, token, component, or runtime test changes under this record.
The canonical brief remains byte-for-byte unchanged.
