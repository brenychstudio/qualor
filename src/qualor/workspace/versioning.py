"""Stable semantic versioning for canonical opportunity observations."""

import hashlib
import json
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from qualor.domain import OpportunityRecord

OPPORTUNITY_DIGEST_POLICY_VERSION = 1
OPPORTUNITY_DIGEST_CRITICAL_FIELDS = (
    "organizer",
    "program_name",
    "edition",
    "canonical_rules_url",
    "application_url",
    "tracks",
    "deadlines",
    "geographic_scope",
    "rewards",
    "deliverables",
    "status",
    "matching_requirements",
    "strategic_benefits",
)


def _value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"instant": value.isoformat().replace("+00:00", "Z")}
    if type(value) is date:
        return {"date": value.isoformat()}
    if isinstance(value, Decimal):
        if value.is_zero():
            return {"decimal": [0, [0], 0]}
        sign, digits, exponent = value.as_tuple()
        digits = list(digits)
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        return {"decimal": [sign, digits or [0], exponent]}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _value(value[key]) for key in sorted(value)}
    return value


def _fact(fact: Any) -> dict[str, Any]:
    return {"value": _value(fact.value), "provenance": fact.provenance.value}


def _reward(reward: Any) -> dict[str, Any]:
    return {
        "kind": reward.kind.value,
        "amount": _value(reward.amount.model_dump()) if reward.amount else None,
        "amount_min": _value(reward.amount_min.model_dump()) if reward.amount_min else None,
        "amount_max": _value(reward.amount_max.model_dump()) if reward.amount_max else None,
        "conditions": list(reward.conditions),
        "expiry": _value(reward.expiry),
        "eligibility_note": reward.eligibility_note,
        "payment_timing": reward.payment_timing,
        "is_total_pool": reward.is_total_pool,
    }


def _matching(requirements: Any) -> dict[str, Any] | None:
    if requirements is None:
        return None
    return {
        "problem_labels": _fact(requirements.problem_labels),
        "audience_labels": _fact(requirements.audience_labels),
        "technologies": _fact(requirements.technologies),
        "features": _fact(requirements.features),
        "stages": _fact(requirements.stages),
        "licenses": _fact(requirements.licenses),
        "original_code_required": _fact(requirements.original_code_required),
        "max_adaptation_hours": _fact(requirements.max_adaptation_hours),
        "adaptation_unbounded": _fact(requirements.adaptation_unbounded),
        "materials": [
            {"kind": material.kind.value, "required": _fact(material.required)}
            for material in requirements.materials
        ],
    }


def _identity_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def opportunity_semantic_projection(record: OpportunityRecord) -> dict[str, Any]:
    record = OpportunityRecord.model_validate(record)
    return {
        "organizer": _identity_text(record.organizer),
        "program_name": _identity_text(record.program_name),
        "edition": _identity_text(record.edition),
        "canonical_rules_url": record.canonical_rules_url,
        "application_url": record.application_url,
        "tracks": list(record.tracks),
        "deadlines": _value(record.deadlines),
        "geographic_scope": record.geographic_scope,
        "rewards": [_reward(reward) for reward in record.rewards],
        "deliverables": list(record.deliverables),
        "status": record.status.value,
        "matching_requirements": _matching(record.matching_requirements),
        "strategic_benefits": _fact(record.strategic_benefits),
    }


def opportunity_semantic_digest(record: OpportunityRecord) -> str:
    projection = {
        "policy_version": OPPORTUNITY_DIGEST_POLICY_VERSION,
        **opportunity_semantic_projection(record),
    }
    encoded = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
