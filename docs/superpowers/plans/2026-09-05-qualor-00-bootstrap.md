# QUALOR-00 Bootstrap Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to execute this owner-approved task in order. Use independent review after implementation. Checkboxes record completed steps.

**Goal:** Establish a reproducible private QUALOR repository and truthful, zero-paid-usage capability baseline, ready for owner review before QUALOR-01.

**Architecture:** A Python package exposes only a FastAPI health endpoint and an offline Typer doctor. A separate React application renders a static bootstrap shell. PowerShell verification and capability scripts remain development utilities; no agent or product workflow is implemented.

**Tech Stack:** Python 3.12, uv, Pydantic v2, pydantic-settings, FastAPI, Uvicorn, Typer, Strands Agents SDK, boto3, HTTPX, pytest, pytest-cov, Ruff; React, TypeScript, Vite, Tailwind v4, npm.

**Spec:** [Approved canonical source](../../00_CANONICAL_BRIEF_UA.md), owner execution instructions QUALOR-00 and fingerprint clarification QUALOR-00A (2026-09-05).

## Global constraints

- Project root `C:\PROJECTS\qualor`; new code only; no proprietary imports.
- Python baseline `3.12`; repository slug `qualor`; GitHub owner `brenychstudio`.
- Source SHA-256 `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`; size `62438` bytes. Preserve canonical bytes, including line endings, in Git.
- Repository remains PRIVATE. PR targets `main` and is never merged by this task.
- `UNKNOWN != PASS`; no fixture/replay/live conflation; live mode disabled.
- No paid inference, Web Search, AWS provisioning, AWS configuration changes, credential publication, or external application submission.
- Detailed machine reports belong only in ignored `.qualor/local/`.
- Owner already authorized implementation, private repository creation, pushes, PR creation, and documented BDB registration. No additional design or publishing approval is needed for this scope.

## Task 1: Canonical and governance baseline

**Files:** `docs/00_CANONICAL_BRIEF_UA.md`, this plan, `.gitignore`, `.gitattributes`, `.editorconfig`, `.python-version`, `.env.example`, `AGENTS.md`, `LICENSE`, `README.md`, `docs/decisions/0001-bootstrap-baseline.md`.

**Interfaces:** Canonical file is immutable input; README supplies local commands; AGENTS supplies future implementation rules. `.gitattributes` disables canonical text normalization so hashes survive checkout.

- [x] Inspect the existing empty directory; verify source hash and size; copy byte-for-byte and recheck destination.
- [x] Write root foundation and ADR describing the limited bootstrap scope and dependency locking.
- [x] Initialize Git and inspect identity: `git init -b main`, `git status --short`, `git config user.name`, `git config user.email`.
- [x] Audit staged foundation, canonical hash, and `git diff --cached --check`. Preserve canonical formatting; do not rewrite it to satisfy generic whitespace rules.
- [x] Commit `chore: initialize QUALOR canonical repository`; capture `git rev-parse HEAD` as MAIN_BASELINE_COMMIT.
- [x] Inspect `gh auth status` without publishing token output; inspect `gh api repos/brenychstudio/qualor`. Create only on confirmed absence: `gh repo create brenychstudio/qualor --private --description "QUALOR — Autonomous Opportunity Intelligence" --source . --remote origin --push`. Verify private visibility and main remote SHA. If authentication is blocked, finish local work.
- [x] Create `git switch -c qualor-00-bootstrap` at the canonical baseline; work in the explicitly requested root, with no extra worktree.

## Task 2: Dependency environment

**Files:** `pyproject.toml`, `uv.lock`, `src/qualor/__init__.py`.

**Interfaces:** Distribution `qualor`, CLI entry point `qualor = qualor.cli:app`; `requires-python = ">=3.12,<3.13"`; package in `src/qualor`. Development group contains pytest, pytest-cov, Ruff. No imported or instantiated Strands agent.

- [x] Create packaging metadata with hatchling build backend and required runtime/development dependencies, bounded to required major versions where mandated.
- [x] Resolve current stable compatible packages with `uv lock`; install using `uv sync --locked`; record installed metadata through `importlib.metadata.version` and `uv run python --version`.
- [x] Keep Ruff target `py312` and pytest `testpaths = ["tests"]`.

