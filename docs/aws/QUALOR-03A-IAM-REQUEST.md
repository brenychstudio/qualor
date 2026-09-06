# QUALOR-03A IAM request

Status: **OWNER REVIEW REQUIRED — DO NOT APPLY AUTOMATICALLY**

This bundle records the minimum permissions discovered for the first controlled QUALOR live path. QUALOR-03A did not modify IAM, create a role, create a Gateway, invoke Web Search, or complete a paid Bedrock inference.

## Observed capability state

- Profile: `qualor-dev`; region: `us-east-1`; principal: non-root IAM user using temporary `aws login` credentials.
- Active selected profile: `global.anthropic.claude-sonnet-4-6` from source region `us-east-1`.
- The current control plane returned two model route entries for that profile: the global foundation-model resource and `us-east-1`. Global profile routes may change; rerun discovery before applying the policy if AWS changes the profile.
- A malformed-body, validation-safe runtime probe stopped at authorization with `AccessDeniedException` for `bedrock:InvokeModel`. No model inference completed.
- `ListGateways`, `GetGateway`, `ListGatewayTargets`, and `GetGatewayTarget` each returned `AccessDeniedException` for the corresponding `bedrock-agentcore` action.
- The public IAM simulator call was itself denied, so no unexecuted write action is represented as directly tested.
- AWS documentation lists the Web Search connector as available in `us-east-1` with connector ID `web-search`. Version `1.2.0` or later is required for request-level domain/date filters.

## A. Developer identity — Bedrock inference

### WHY_PERMISSION_IS_NEEDED

Strands `1.54.0` uses Bedrock Converse/ConverseStream. Non-streaming calls require `bedrock:InvokeModel`; the default streaming path requires `bedrock:InvokeModelWithResponseStream`.

