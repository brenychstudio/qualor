# QUALOR-03A Capability Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a fail-closed local runtime and least-privilege AWS permission gate before QUALOR can perform paid inference or create AgentCore resources.

**Architecture:** Runtime modes and live provider interfaces form a local capability boundary. A per-run budget guard reserves calls and estimated cost before provider use, while a separate AWS permission gate rejects root, long-term credentials, and missing capabilities. AWS IAM files are review-only templates derived from current control-plane discovery and official service authorization data.

**Tech Stack:** Python 3.12, Pydantic-independent typed runtime contracts, pytest, AWS CLI v2, boto3/botocore service models, JSON IAM examples.

**Spec:** `docs/00_CANONICAL_BRIEF_UA.md` and owner-approved task `QUALOR-03A`

## Global Constraints

- Keep `FIXTURE`, `REPLAY`, and `LIVE` distinct; only `LIVE` can receive live providers.
- Provider output cannot set eligibility or recommendation; deterministic engines remain authoritative.
- Cap each run at 3 inference calls, 5 searches, 10 fetched documents, and USD 2.00 reserved cost.
- Do not mutate IAM, create AWS resources, invoke Web Search, or perform paid model inference in this gate.
- Use `qualor-dev` in `us-east-1` and reject root or long-term credentials.
- Commit no account IDs, private ARNs, tokens, or credentials.

---

### Task 1: Runtime modes and provider boundaries

**Files:**
- Create: `src/qualor/runtime/mode.py`
- Create: `src/qualor/runtime/providers.py`
- Create: `src/qualor/runtime/__init__.py`
- Test: `tests/runtime/test_runtime_gate.py`
- Test: `tests/runtime/test_providers.py`

**Interfaces:**
- Produces: `RuntimeMode`, `RuntimeBoundary.open`, `LiveProviders`, `ModelProvider`, `SearchProvider`, `SourceFetcher`.
- Guarantees: fixture/replay reject live providers; live requires an explicit provider bundle; provider results have no final decision fields.

- [ ] **Step 1: Write failing tests for C01-C03 and C08.**
- [ ] **Step 2: Run `uv run pytest tests/runtime/test_runtime_gate.py tests/runtime/test_providers.py -q` and verify import failures.**
- [ ] **Step 3: Implement the minimal enums, immutable request/result types, protocols, and boundary constructor.**
- [ ] **Step 4: Run the focused tests and verify PASS.**

### Task 2: Per-run call and cost budget

**Files:**
- Create: `src/qualor/runtime/budget.py`
- Test: `tests/runtime/test_budget.py`

**Interfaces:**
- Produces: `LiveCallKind`, `LiveBudgetPolicy`, `LiveBudgetGuard.reserve`, `BudgetLimitExceeded`.
- Defaults: inference=3, search=5, fetch=10, cost=`Decimal("2.00")`.

- [ ] **Step 1: Write failing tests for C04-C06 and C10, including state unchanged after a rejected reservation.**
- [ ] **Step 2: Run `uv run pytest tests/runtime/test_budget.py -q` and verify import failures.**
- [ ] **Step 3: Implement atomic, integer-counted, Decimal-cost reservations.**
- [ ] **Step 4: Run focused tests and verify PASS.**

### Task 3: AWS live permission gate

**Files:**
- Create: `src/qualor/runtime/permissions.py`
- Test: `tests/runtime/test_permissions.py`

**Interfaces:**
- Produces: `CapabilityState`, `AwsCapability`, `AwsLivePermissionGate.require_identity`, and `require`.
- Guarantees: denied/unverified capability, root identity, or non-temporary credentials raise before provider construction.

- [ ] **Step 1: Write failing tests for C09, C11, and C12.**
- [ ] **Step 2: Run `uv run pytest tests/runtime/test_permissions.py -q` and verify import failures.**
- [ ] **Step 3: Implement the minimal immutable gate and explicit exceptions.**
- [ ] **Step 4: Run focused tests and verify PASS.**

### Task 4: Search snippet eligibility regression

**Files:**
- Modify: `tests/eligibility/test_engine.py`

**Interfaces:**
- Consumes: `aggregate_eligibility`, `SourceType.SEARCH_SNIPPET`.
- Guarantees: a matching snippet can create a candidate but cannot prove a critical hard rule.

- [ ] **Step 1: Add C07 using matching legal facts and snippet-only evidence.**
- [ ] **Step 2: Run the test and confirm existing eligibility behavior returns `REVIEW_REQUIRED`.**

### Task 5: Owner-review IAM bundle

**Files:**
- Create: `docs/aws/QUALOR-03A-IAM-REQUEST.md`
- Create: `infra/iam/examples/qualor-dev-bedrock-invoke.example.json`
- Create: `infra/iam/examples/qualor-dev-agentcore-gateway.example.json`
- Create: `infra/iam/examples/qualor-agentcore-gateway-role-trust.example.json`
- Create: `infra/iam/examples/qualor-agentcore-gateway-role-policy.example.json`
- Create: `docs/status/QUALOR-03A.md`

**Interfaces:**
- Documents exact actions, resource scopes, recipient identity, removal point, and risks.
- Uses placeholders for account-specific values; every file is review-only and applies nothing.

- [ ] **Step 1: Write policies from current AWS service authorization metadata and observed profile/model data.**
- [ ] **Step 2: Parse every JSON template and scan for account IDs, credentials, wildcards outside documented create/list needs, and broad actions.**
- [ ] **Step 3: Record permission denials and the `WAITING_HUMAN_GATE_A` state.**

### Task 6: Verification and branch checkpoint

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run focused runtime and eligibility tests.**
- [ ] **Step 2: Run `scripts/verify.ps1`, `scripts/aws-preflight.ps1`, schema export, and TypeScript generation.**
- [ ] **Step 3: Run independent Ruff, pytest, npm clean install/build, JSON parsing, secret scan, and `git diff --check`.**
- [ ] **Step 4: Commit logical changes, push `qualor-03-live-agent`, and leave the worktree clean without opening a PR.**

## Deferred to QUALOR-03B

- Strands Agent construction, prompts, autonomous loops, live discovery, Web Search calls, source fetching, and evidence extraction.
- Bedrock inference smoke until the owner applies and approves the minimal permission bundle.
- Gateway, target, service-role, Runtime, Memory, Browser, and Code Interpreter resource creation.