## Task 3: Health endpoint RED/GREEN

**Files:** `tests/test_api_health.py`, `src/qualor/api.py`.

**Interfaces:** `qualor.api.app: FastAPI`; `GET /health` returns HTTP 200 and exactly the owner-defined JSON object. No network provider initialization.

- [x] RED: write the contract test before the implementation:

```python
def test_health_returns_bootstrap_status():
    import asyncio
    from httpx import ASGITransport, AsyncClient
    from qualor.api import app

    async def request():
        async with AsyncClient(transport=ASGITransport(app), base_url='http://qualor') as client:
            return await client.get('/health')
    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json() == {"service": "qualor", "status": "ok", "phase": "bootstrap"}
```

- [x] Run `uv run pytest tests/test_api_health.py -q`; record failure due to missing `qualor.api` inside the test, not a dependency/configuration failure.
- [x] GREEN: implement `app = FastAPI()` and `@app.get("/health")` returning the literal contract. Disable unnecessary documentation routes for the minimal bootstrap surface.
- [x] Run the same test and record exit 0.

## Task 4: Offline doctor and safe settings RED/GREEN

**Files:** `tests/test_cli_doctor.py`, `src/qualor/cli.py`, `src/qualor/settings.py`.

**Interfaces:** `qualor.cli.app: typer.Typer`; `doctor() -> None`. `Settings` reads `QUALOR_ENV=development`, `QUALOR_LIVE_ENABLED=false`, `AWS_REGION=us-east-1`; true live configuration is rejected because no live behavior exists. Canonical verification uses the approved hash, not file presence alone.

- [x] RED: invoke `CliRunner().invoke(app, ["doctor"])` while denying socket connections and boto3 session client creation. Require exit 0 and all six lines: `QUALOR`, `PHASE=bootstrap`, `PYTHON=PASS`, `CANONICAL=PASS`, `LIVE_MODE=DISABLED`, `PAID_AWS_CALLS=DISABLED`. Run from a temporary working directory to verify repository-relative canonical lookup.
- [x] Add negative cases: missing or altered canonical bytes cause `CANONICAL=BLOCKED` and nonzero exit; incompatible Python causes `PYTHON=BLOCKED`; `QUALOR_LIVE_ENABLED=true` is rejected. Assert safe defaults and environment override for region through real settings.
- [x] Run `uv run pytest tests/test_cli_doctor.py -q` and record failures caused by absent CLI/settings modules.
- [x] GREEN: implement minimal offline doctor, hash comparison, Python version check and Pydantic Settings validation. Include a Typer callback so `qualor doctor` is an explicit subcommand. No product commands.
- [x] Run `uv run pytest -q` then `uv run qualor doctor` and `uv run ruff check .`; record passing output.

## Task 5: Static frontend

**Files:** `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/index.html`, `apps/web/tsconfig.json`, `apps/web/vite.config.ts`, `apps/web/src/main.tsx`, `apps/web/src/index.css`, `.node-version`.

**Interfaces:** `npm --prefix apps/web run dev`, `run typecheck` (`tsc --noEmit`), `run build` (`npm run typecheck && vite build`). Vite uses React and Tailwind v4 plugins. Browser has no backend, AWS or external-service call.

- [x] Resolve stable compatible React/React DOM and development packages TypeScript, Vite, React plugin/types, Tailwind v4/Vite plugin; save exact versions and npm lockfile. Record tested Node/npm versions and pin Node version for CI.
- [x] Render one semantic `main` with `QUALOR`, `Autonomous Opportunity Intelligence`, `Development foundation ready.`, and visible `BOOTSTRAP` badge. Use simple responsive neutral styling and system fonts.
- [x] Run `npm --prefix apps/web ci`, `npm --prefix apps/web run typecheck`, `npm --prefix apps/web run build`. Inspect produced HTML/CSS and shell if browser access is available.

## Task 6: Verification, CI and read-only capability discovery

**Files:** `scripts/verify.ps1`, `scripts/preflight.ps1`, `.github/workflows/ci.yml`, `tests/test_preflight.py`.

