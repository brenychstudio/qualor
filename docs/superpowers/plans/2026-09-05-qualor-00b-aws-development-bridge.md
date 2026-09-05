# QUALOR-00B AWS Development Bridge Implementation Plan

> **For agentic workers:** Execute this owner-authorized plan with Superpowers TDD and verification. Independent review is limited to the bridge safety boundary.

**Goal:** Enable a named temporary AWS development identity and one pinned, read-only managed AWS MCP connection, with truthful capability evidence and no resource creation or paid AWS calls.

**Architecture:** Official AWS CLI v2 browser login supplies `qualor-dev` credentials outside the repository. A local guarded launcher starts the pinned SigV4 MCP Proxy for the documented managed endpoint. CLI preflight supplies independent read-only control-plane evidence. Root credentials never reach the proxy.

**Tech stack:** Existing Python 3.12/uv, PowerShell, AWS CLI v2 >=2.35.0, Codex CLI, mcp-proxy-for-aws-cli==1.6.5 (official release reviewed; transitive pins included).

**Spec:** [Canonical brief](../../00_CANONICAL_BRIEF_UA.md) and owner task QUALOR-00B. Baseline `021f9b85b9cee26020b6e2217218f4655d2a0f75`. Canonical SHA-256 `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`.

## Constraints

- Work only on `qualor-00b-aws-development-bridge`; no QUALOR-01 behavior.
- Region `us-east-1`, profile `qualor-dev`, MCP entry `aws-qualor`.
- Preserve existing AGENTS rules, AWS profiles and unrelated Codex MCP entries.
- No permanent keys, IAM identity creation, AWS resources, inference or Web Search execution.
- Login/cache/config stay under the user profile. Raw local diagnostics stay ignored under `.qualor/local/`; no account IDs, private ARNs or credential values in tracked files or reports.
- Root identity blocks authenticated automation. Missing/expired authentication never becomes PASS.
- Official endpoint: `https://aws-mcp.us-east-1.api.aws/mcp`, verified against current Agent Toolkit documentation before configuration.

## 1. Baseline and local inventory

- [x] Verify clean main, exact expected baseline and canonical hash; run `scripts/verify.ps1` successfully (14 tests).
- [x] Create task branch and inspect sanitized local state: CLI absent, no AWS config/credentials, no AWS MCP server or Agent Toolkit setup found. Existing unrelated MCP entries are preserved.

## 2. Supported tool installation and login

**Local changes:** Official AWS CLI per-user installation; AWS profile config/login cache; uvx proxy cache. No tracked credential files.

- [x] Verify official AWS installation/login documentation and proxy GitHub/PyPI release metadata. Pin supported proxy release; record any documentation discrepancy in ADR.
- [x] Download the official per-user Windows installer outside the repository, verify Authenticode publisher/status, prepare installation without reboot (automatic installer execution blocked; owner installed the verified MSI), verify `aws --version`, `aws login help`, `aws agent-toolkit help`.
- [x] Launch `aws login --profile qualor-dev --region us-east-1`, request owner browser completion only if needed, and wait while continuing independent repository work.
- [x] Capture STS output privately in memory; normalize identity type and temporary-credential provider. Do not export credentials or copy caches. If ROOT, stop authenticated automation and configure only isolated unauthenticated knowledge access where supported.

## 3. CLI preflight and guarded MCP launcher, RED/GREEN

**Files:** `scripts/aws-preflight.ps1`, `scripts/aws_bridge.py`, `scripts/aws-mcp.ps1`, `tests/test_aws_bridge.py`.

**Interfaces:** `aws_bridge.py` exposes sanitized preflight and guarded proxy launch via command-line entry points. PowerShell wrappers resolve repository paths and propagate nonzero status. AWS CLI commands always specify `--profile qualor-dev`, `--region us-east-1`, disabled pager and bounded network timeouts. No product module imports this utility.