### EXACT_ACTIONS

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`

`bedrock:CountTokens` is deliberately omitted because the pinned Strands provider falls back to local token estimation when it is unavailable.

### RESOURCE_SCOPE

- The account-scoped inference profile `global.anthropic.claude-sonnet-4-6` in source region `us-east-1`.
- Only the two foundation-model resources returned by the current profile control-plane response.
- The foundation-model statement is conditioned on the selected inference profile ARN, preventing direct model use outside that profile.

Replace the review placeholders with resources having these exact components:

| Placeholder | Partition | Service | Region | Account | Resource |
| --- | --- | --- | --- | --- | --- |
| `GLOBAL_SONNET_46_INFERENCE_PROFILE_ARN` | `aws` | `bedrock` | `us-east-1` | owner account | `inference-profile/global.anthropic.claude-sonnet-4-6` |
| `GLOBAL_SONNET_46_FOUNDATION_MODEL_ARN` | `aws` | `bedrock` | empty | empty | `foundation-model/anthropic.claude-sonnet-4-6` |
| `US_EAST_1_SONNET_46_FOUNDATION_MODEL_ARN` | `aws` | `bedrock` | `us-east-1` | empty | `foundation-model/anthropic.claude-sonnet-4-6` |

### WHICH_IDENTITY_RECEIVES_IT

The existing non-root developer identity reached only through profile `qualor-dev`.

### WHEN_IT_CAN_BE_REMOVED

Remove after controlled local QUALOR live development ends or when invocation moves to a dedicated execution role.

### RISK_NOTES

These actions can incur Bedrock charges. QUALOR's local reservation guard limits calls it controls, but it is not an AWS billing hard cap. Global inference routing can change, so profile routes and pricing must be rechecked before live use.

Template: `infra/iam/examples/qualor-dev-bedrock-invoke.example.json`

## B. Developer identity — AgentCore Gateway

### WHY_PERMISSION_IS_NEEDED

QUALOR-03B plans one MCP Gateway, one built-in Web Search target, read/invoke access, and bounded cleanup. It does not need AgentCore Runtime, Browser, Memory, Code Interpreter, or general credential-provider administration.

### EXACT_ACTIONS

- `bedrock-agentcore:CreateGateway`
- `bedrock-agentcore:GetGateway`
- `bedrock-agentcore:ListGateways`
- `bedrock-agentcore:DeleteGateway`
- `bedrock-agentcore:CreateGatewayTarget`
- `bedrock-agentcore:GetGatewayTarget`
- `bedrock-agentcore:ListGatewayTargets`
- `bedrock-agentcore:DeleteGatewayTarget`
- `bedrock-agentcore:InvokeGateway`
- `bedrock-agentcore:SynchronizeGatewayTargets` as the documented dependent permission for create operations
- `bedrock-agentcore:TagResource` so Gateway creation can enforce canonical tags

### RESOURCE_SCOPE

Existing-resource actions use only the `QUALOR_GATEWAY_ARN_PATTERN` review placeholder and require the canonical QUALOR resource tags. Its exact components are partition `aws`, service `bedrock-agentcore`, region `us-east-1`, the owner account, and resource `gateway/*`. `CreateGateway` and `ListGateways` do not support resource-level authorization, so their isolated statements use `Resource: "*"`; creation additionally requires exactly the canonical request tags. No wildcard AgentCore action is requested.

### WHICH_IDENTITY_RECEIVES_IT

The existing non-root developer identity reached only through profile `qualor-dev`.

### WHEN_IT_CAN_BE_REMOVED

Remove create/delete/tag/pass-role permissions after the single Gateway and target are stable. Retain only narrowly scoped read/invoke permissions while local live execution is required.

### RISK_NOTES

Create, target synchronization, invoke, and delete are state-changing or billable-capable actions. The example cannot restrict the future Gateway ID before creation, so tags are mandatory and the policy should be narrowed to the exact created Gateway ARN immediately after owner-approved creation.

Template: `infra/iam/examples/qualor-dev-agentcore-gateway.example.json`

## C. Gateway service role

### WHY_PERMISSION_IS_NEEDED

AgentCore assumes a dedicated role to invoke the Gateway and the AWS-owned Web Search connector.

### EXACT_ACTIONS

- Trust: `sts:AssumeRole` by `bedrock-agentcore.amazonaws.com`
- Permission: `bedrock-agentcore:InvokeGateway`
- Permission: `bedrock-agentcore:InvokeWebSearch`

### RESOURCE_SCOPE

The Gateway permission is restricted to the `QUALOR_GATEWAY_ARN_PATTERN` placeholder in `us-east-1`. The `AWS_US_EAST_1_WEB_SEARCH_TOOL_ARN` placeholder has exact components: partition `aws`, service `bedrock-agentcore`, region `us-east-1`, service-owned account segment `aws`, and resource `tool/web-search.v1`. The trust policy binds both source account and source Gateway ARN.

### WHICH_IDENTITY_RECEIVES_IT

A future single role named `qualor-agentcore-gateway-role`. The owner must create and review it; QUALOR-03A does not.

### WHEN_IT_CAN_BE_REMOVED

Delete the role after the Gateway is removed and no retained QUALOR artifact depends on it.

### RISK_NOTES

Before creation the trust template uses the QUALOR Gateway wildcard because its ID is unknown. Replace it with the exact Gateway ARN immediately after creation.

Templates:

- `infra/iam/examples/qualor-agentcore-gateway-role-trust.example.json`
- `infra/iam/examples/qualor-agentcore-gateway-role-policy.example.json`

## D. PassRole

### WHY_PERMISSION_IS_NEEDED

`CreateGateway` accepts the pre-created service role ARN and declares `iam:PassRole` as a dependent permission.

### EXACT_ACTIONS

- `iam:PassRole`

### RESOURCE_SCOPE

Only the `QUALOR_GATEWAY_ROLE_ARN` placeholder, whose exact components are partition `aws`, service `iam`, owner account, and resource `role/qualor-agentcore-gateway-role`; it is conditioned on `iam:PassedToService = bedrock-agentcore.amazonaws.com`.

### WHICH_IDENTITY_RECEIVES_IT

The existing non-root developer identity reached through `qualor-dev`.

### WHEN_IT_CAN_BE_REMOVED

Remove after the Gateway is created and no update needs to attach a different role.

### RISK_NOTES

No `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PutRolePolicy`, or wildcard IAM administration is requested.

## References checked on 2026-09-05

- AWS Bedrock Sonnet 4.6 model card: <https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html>
- AWS inference profile prerequisites: <https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-prereq.html>
- AgentCore Gateway permissions: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-prerequisites-permissions.html>
- Web Search connector: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html>
- Gateway target configuration: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-api-target-config.html>
- AgentCore service authorization data: <https://servicereference.us-east-1.amazonaws.com/v1/bedrock-agentcore/bedrock-agentcore.json>
