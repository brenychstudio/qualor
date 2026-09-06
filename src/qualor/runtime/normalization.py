"""Deterministic support checks between grounded source text and proposed values."""

import re
from typing import Literal

from pydantic import StrictStr

from qualor.domain.base import Contract

NormalizationStatus = Literal["SUPPORTED", "UNSUPPORTED", "AMBIGUOUS", "UNKNOWN"]
NormalizedValue = StrictStr | tuple[StrictStr, ...] | None
NORMALIZER_VERSION = "1"


class NormalizedSupportResult(Contract):
    status: NormalizationStatus
    canonical_value: NormalizedValue
    reason_code: StrictStr
    normalizer_version: Literal["1"] = NORMALIZER_VERSION


class ClaimNormalizationError(ValueError):
    """Safe typed rejection carrying no source text or proposed value."""

    def __init__(self, reason_code: str, result: NormalizedSupportResult):
        super().__init__(reason_code)
        self.result = result


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _clause(text: str) -> str:
    return normalize_text(text).strip().rstrip(".!?")


def _unknown(reason: str = "MODEL_RETAINED_UNKNOWN") -> NormalizedSupportResult:
    return NormalizedSupportResult(
        status="UNKNOWN", canonical_value=None, reason_code=reason
    )


def _ambiguous(reason: str) -> NormalizedSupportResult:
    return NormalizedSupportResult(
        status="AMBIGUOUS", canonical_value=None, reason_code=reason
    )


def _unsupported(reason: str) -> NormalizedSupportResult:
    return NormalizedSupportResult(
        status="UNSUPPORTED", canonical_value=None, reason_code=reason
    )


def _supported(value: str | tuple[str, ...], reason: str) -> NormalizedSupportResult:
    return NormalizedSupportResult(
        status="SUPPORTED", canonical_value=value, reason_code=reason
    )


def _entrant_type(excerpt: str) -> NormalizedSupportResult:
    clause = _clause(excerpt)
    explicit = {
        "individuals may enter": "INDIVIDUAL",
        "individuals can enter": "INDIVIDUAL",
        "individuals may participate": "INDIVIDUAL",
        "individuals are eligible to enter": "INDIVIDUAL",
        "natural persons may enter": "INDIVIDUAL",
        "natural persons are eligible to enter": "INDIVIDUAL",
        "solo entrants may enter": "INDIVIDUAL",
        "teams may enter": "TEAM",
        "teams can enter": "TEAM",
        "teams may participate": "TEAM",
        "teams are eligible to enter": "TEAM",
        "individuals and teams may enter": ("INDIVIDUAL", "TEAM"),
        "individuals and teams may participate": ("INDIVIDUAL", "TEAM"),
    }
    if clause in explicit:
        return _supported(explicit[clause], "ENTRANT_TYPE_EXPLICIT_LEXICON")
    if any(
        term in " " + clause + " "
        for term in (
            " individual ",
            " individuals ",
            " natural person ",
            " natural persons ",
            " solo entrant ",
            " solo entrants ",
            " team ",
            " teams ",
            " applicant ",
            " applicants ",
            " participant ",
            " participants ",
        )
    ):
        return _ambiguous("ENTRANT_TYPE_LANGUAGE_NOT_IN_EXPLICIT_LEXICON")
    return _unsupported("ENTRANT_TYPE_NOT_SUPPORTED_BY_SPAN")


def _project_policy(excerpt: str) -> NormalizedSupportResult:
    if _clause(excerpt) in {
        "projects must be new",
        "project must be new",
        "must create a new project",
        "projects must be newly created",
        "project must be newly created",
    }:
        return _supported("NEW_ONLY", "PROJECT_POLICY_CONTROLLED_CLAUSE")
    return _unsupported("PROJECT_POLICY_NOT_SUPPORTED_BY_CONTROLLED_CLAUSE")


_TECHNOLOGY_CLAUSE = re.compile(
    r"(?:projects|the project|submissions|the submission) "
    r"(?:must use|are required to use|must be built with|must be built using) "
    r"(?P<technology>[^.]+)"
)


def _required_technology(
    excerpt: str, proposed_value: NormalizedValue
) -> NormalizedSupportResult:
    clauses = tuple(
        clause
        for sentence in re.split(r"(?<=[.!?])\s+", normalize_text(excerpt))
        if (clause := sentence.strip().rstrip(".!?"))
    )
    if any(
        marker in " " + clause + " "
        for clause in clauses
        for marker in (" not ", " no ", " or ", " unless ", " except ", " if ")
    ) or any(clause.startswith("for example") for clause in clauses):
        return _ambiguous("REQUIRED_TECHNOLOGY_QUALIFIED_CLAUSE")
    matches = tuple(
        match
        for clause in clauses
        if (match := _TECHNOLOGY_CLAUSE.fullmatch(clause)) is not None
    )
    if len(matches) != 1:
        return _unsupported("REQUIRED_TECHNOLOGY_NOT_SUPPORTED_BY_CONTROLLED_CLAUSE")
    technology = matches[0].group("technology").strip()
    if not technology:
        return _unsupported("REQUIRED_TECHNOLOGY_VALUE_MISSING")
    canonical: str | tuple[str, ...] = (
        (technology,) if isinstance(proposed_value, tuple) else technology
    )
    return _supported(canonical, "REQUIRED_TECHNOLOGY_CONTROLLED_CLAUSE")


def _literal_value(excerpt: str, proposed_value: NormalizedValue) -> NormalizedSupportResult:
    if proposed_value is None:
        return _unknown()
    values = proposed_value if isinstance(proposed_value, tuple) else (proposed_value,)
    normalized_excerpt = normalize_text(excerpt)
    if any(not value or normalize_text(value) not in normalized_excerpt for value in values):
        return _unsupported("OPEN_TEXT_VALUE_NOT_LITERAL_IN_SOURCE_SPAN")
    return _supported(proposed_value, "OPEN_TEXT_EXACT_NORMALIZED_SUBSTRING")


def normalize_supported_claim(
    normalized_field: str,
    evidence_span_exact_text: str,
    proposed_value: NormalizedValue,
    *,
    state: str,
) -> NormalizedSupportResult:
    """Derive bounded canonical support from one runtime-grounded exact source span."""

    if state == "UNKNOWN":
        return _unknown()
    if state == "NOT_APPLICABLE":
        return _unknown("NOT_APPLICABLE_REQUIRES_SEPARATE_REASON_GROUNDING")
    if normalized_field == "entrant_type":
        return _entrant_type(evidence_span_exact_text)
    if normalized_field == "project_policy":
        return _project_policy(evidence_span_exact_text)
    if normalized_field == "required_technology":
        return _required_technology(evidence_span_exact_text, proposed_value)
    return _literal_value(evidence_span_exact_text, proposed_value)


def canonical_values_equal(left: NormalizedValue, right: NormalizedValue) -> bool:
    if isinstance(left, tuple) != isinstance(right, tuple):
        return False
    if isinstance(left, tuple) and isinstance(right, tuple):
        return tuple(normalize_text(item) for item in left) == tuple(
            normalize_text(item) for item in right
        )
    if isinstance(left, str) and isinstance(right, str):
        return normalize_text(left) == normalize_text(right)
    return left is right