- [x] RED: test version/profile/config validation; classify root/user/role/federated identities without emitting identity values; reject static/unknown credentials and root before proxy/API use; exercise model discovery using authoritative identifiers, not profile labels; reject unpinned/incorrect/read-write MCP configuration.
- [x] GREEN: implement minimal subprocess-based CLI adapter and deterministic normalization. Only STS identity, Bedrock list operations and supported AgentCore list operations may reach AWS. Offline tests supply subprocess responses, never network calls or simulated live status evidence.
- [x] Test fail-closed subprocess errors and the safe launch argument contract: pinned proxy, one profile, `--read-only`, signing region and `AWS_REGION` metadata. Strip inherited credential/profile-switch overrides so the named profile is authoritative.
- [x] Run `uv run pytest tests/test_aws_bridge.py -q` and Ruff; record RED/GREEN evidence locally.

## 4. Local Codex MCP configuration and smoke

**Local change:** Add only `aws-qualor` to Codex config via supported CLI; use guarded launcher and explicit non-secret environment settings. No duplicate legacy servers.

- [x] Verify installed proxy CLI and actual read-only enforcement implementation. Configure exactly one QUALOR MCP entry, with pinned version and read-only flag enforced in launcher.
- [x] Inspect `codex mcp list --json` through a sanitizer; confirm enabled entry and expected command/environment. Preserve unrelated servers byte-for-byte where the CLI permits.
- [x] Use a new `codex exec` process with a harmless knowledge-only prompt and read-only sandbox. Restrict smoke to `aws-qualor`; collect private JSONL locally, then report tool names/result statuses only.
- [x] Independently inspect MCP tool discovery; verify every exposed tool has `readOnlyHint=true` and write-capable API/script tools are absent or blocked. Do not call a write tool to test it against AWS.
- [x] If fresh Codex smoke cannot run, record CONFIGURED_RESTART_REQUIRED or the actual connection blocker; never substitute a configuration check for a live connection result.

## 5. Capability documentation and project rules

**Files:** `AGENTS.md`, `docs/decisions/0002-aws-development-bridge.md`, `docs/status/QUALOR-00B.md`, this plan; `.gitignore` only if additional credential/cache exclusions are needed.

- [x] Inspect Bedrock and AgentCore control planes with the named CLI profile after non-root temporary identity verification. Record unsupported/denied operations explicitly; do not infer invocation permission from discovery.
- [x] Check canonical region assumptions against current official AWS docs; record differences in ADR without editing the canonical source.
- [x] Preserve existing AGENTS rules and add the 15 requested AWS development rules, including canonical tags `Project=QUALOR`, `Environment=hackathon`, `Owner=BrenychStudio`.
- [x] Document SigV4/read-only design, verified versions/endpoint, operator login and recovery, known blockers, single-account strategy and deferred write/IAM/deployment/inference scope.

## 6. Verification and PR checkpoint

- [x] Audit tracked files/diff for secrets, account identifiers, private ARNs, session caches and scope drift. Never commit local AWS/Codex config.
- [x] Run named-profile `scripts/aws-preflight.ps1`; expected external blockers remain explicit and nonzero.
- [x] Run existing Ruff, full pytest and frontend locked install/build; independent review of safety changes. Commit `chore: add secure AWS development bridge` after green local gates.
- [x] Run full `scripts/verify.ps1` on the clean committed tree, then independently Ruff, pytest, npm ci/build and Git diff/status. Fix only task-scoped issues and repeat affected gates.
- [x] Push task branch and create unmerged PR `QUALOR-00B: Add secure AWS development bridge` against main. Verify private visibility, exact remote HEAD and CI.
- Return the factual QUALOR-00B Result Packet and stop. Any required authentication/root blocker makes the overall status PARTIAL even if the repository utilities and unauthenticated knowledge fallback are complete.

## Execution outcome

All repository implementation and offline gates were executed. AWS CLI 2.36.40 login succeeded with ROOT; authenticated discovery and automation were therefore blocked. Direct anonymous MCP initialization, discovery and knowledge call passed. Fresh Codex 0.153.4 smoke was attempted and reported an explicit handshake failure; it is not PASS. These blockers remain factual exceptions to successful enablement, detailed in docs/status/QUALOR-00B.md. No IAM identity, resource or paid invocation was created.
