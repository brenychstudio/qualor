# ADR 0001: QUALOR bootstrap baseline

Date: 2026-09-05. Status: Accepted for owner-authorized QUALOR-00 scope.

## Context

QUALOR is a new repository. The [canonical brief](../00_CANONICAL_BRIEF_UA.md) establishes Python 3.12, Strands/Pydantic/FastAPI and React/TypeScript/Vite/Tailwind v4. QUALOR-00 authorizes only a reproducible foundation and read-only capability discovery.

## Decision

Use a small `src/qualor` Python package and separate `apps/web` frontend. Commit `uv.lock` and npm lockfile; use locked installs locally and in CI. The only runtime interfaces are `GET /health` and offline `qualor doctor`. Doctor verifies Python and canonical bytes without contacting providers. Reject live enablement during bootstrap.

Keep the owner-approved canonical file byte-for-byte. Git attributes disable its line-ending normalization and default textual diff; inspect changes explicitly as bytes and only with an approved change record. The canonical document contains owner-supplied planning context and is authorized for this private repository; no additional private operational information is imported.

Initialize canonical governance on `main`, then implement on `qualor-00-bootstrap`. Create a private GitHub repository and an unmerged PR. The owner-approved task supplies this authorization.

Use the installed boto3/botocore service models for read-only AWS capability discovery, including when AWS CLI is missing. Report CLI presence separately. List APIs prove control-plane access only. Do not invoke models or create resources. Detailed raw data stays in `.qualor/local/`; commit sanitized statuses only.

## Consequences

No domain, persistence, agent behavior, live integration, dashboard or deployment is included. These require later scoped tasks. Missing external access is an explicit blocker for that capability and does not convert into a simulated success. BDB registration uses only a documented operator mechanism and introduces no runtime dependency.
