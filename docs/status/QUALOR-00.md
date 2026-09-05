# QUALOR-00 — Repository Bootstrap & Capability Preflight

Date: 2026-09-05. Scope: QUALOR-00, resumed by QUALOR-00A. `STATUS=PASS` for the repository bootstrap. External AWS access and BDB registration remain explicitly blocked below. This document records the verified implementation checkpoint; the final Result Packet reports the exact final documentation commit and its repeated verification.

## Canonical import

- `CANONICAL_SOURCE_VERIFICATION=PASS`
- `CANONICAL_IMPORT=PASS`
- `CANONICAL_HASH_MATCH=PASS`
- SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`
- Size: `62438` bytes.
- Source, destination and staged Git blob matched the owner-provided fingerprint. The owner confirmed the download filename suffix was not part of canonical identity. `.gitattributes` preserves the original bytes.

## Installed and exercised tools

| Tool/package | Version |
| --- | --- |
| Git | 2.53.0.windows.1 |
| GitHub CLI | 2.96.0 |
| Python in uv environment | 3.12.14 |
| System Python | 3.12.10 |
| uv | 0.12.5 |
| Pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| FastAPI | 0.141.1 |
| Uvicorn | 0.52.4 |
| Typer | 0.27.2 |
| Strands Agents SDK | 1.54.0 |
| boto3 / botocore | 1.43.89 |
| HTTPX | 0.28.1 |
| pytest | 9.1.1 |
| pytest-cov | 7.1.0 |
| Ruff | 0.16.6 |
| Node | 24.13.0 |
| npm | 11.6.2 |
| React / React DOM | 19.2.8 |
| TypeScript | 7.0.2 |
| Vite | 8.2.2 |
| Tailwind CSS / Vite plugin | 4.3.3 |
| AWS CLI | BLOCKED_NOT_INSTALLED |

Python dependencies are resolved in `uv.lock`; frontend versions are exact in `apps/web/package.json` and `package-lock.json`. Strands is installed; no Strands agent has been instantiated or run. Build tools follow official [uv locked-sync documentation](https://docs.astral.sh/uv/concepts/projects/sync/), [Vite setup](https://vite.dev/guide/) and [Tailwind Vite installation](https://tailwindcss.com/docs/installation/using-vite).

## Behavioral verification

| Command/check | Result | Exit |
| --- | --- | --- |
| `uv lock`, `uv sync --locked` | PASS | 0 |
| Health test before implementation | RED: missing `qualor.api`, 1 failed | 1 |
| Health test after implementation | GREEN: 1 passed | 0 |
| Doctor/settings tests before implementation | RED: missing CLI/settings, 8 failed | 1 |
| `uv run pytest -q` after implementation | PASS: 9 passed | 0 |
| `uv run qualor doctor` | Required six bootstrap status lines | 0 |
| `uv run ruff check .` | PASS | 0 |
| `npm --prefix apps/web ci` | PASS; npm reported 0 vulnerabilities | 0 |
| `npm --prefix apps/web run build` | PASS, includes `tsc --noEmit` | 0 |
| Preflight output regression | Duplicate local blocker reproduced RED, corrected GREEN | 1 / 0 |
| Discovery false-positive regression | RED: 2 failed, 3 passed; GREEN: 5 passed | 1 / 0 |
| `uv run pytest -q` after discovery correction | PASS: 14 passed | 0 |
| Browser shell inspection | Required copy and badge visible; no application console errors | PASS |
| Independent read-only review after correction | No remaining blocking findings; 14 tests and Ruff pass | 0 |

Health uses HTTPX ASGITransport to test the real in-process app. The installed Starlette TestClient emits an HTTPX deprecation warning; using HTTPX directly avoids adding an unrequested HTTP client or suppressing warnings. Doctor tests deny socket connections and AWS client creation and verify missing/modified canonical bytes, incompatible Python, safe settings and rejected live enablement. No test requires AWS credentials.

Initial `scripts/verify.ps1` passed sync, Ruff, pytest, doctor, frontend install/build, canonical/secret-pattern scan and whitespace gates, then correctly returned exit 1 because the implementation was staged but uncommitted. Raw RED/GREEN logs are ignored under `.qualor/local/`.

Independent review reproduced an incorrect discovery PASS when a custom inference profile merely had a Sonnet 4.6 label. The corrected expression inspects authoritative foundation `modelId` and inference-profile `models[].modelArn` only. Five synthetic regression cases execute that actual expression without SDK startup or network calls; they are not evidence of AWS access. Browser inspection showed only the requested static shell and no application errors; unrelated browser-extension warnings were excluded from the application result.

## Git and GitHub

- Project root: `C:\PROJECTS\qualor`; initially empty, no files overwritten.
- Default branch: `main`.
- First canonical/root/governance commit: `bae6df2b8a6c189b7c9d3d5901236f46707ade7c`.
- Task branch: `qualor-00-bootstrap`, created from that baseline.
- `HEAD_BEFORE=NONE` at task start; implementation starts at the baseline above.
- Remote: `https://github.com/brenychstudio/qualor.git`.
- Owner authenticated as `brenychstudio`; repository absence confirmed before creation.
- `REMOTE_VISIBILITY=PRIVATE`; `ORIGIN=CONFIGURED`; `MAIN_PUSHED=YES`.
- `main` remote SHA matched the baseline. No Pages, deployment, repository secrets or visibility change configured.
- Final task SHA is reported using `git rev-parse HEAD` in the Result Packet, avoiding a self-referential committed hash.
- Implementation commit: `23d51a2e3a890f2d441731593529a2667d79dd28`, pushed to the task branch.
- PR: [QUALOR-00: Bootstrap repository and capability preflight](https://github.com/brenychstudio/qualor/pull/1), OPEN, base `main`, head `qualor-00-bootstrap`, `mergedAt=null` when checked. `PR_CREATED=YES`; `PR_MERGED=NO`.

## Final verification checkpoint

Verified implementation commit: `23d51a2e3a890f2d441731593529a2667d79dd28`. Subsequent checkpoint changes only record results, mark plan execution and document Windows verification setup. The final Result Packet identifies and verifies the final HEAD.

| Gate | Result | Exit |
| --- | --- | --- |
| `powershell -NoProfile -File scripts/verify.ps1` | PASS on clean committed tree | 0 |
| Independent `uv run ruff check .` | PASS | 0 |
| Independent `uv run pytest -q` | PASS, 14 tests | 0 |
| Independent `npm --prefix apps/web ci` | PASS | 0 |
| Independent `npm --prefix apps/web run build` | PASS, including TypeScript | 0 |
| `git diff --check`, `git diff --cached --check` | PASS | 0 |
| Canonical and tracked secret-pattern audit | PASS | 0 |
| `git status --short` | Empty; WORKTREE=CLEAN | 0 |
| Temporary Ruff failure probe | Correctly failed at Ruff, probe removed | 1 |
| Temporary untracked-file probe | Correctly failed clean-tree gate, probe removed | 1 |
| GitHub push CI on implementation commit | [PASS](https://github.com/brenychstudio/qualor/actions/runs/33963242324) | success |

A verification attempt while the inspection dev server was still running failed with Windows EPERM at `npm ci`, correctly propagated as nonzero. Stopping that task-owned server released its native dependency file lock; the full script then passed. README now documents stopping the frontend dev server before verification on Windows. No deletion or permission change was used to bypass the lock.

`VERIFY_SCRIPT=PASS`; `SECRETS_SCAN=PASS`; `PROPRIETARY_CODE_IMPORTED=NO`. Manual provenance review found only newly authored bootstrap code, dependency lock metadata and the approved canonical import. No unrelated product code, credentials, runtime state or external rules-page copies are tracked. Known AWS/BDB blockers remain separate from these local results.

## AWS capability state

```text
AWS_CLI=BLOCKED_NOT_INSTALLED
AWS_STS=BLOCKED
BEDROCK_CONTROL_PLANE=BLOCKED
SONNET_4_6_DISCOVERY=BLOCKED
SONNET_4_6_INFERENCE=NOT_TESTED
AGENTCORE_CONTROL_PLANE=BLOCKED
AGENTCORE_WEB_SEARCH=UNVERIFIED
AWS_PAID_SMOKE=NOT_RUN_BY_POLICY
AWS_RESOURCES_CREATED=0
AWS_ESTIMATED_TASK_COST=0_USD
```

Installed botocore models support `GetCallerIdentity`, `ListFoundationModels`, `ListInferenceProfiles` and `ListAgentRuntimes`. In `us-east-1`, all four attempted reads were blocked by `NoCredentialsError` from the standard SDK credential chain. No account identifiers, credential values or ARNs are recorded here. CLI absence is reported separately from SDK access. Preflight exits 1 for unavailable tools/access; it is not part of the offline verification gate.

Only the explicit read-operation allowlist is callable by preflight. SDK timeouts and retries are bounded, inference-profile pagination is bounded, and incomplete discovery remains BLOCKED. Model listing would establish discovery only, never invocation permission. API references: [foundation models](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock/client/list_foundation_models.html), [inference profiles](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock/client/list_inference_profiles.html), [AgentCore runtime list](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore-control/client/list_agent_runtimes.html).

The cost estimate covers this task's AWS actions only: no paid service was invoked and no resources were created. It is not an account billing audit or promotional-credit coverage verification.

## BDB registration

`BDB_REGISTRATION=BLOCKED_NO_DOCUMENTED_OPERATOR_PATH`

Target: `workspaceId=ws_qualor`, `projectId=qualor`, `displayName=QUALOR`, repository `C:\PROJECTS\qualor`.

Discovery was timeboxed to five minutes. Read-only inspection covered BDB README workspace persistence/runtime documentation, BDB-01 project registry acceptance, BDB-00 bootstrap documentation and registration-related documentation search. These describe automatic startup registration of predefined canonical projects, but no documented operator command for registering this new repository. Available BDB connector operations expose workspace reads and staged task/source proposals, not registration. No BDB source, database or state was changed; no proprietary implementation was imported.

## Scope and known blockers

External blockers: AWS CLI absent; AWS credentials unavailable to this session; BDB has no discovered documented registration path. These do not authorize cloud configuration changes or custom BDB registration formats.

Implemented surface: one health route, offline doctor, bootstrap settings, static frontend, locks, CI and local scripts. `LIVE_AGENT=NOT_IMPLEMENTED`; `AGENTCORE_RUNTIME=NOT_DEPLOYED`; `PROPRIETARY_CODE_IMPORTED=NO`.

Deferred: domain/profile implementation, evidence/persistence, eligibility/strategy/decision/conflict engines, source fetching/search, Strands behavior/tools, AgentCore Gateway/Web Search/Runtime, storage, approval/draft packs, real dashboard, notifications, scheduler, browser automation, authentication, billing, external submission, public/cloud deployment, competition submission, video and blog posts. QUALOR-01 has not begun.
