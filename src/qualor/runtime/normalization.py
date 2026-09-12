"""Deterministic support checks between grounded source text and proposed values."""

import re
from datetime import UTC, datetime
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


_QUALIFIERS = (" not ", " no ", " or ", " unless ", " except ", " if ")
_LABELED_SCALAR = {
    field: re.compile(
        rf"^(?:the\s+)?{label}\s*(?::|\bis\b)\s*(?P<value>.+?)\s*[.!?]?$",
        re.IGNORECASE,
    )
    for field, label in {
        "organizer": "organizer",
        "program": "program",
        "edition": "edition",
    }.items()
}
_DELIVERABLES = re.compile(
    r"^(?:the\s+)?deliverables\s*(?::|\bare\b)\s*(?P<value>.+?)\s*[.!?]?$",
    re.IGNORECASE,
)


def _unqualified(value: str) -> bool:
    normalized = " " + normalize_text(value) + " "
    return not any(marker in normalized for marker in _QUALIFIERS)


def _labeled_scalar(
    field: str, excerpt: str, proposed_value: NormalizedValue
) -> NormalizedSupportResult:
    if proposed_value is None:
        return _unknown()
    if not isinstance(proposed_value, str):
        return _unsupported("LABELED_METADATA_REQUIRES_ONE_TEXT_VALUE")
    match = _LABELED_SCALAR[field].fullmatch(excerpt.strip())
    if match is None:
        return _unsupported("METADATA_NOT_SUPPORTED_BY_CONTROLLED_FIELD_CLAUSE")
    source_value = match.group("value").strip()
    if not _unqualified(source_value):
        return _ambiguous("METADATA_FIELD_CLAUSE_QUALIFIED")
    if normalize_text(source_value) != normalize_text(proposed_value):
        return _unsupported("METADATA_VALUE_NOT_EXACT_FIELD_VALUE")
    return _supported(proposed_value, "METADATA_EXACT_FIELD_CLAUSE")


def _deliverables(excerpt: str, proposed_value: NormalizedValue) -> NormalizedSupportResult:
    if proposed_value is None:
        return _unknown()
    match = _DELIVERABLES.fullmatch(excerpt.strip())
    if match is None:
        return _unsupported("DELIVERABLES_NOT_SUPPORTED_BY_CONTROLLED_FIELD_CLAUSE")
    source_value = match.group("value").strip()
    if not _unqualified(source_value):
        return _ambiguous("DELIVERABLES_FIELD_CLAUSE_QUALIFIED")
    values = proposed_value if isinstance(proposed_value, tuple) else (proposed_value,)
    normalized_values = tuple(normalize_text(value) for value in values)
    joined = {
        normalized_values[0] if len(normalized_values) == 1 else "",
        ", ".join(normalized_values),
        " and ".join(normalized_values),
        "; ".join(normalized_values),
    }
    if len(normalized_values) > 1:
        joined.add(", ".join(normalized_values[:-1]) + ", and " + normalized_values[-1])
    if normalize_text(source_value) not in joined:
        return _unsupported("DELIVERABLES_VALUE_NOT_EXACT_FIELD_VALUE")
    return _supported(proposed_value, "DELIVERABLES_EXACT_FIELD_CLAUSE")


_ABSOLUTE_DEADLINE = re.compile(
    r"^(?:the\s+)?deadline\s*(?::|\bis\b)\s*(?P<value>.+?)\s*[.!?]?$",
    re.IGNORECASE,
)
_RFC3339_ABSOLUTE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def parse_absolute_deadline(value: str) -> datetime | None:
    """Return one UTC instant only when ``value`` carries an explicit offset."""

    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if _RFC3339_ABSOLUTE.fullmatch(candidate) is None:
        return None
    try:
        parsed = datetime.fromisoformat(
            candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
        )
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _deadline(excerpt: str, proposed_value: NormalizedValue) -> NormalizedSupportResult:
    if proposed_value is None:
        return _unknown()
    if not isinstance(proposed_value, str):
        return _ambiguous("DEADLINE_REQUIRES_ONE_ABSOLUTE_INSTANT")
    match = _ABSOLUTE_DEADLINE.fullmatch(excerpt.strip())
    if match is None or normalize_text(match.group("value")) != normalize_text(proposed_value):
        return _unsupported("DEADLINE_NOT_SUPPORTED_BY_CONTROLLED_CLAUSE")
    if parse_absolute_deadline(proposed_value) is None:
        return _ambiguous("DEADLINE_TIMEZONE_OR_INSTANT_AMBIGUOUS")
    return _supported(proposed_value, "DEADLINE_ABSOLUTE_INSTANT")


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
    if normalized_field == "deadline":
        return _deadline(evidence_span_exact_text, proposed_value)
    if normalized_field in _LABELED_SCALAR:
        return _labeled_scalar(normalized_field, evidence_span_exact_text, proposed_value)
    if normalized_field == "deliverables":
        return _deliverables(evidence_span_exact_text, proposed_value)
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
