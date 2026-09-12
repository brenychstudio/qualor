# Hosted LIVE backend — Task 2

This backend surface is for a single Python process with one owned worker thread.
It uses the existing Strands runtime and Task 1 WorkspaceRunCapture. No queue,
transient-job database table, infrastructure deployment, or new cost authority is
introduced. Browser disconnection does not own the worker lifetime.

## Configuration

The default security mode remains `LOCAL`. Its loopback Origin checks, action token,
read-only switch, and fixture endpoints retain their previous behavior. The hosted
LIVE routes are unavailable in LOCAL.

Operator-owned runtime configuration for `HOSTED_DEMO`:

| Environment variable | Requirement/default |
| --- | --- |
| `QUALOR_SECURITY_MODE` | `HOSTED_DEMO` |
| `QUALOR_ORIGIN_AUTH` | Server secret, 32–1024 characters; inject at runtime |
| `QUALOR_DEMO_PROFILE_PATH` | Private operator-mounted StudioInput JSON file |
| `DATABASE_PATH` | Dedicated SQLite Workspace database for the sanitized demo |
| `QUALOR_GATEWAY_ID` | Existing server-owned Gateway identifier |
| `QUALOR_HOSTED_LIVE_ENABLED` | Defaults to false; must explicitly enable execution |
| `QUALOR_MAX_CONCURRENT_LIVE_RUNS` | Exactly 1; other values rejected |
| `QUALOR_LIVE_MAX_RUNS` | 5 per process lifetime; configurable 1–100 |
| `QUALOR_LIVE_COOLDOWN_SECONDS` | 60 after terminal execution; configurable 0–86400 |

The unchanged physical `live_budget()` guard caps each run at USD 0.20, with its
existing model/search/fetch limits and reservation/reconciliation rules. The
process-wide guard counts every admitted execution, including failed runs. Rejected
requests make no paid call. Restart resets process-local limits; the later Cloudflare
layer must enforce access sessions and coarse rate limiting independently. Do not
start multiple uvicorn workers or multiple backend instances against this controller.

The profile file uses the existing StudioInput schema and must contain exactly one
project named `QUALOR`. It is supplied by the operator, never uploaded through the
browser. Project facts and effort assumptions must be reviewed for public demo use;
unknown fields remain unknown. The loader discards the file's goal, allowed hosts,
and URL, and assigns stable demo-only founder/project IDs. It removes founder
residence, citizenship, incorporation date, availability, cash budget, strategic
notes, and constraints before runtime/persistence. No project capability, legal form,
or eligibility fact is invented. Keep the file outside Git, restrict its filesystem
permissions, and do not place secrets in any profile fact. Startup refuses a database
with any profile history or any profile differing from the single immutable sanitized
demo snapshot. This includes older decision-bound profiles, not only current versions.
Changing that snapshot requires a new dedicated demo database in this task.

## Authentication and endpoints

Every hosted `/api/*` request requires exactly one `X-QUALOR-Origin-Auth` header,
verified with constant-time comparison. The later Worker must overwrite that header
with its server secret after authenticating the user's demo session. It must never
forward an arbitrary browser-supplied value as trust. No secret is serialized in
settings, status responses, or validation errors. CORS grants no hosted origins and
is not the authentication mechanism.

`POST /api/v1/live-runs` accepts only `official_url` and optional short `goal`.
The goal is supplemental context under the server's fixed research objective.
The URL must be HTTPS with a public DNS hostname, no userinfo, nonstandard port,
control characters, or ambiguous backslashes. Public DNS admission is followed by
the existing pinned-IP fetch and redirect checks. The URL is passed to Strands as
`unverified_user_opportunity_url`; only the normal search/fetch/admission path can
produce evidence. Browser fields for profiles, projects, hosts, budgets, models,
AWS configuration, credentials, or policy are rejected.

Admission returns HTTP 202 with `run_id` and `STARTING`. A busy slot returns
HTTP 409 `LIVE_RUN_BUSY`; run-count or cooldown limits return HTTP 429 with
`LIVE_RUN_LIMIT_REACHED` or `LIVE_RUN_COOLDOWN`. Disabled execution returns
HTTP 503 `LIVE_RUN_UNAVAILABLE`.

`GET /api/v1/live-runs/{run_id}` returns only the bounded public status contract.
`RESEARCHING` follows real search/fetch/extraction events; `EVALUATING` follows
actual deterministic engine events. Research may resume if the agent requests more
evidence. There are no percentages or timers that invent progress. `COMPLETED` is
read from the persisted linked LIVE RunRecord, opportunity, decision and evidence;
the coordinator never computes another decision. Partial runtime outcomes map to
`FAILED` with `LIVE_RUN_INCOMPLETE`; provider failures and budget stops have bounded
codes. Persistence failures always fail the public run. Unknown exceptions never
return provider text, stack traces, endpoint URLs, or AWS request IDs.

Status polling survives browser refresh. After process restart, completed runs are
read from SQLite. An in-flight run lost with the process returns HTTP 404
`LIVE_RUN_UNAVAILABLE`; the backend does not claim that work resumed. Graceful
shutdown stops admission and waits for the owned worker; it never releases a slot
while a physical call may still be running.

Existing Inbox, Workspace, Evidence, and Runs APIs serve the persisted graph through
the authenticated proxy. Hosted session/token issuance, Portfolio, approval and pack
endpoints, and all owner mutations remain unavailable. No hosted action token is
created. The later Cloudflare session layer and a bounded session/action capability
must be integrated before enabling hosted approval/confirmation/draft generation.
The frontend must not offer those mutations until that boundary is implemented.

## Verification and deployment boundary

`tests/test_hosted_live_runs.py` drives POST → status polling → the actual LIVE-mode
OpportunityRun with controlled provider I/O → Task 1 persistence → existing read
APIs, plus restart, concurrency races, private URLs, secret handling, and faults.
It seeds neither a fixture graph nor a replay graph and performs no paid AWS call.

This task does not deploy or claim real AWS access. The runtime still uses its
existing `qualor-dev` short-lived-credential and Gateway preflight path in
`runtime/search_transport.py`; region and model remain server-owned constants.
EC2 instance-profile adaptation and its infrastructure/access checks belong to the
deployment work. The Worker, user access session, rate limiter, Tunnel, DNS and
frontend Research control are subsequent tasks.
