# QUALOR

**Autonomous Opportunity Intelligence**

Find what qualifies. Pursue what matters.

## What QUALOR is

QUALOR is autonomous opportunity intelligence for founders and small technology or creative teams. It discovers opportunities, verifies evidence and blockers against real project constraints, and prepares the next decision for human approval.

This describes the intended product. The authoritative specification is [the canonical brief](docs/00_CANONICAL_BRIEF_UA.md).

## Current development status

**Early development / AWS Agents for Humans 2026 build**

QUALOR-00 establishes the development foundation: a health endpoint, an offline doctor, a static frontend shell, dependency locks and verification. Product discovery, agents and cloud deployment are not implemented. See [bootstrap status](docs/status/QUALOR-00.md) for measured results.

## Architecture direction

Python 3.12, Pydantic v2 and FastAPI form the backend foundation. Strands Agents SDK is installed for later tasks. React, TypeScript, Vite and Tailwind v4 form the frontend foundation. Future deterministic controls and evidence handling follow the canonical brief. Live AgentCore integration belongs to later tasks.

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

```powershell
.\scripts\verify.ps1
.\scripts\preflight.ps1
```

Verification includes a clean Git worktree gate, so commit intended changes before the final run. Preflight performs separate read-only AWS metadata checks; missing access is reported as blocked. Its detailed output stays in ignored `.qualor/local/`. The doctor and CI do not contact AWS.

## Safety boundaries

No paid inference, live search, cloud provisioning or external application submission exists in this bootstrap. Discovery of model metadata does not prove inference permission. FIXTURE, REPLAY and LIVE must remain distinct in future work. Keep credentials, `.env` and runtime data out of Git. The repository remains private until explicitly authorized otherwise.

## License

[MIT](LICENSE), copyright 2026 Rostyslav Brenych.
