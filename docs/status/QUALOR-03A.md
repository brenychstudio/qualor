# QUALOR-03A status

- Date: 2026-09-05
- Base: `17c8c46b39ee6fead667461953a4fb975ba52dd0`
- Branch: `qualor-03-live-agent`
- Canonical SHA-256: `440db7b600d6ec170778035e39d93ce8cd5b8f20d49fd99bccf3174978536829`
- Python: `3.12.14`
- Strands: `1.54.0`
- boto3 / botocore: `1.43.89` / `1.43.89`
- Pydantic / FastAPI / HTTPX: `2.13.5` / `0.141.1` / `0.28.1`
- AWS CLI: `2.36.40`
- AWS identity: non-root IAM user, temporary `aws login` credentials, profile `qualor-dev`, region `us-east-1`
- Selected model/profile: `global.anthropic.claude-sonnet-4-6`
- Profile source region: `us-east-1`; current control-plane model route entries: `2`
- Bedrock invoke permission: blocked on `bedrock:InvokeModel`; inference not completed
- Gateway reads: blocked on `ListGateways`, `GetGateway`, `ListGatewayTargets`, and `GetGatewayTarget`
- Gateway manage/invoke, Web Search invoke, and PassRole: not granted; owner review required
- Web Search architecture: available in `us-east-1`, connector `web-search`; use connector `1.2.0` for request-level domain/date filters
- Runtime modes: `LIVE`, `FIXTURE`, `REPLAY`
- Live limits: inference `3`, search `5`, fetch documents `10`, development cost reservation cap USD `2.00`
- AWS resources created: `0`
- Paid AWS calls completed: `0`
- Bedrock inference calls completed: `0`
- Status: `WAITING_HUMAN_GATE_A`

Implemented in this gate: local mode/provider boundaries, call/cost budget guard, AWS identity/capability admission gate, search-snippet regression protection, and review-only IAM examples.

Deferred: complete Strands agent, prompts, autonomous loop, live search/fetch, evidence extraction, Gateway/target/service-role creation, AgentCore Runtime, and any paid smoke.
