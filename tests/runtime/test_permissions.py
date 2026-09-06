import pytest

from qualor.runtime import (
    AwsCapability,
    AwsLivePermissionGate,
    CapabilityDenied,
    CapabilityState,
    UnsafeAwsIdentity,
)


def gate(**changes) -> AwsLivePermissionGate:
    values = dict(
        principal_type="IAM_USER",
        root_identity=False,
        temporary_credentials=True,
        capabilities={capability: CapabilityState.PASS for capability in AwsCapability},
    )
    values.update(changes)
    return AwsLivePermissionGate(**values)


def test_C09_permission_denial_fails_closed():
    denied = gate(capabilities={AwsCapability.BEDROCK_INVOKE: CapabilityState.BLOCKED_PERMISSION})
    with pytest.raises(CapabilityDenied, match="BEDROCK_INVOKE"):
        denied.require(AwsCapability.BEDROCK_INVOKE)


def test_unverified_permission_fails_closed():
    unknown = gate(capabilities={AwsCapability.WEB_SEARCH: CapabilityState.UNVERIFIED})
    with pytest.raises(CapabilityDenied, match="WEB_SEARCH"):
        unknown.require(AwsCapability.WEB_SEARCH)


def test_C11_root_identity_is_rejected():
    with pytest.raises(UnsafeAwsIdentity, match="root"):
        gate(principal_type="ROOT", root_identity=True).require_identity()


def test_C12_long_term_or_unknown_credentials_are_rejected():
    with pytest.raises(UnsafeAwsIdentity, match="temporary"):
        gate(temporary_credentials=False).require_identity()


def test_safe_identity_and_explicit_permission_pass():
    allowed = gate()
    allowed.require_identity()
    allowed.require(AwsCapability.BEDROCK_INVOKE)