**Interfaces:** PowerShell scripts run from repository root even when invoked elsewhere. `verify.ps1` fails nonzero on gate failure or dirty worktree. Preflight prints normalized statuses only, returns nonzero if access is blocked, and saves detailed output only under `.qualor/local/`.

- [x] Implement verify gates: `uv sync --locked`; Ruff; pytest; doctor; `npm ci`; typecheck/build; canonical hash; tracked credential-pattern and forbidden-file scan; `git diff --check`; `git diff --cached --check`; clean `git status --porcelain`.
- [x] Implement CI with checkout, Python 3.12, pinned uv, Node from `.node-version`, dependency installation, Ruff, pytest, doctor and frontend build. No AWS credentials, calls or deployment. Use pinned supported major action versions and minimal read-only contents permissions.
- [x] Preflight checks local tool presence/versions. Inspect installed botocore operation models before calling APIs. Use only STS `GetCallerIdentity`, Bedrock `ListFoundationModels` and supported `ListInferenceProfiles`, AgentCore control-plane `ListAgentRuntimes` if supported; region `us-east-1`. Validate result structure. Discovery must not imply inference access.
- [x] Catch capability errors into BLOCKED/UNAVAILABLE; report Sonnet 4.6 PASS only on matching model/profile metadata. Preserve `SONNET_4_6_INFERENCE=NOT_TESTED`, `AGENTCORE_WEB_SEARCH=UNVERIFIED`, `AWS_PAID_SMOKE=NOT_RUN_BY_POLICY`, `AWS_RESOURCES_CREATED=0`.
- [x] Review correction: RED reproduced two false-positive Sonnet results from custom profile labels. GREEN now matches authoritative model identifiers only; five isolated metadata regressions pass. These tests establish no live capability.
- [ ] Test verification failure propagation with a temporary untracked sentinel, then remove only that file. Exercise preflight with installed SDK; missing AWS CLI is a tool blocker, not a reason to simulate AWS results.

## Task 7: BDB operator path, review and final Git checkpoint

**Files:** `docs/status/QUALOR-00.md`; update this plan checkboxes and factual README/ADR as needed. Local-only logs: `.qualor/local/`.

**Interfaces:** Registration target `workspaceId=ws_qualor`, `projectId=qualor`, `displayName=QUALOR`, `repository=C:\PROJECTS\qualor`.

- [x] Timebox BDB operator documentation discovery to five minutes, read-only. Use only documented registration/bootstrap commands; validate workspace if supported. Do not read or copy proprietary implementation, patch BDB or edit opaque state. Otherwise report `BLOCKED_NO_DOCUMENTED_OPERATOR_PATH`.
- [x] Record canonical hash, installed versions, exact baseline SHA, task branch, commands/exit codes/counts, sanitized AWS/BDB/remote state, blockers and deferred items in status. No self-referential final commit hash: identify final checkpoint with `git rev-parse HEAD` and final Result Packet.
- [x] Independently review requirements, code, boundary behavior, secret patterns and Git diff; resolve concrete findings only within bootstrap scope.
- [ ] Commit `chore: bootstrap QUALOR development foundation`; run `.\scripts\verify.ps1` on clean committed tree. If a gate fails, fix and commit, then repeat affected gates and full final verification.
- [ ] Independently rerun `uv run ruff check .`, `uv run pytest -q`, `npm --prefix apps/web ci`, `npm --prefix apps/web run build`, `git diff --check`, `git status --short` as explicitly required by owner.
- [ ] Push task branch if available. Write exact PR body to ignored local file; `gh pr create --base main --head qualor-00-bootstrap --title "QUALOR-00: Bootstrap repository and capability preflight" --body-file .qualor/local/pr-body.md`. Verify PR remains open/unmerged, remote private, baseline and task SHAs, clean worktree. Observe CI result.
- [ ] Return one complete QUALOR-00 Result Packet; stop before QUALOR-01.

## Explicitly deferred

Opportunity/domain/profile implementation; evidence storage; eligibility, strategy, decision and conflict engines; search/fetch; Strands behavior/tools; AgentCore Gateway/Web Search/Runtime; storage/databases; approval/draft packs; dashboard, notification, scheduler, automation, authentication, billing, submissions; public or cloud deployment; video/blog/competition submission. Installing dependencies and inspecting control-plane metadata do not implement any of these.
