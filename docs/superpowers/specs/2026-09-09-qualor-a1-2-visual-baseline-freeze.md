# QUALOR A1.2 Spatial Precision — frozen visual baseline

Owner decision recorded by `QUALOR-04A-TASK-07R3-CLOSE`, 2026-09-09.

```text
OWNER_VISUAL_ACCEPTANCE=PASS
APPROVED_VISUAL_DIRECTION=A1.2_SPATIAL_PRECISION
A1_2_SPATIAL_PRECISION_BASELINE=FROZEN
REDESIGN_ALLOWED=NO
```

The owner explicitly accepted the current FIX2.1 browser result as the
canonical QUALOR A1.2 visual baseline. This decision supersedes earlier
pending/rejected visual checkpoint statuses and conflicting visual directions
in the [07R correction](2026-09-08-qualor-04a-task-07r-spatial-correction.md)
and [Spatial Precision specification](2026-09-08-qualor-04a-spatial-precision-design.md).
Those documents retain the history and context of the correction. The
canonical product brief and deterministic product authority remain unchanged.

## Accepted visual system

- Dark blue-carbon decision workspace and Opportunity Inbox.
- Four causal decision signals converging into a rectangular recommendation
  surface.
- Light Evidence Plane and quiet Intelligence rail.
- Decision Trace and concise Next Actions.
- Restrained premium optical treatment, including the approved typography,
  material contrast, signal paths and rectangular recommendation geometry.
- No orb, polygon, ring or decorative sci-fi centerpiece. Existing small
  signal icons do not authorize a new centerpiece or visual metaphor.

Future work may extend this system. Replacing or reinterpreting it requires
explicit owner authorization. This closure authorizes no further polish.

## Frozen frame and implementation boundary

The accepted frame is the development-only D02 synthetic preview at exactly
1440 × 810, captured as `fix2-1-final-1440x810.png`.
Its SHA-256 is:

```text
80b553b9693f7f27eae8a7138d7253a17655cb3738ba4a4ec315910171f10100
```

The approved presentation is implemented by `apps/web/src/dev/DecisionPreview.tsx`,
`apps/web/src/dev/decision-optical.css` and the shared workspace frame, styles
and local font assets. The existing preview opt-in remains restricted to this
frame and scenario. Screenshots and machine verification reports stay in the
ignored local QA area; they are not production data.

The populated proof remains visibly synthetic and read-only. It does not
authorize LIVE claims, invented evidence, numeric eligibility confidence,
approval actions or external submission. Product business rules, API/security
contracts, migrations and AWS infrastructure are outside this closure.

## Closure and follow-on boundary

This closure records and commits the complete approved accumulated Task 7
visual work after fresh technical verification. It does not propagate the
frozen desktop frame to Portfolio, tablet, mobile or empty state. Existing
earlier presentation work in those surfaces is retained without new changes.

Task 8, visual propagation, new visual exploration and backend feature work
must wait until the owner reviews the close packet. No push is authorized.
