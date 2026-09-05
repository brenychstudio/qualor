# QUALOR

**Autonomous Opportunity Intelligence**

Find what qualifies. Pursue what matters.

## What QUALOR is

QUALOR is autonomous opportunity intelligence for founders and small technology or creative teams. It discovers opportunities, verifies evidence and blockers against real project constraints, and prepares the next decision for human approval.

This describes the intended product. The authoritative specification is [the canonical brief](docs/00_CANONICAL_BRIEF_UA.md).

## Current development status

**Early development / AWS Agents for Humans 2026 build**

QUALOR-00 establishes the development foundation: a health endpoint, an offline doctor, a static frontend shell, dependency locks and verification. Product discovery, agents and cloud deployment are not implemented. See [bootstrap status](docs/status/QUALOR-00.md) for measured results.

QUALOR-01 adds typed domain contracts and a deterministic eligibility core, exercised only with owned synthetic fixtures. It checks evidence references, critical coverage, freshness and explicit rules, and returns PASS, FAIL or REVIEW_REQUIRED. Eligibility is not a submission recommendation. See [QUALOR-01 status](docs/status/QUALOR-01.md).

## Architecture direction

Python 3.12, Pydantic v2 and FastAPI form the backend foundation. Pydantic owns the domain contracts and exported JSON Schema. The eligibility core is pure Python and does not import AWS, network or agent clients. Strands Agents SDK is installed for later tasks. React, TypeScript, Vite and Tailwind v4 form the frontend foundation. Live AgentCore integration belongs to later tasks.

## Local development

Install Python 3.12, uv, Node (version in `.node-version`), npm and Git. From the repository root:

```powershell
uv sync --locked
uv run qualor doctor
uv run uvicorn qualor.api:app --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` reports bootstrap health. In another terminal:

```powershell
npm --prefix apps/web ci
npm --prefix apps/web run dev -- --host 127.0.0.1
```

The frontend displays the bootstrap shell. Non-secret defaults are documented in `.env.example`. Live configuration is rejected during bootstrap.

Evaluate the owned gold fixtures and regenerate domain schemas:

```powershell
uv run qualor evaluate-fixture tests/fixtures/F01_FULL_PASS.json
.\scripts\export-schemas.ps1
.\scripts\export-schemas.ps1 -Check
```

The CLI prints `MODE=FIXTURE`, `ELIGIBILITY=...` and the structured gate. `POST /dev/evaluate-fixture` accepts the same JSON envelope directly; it never accepts a filesystem path. This route returns 404 outside `QUALOR_ENV=development`. Run the API on loopback as shown above. It performs no persistence or external call. A FAIL or REVIEW_REQUIRED is a successfully evaluated fixture; malformed input exits nonzero in the CLI or returns HTTP 422 in the API.

Public APIs and policy details are documented in the [implementation plan](docs/superpowers/plans/2026-09-05-qualor-01-domain-eligibility-core.md). The eight generated files in `schemas/` describe serialized contracts; Pydantic runtime validators also enforce cross-field semantics. TypeScript code generation is deferred to QUALOR-02; no duplicated frontend domain interfaces are maintained.

```powershell
.\scripts\verify.ps1
.\scripts\preflight.ps1
```

Verification includes a clean Git worktree gate, so commit intended changes before the final run. Stop the frontend dev server first on Windows: `npm ci` reinstalls native packages that the running server can lock. Preflight performs separate read-only AWS metadata checks; missing access is reported as blocked. Its detailed output stays in ignored `.qualor/local/`. The doctor and CI do not contact AWS.

## Safety boundaries

No paid inference, live search, cloud provisioning or external application submission exists in this bootstrap. Discovery of model metadata does not prove inference permission. FIXTURE, REPLAY and LIVE must remain distinct in future work. Keep credentials, `.env` and runtime data out of Git. The repository remains private until explicitly authorized otherwise.

## License

[MIT](LICENSE), copyright 2026 Rostyslav Brenych.
