"""Local admission gate for AWS-backed providers; this module performs no AWS calls."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class CapabilityState(StrEnum):
    PASS = "PASS"
    BLOCKED_PERMISSION = "BLOCKED_PERMISSION"
    UNVERIFIED = "UNVERIFIED"


class AwsCapability(StrEnum):
    BEDROCK_INVOKE = "BEDROCK_INVOKE"
    AGENTCORE_GATEWAY_MANAGE = "AGENTCORE_GATEWAY_MANAGE"
    AGENTCORE_GATEWAY_INVOKE = "AGENTCORE_GATEWAY_INVOKE"
    WEB_SEARCH = "WEB_SEARCH"
    PASS_ROLE = "PASS_ROLE"


class UnsafeAwsIdentity(RuntimeError):
    pass


class CapabilityDenied(RuntimeError):
    pass


@dataclass(frozen=True)
class AwsLivePermissionGate:
    principal_type: str
    root_identity: bool
    temporary_credentials: bool
    capabilities: Mapping[AwsCapability, CapabilityState]

    def __post_init__(self) -> None:
        normalized = {
            AwsCapability(capability): CapabilityState(state)
            for capability, state in self.capabilities.items()
        }
        object.__setattr__(self, "capabilities", MappingProxyType(normalized))

    def require_identity(self) -> None:
        if self.root_identity or self.principal_type == "ROOT":
            raise UnsafeAwsIdentity("AWS live execution rejects root identity")
        if self.principal_type not in {"IAM_USER", "ASSUMED_ROLE", "FEDERATED"}:
            raise UnsafeAwsIdentity("AWS live execution requires an approved principal type")
        if not self.temporary_credentials:
            raise UnsafeAwsIdentity("AWS live execution requires temporary credentials")

    def require(self, capability: AwsCapability) -> None:
        self.require_identity()
        capability = AwsCapability(capability)
        state = self.capabilities.get(capability, CapabilityState.UNVERIFIED)
        if state is not CapabilityState.PASS:
            raise CapabilityDenied(f"{capability.value} is {state.value}")
