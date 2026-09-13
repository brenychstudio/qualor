"""Classify independently supplied decision facts without rewriting provenance."""

from datetime import datetime
from typing import Literal

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.base import Fact
from qualor.domain.enums import Provenance
from qualor.domain.profiles import FounderProfile
from qualor.runtime.run_models import StudioInput

FactScope = Literal["OWNER", "PROJECT", "ACCOUNT"]
FactAuthorityClass = Literal[
    "OWNER_PROVIDED", "PROJECT_STATE", "VERIFIED_ACCOUNT_STATE", "UNKNOWN"
]


def independent_decision_facts(
    inputs: StudioInput,
) -> tuple[FounderProfile, tuple[ProjectDecisionInput, ...]]:
    """Return only the validated founder and project facts supplied by the caller."""
    StudioInput.model_validate(inputs)
    return inputs.founder, inputs.projects


def fact_authority_class(
    fact: Fact,
    *,
    scope: FactScope,
    verified_at: datetime | None,
) -> FactAuthorityClass:
    """Describe existing fact authority without changing its provenance or value."""
    if fact.value is None or fact.provenance == Provenance.UNKNOWN:
        return "UNKNOWN"
    if scope == "OWNER" and fact.provenance == Provenance.USER_ASSERTED:
        return "OWNER_PROVIDED"
    if scope == "PROJECT" and fact.provenance in {
        Provenance.USER_ASSERTED,
        Provenance.DOCUMENTED,
    }:
        return "PROJECT_STATE"
    if (
        scope == "ACCOUNT"
        and fact.provenance == Provenance.DOCUMENTED
        and fact.evidence_refs
        and verified_at is not None
    ):
        return "VERIFIED_ACCOUNT_STATE"
    return "UNKNOWN"
