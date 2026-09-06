"""Quoted extraction proposals, independently admitted by a narrow deterministic policy."""

import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, StrictStr, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category, ExtractionState, Provenance, SourceType
from qualor.domain.evidence import MAX_EVIDENCE_EXCERPT_CHARS, EvidenceRecord

from .sources import SourceDocument

ClaimField = Literal[
    "organizer",
    "program",
    "edition",
    "deadline",
    "entrant_type",
    "geography",
    "legal_entity",
    "project_policy",
    "license",
    "required_technology",
    "financial_support",
    "reward_conditions",
    "deliverables",
]
FIELD_CATEGORY = {
    field: Category(field.upper())
    for field in (
        "deadline",
        "entrant_type",
        "geography",
        "legal_entity",
        "project_policy",
        "license",
        "required_technology",
        "financial_support",
        "reward_conditions",
    )
}
HARD_AUTHORITIES = {
    SourceType.OFFICIAL_RULES,
    SourceType.OFFICIAL_APPLICATION,
    SourceType.OFFICIAL_FAQ,
}


class ExtractedClaim(Contract):
    source_id: NonEmpty
    source_url: NonEmpty
    field: ClaimField
    value: Annotated[StrictStr, Field(max_length=500)] | tuple[StrictStr, ...] | None
    excerpt: str = Field(min_length=1, max_length=MAX_EVIDENCE_EXCERPT_CHARS)
    state: Literal["CANDIDATE", "UNKNOWN", "NOT_APPLICABLE"]
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    not_applicable_reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def explicit_state(self) -> Self:
        if self.state == "UNKNOWN" and self.value is not None:
            raise ValueError("UNKNOWN cannot carry an asserted value")
        if self.state == "CANDIDATE" and self.value is None:
            raise ValueError("Candidate value required")
        if self.state == "NOT_APPLICABLE" and not self.not_applicable_reason:
            raise ValueError("N/A requires an explicit source-backed reason")
        if isinstance(self.value, tuple) and (not self.value or len(self.value) > 12):
            raise ValueError("Bounded nonempty list required")
        return self


class ValidatedClaim(Contract):
    claim: ExtractedClaim
    evidence: EvidenceRecord
    normalized_value: StrictStr | tuple[StrictStr, ...] | None
    support_state: Literal["CONTROLLED_CLAUSE_VERIFIED", "QUOTE_ONLY", "UNKNOWN"]


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def validate_claim(claim: ExtractedClaim, sources: dict[str, SourceDocument]) -> ValidatedClaim:
    claim = ExtractedClaim.model_validate(claim)
    source = sources.get(claim.source_id)
    if source is None or claim.source_url not in {source.original_url, source.final_url}:
        raise ValueError("CLAIM_REQUIRES_FETCHED_SOURCE")
    text, excerpt = normalize(source.text), normalize(claim.excerpt)
    if excerpt not in text:
        raise ValueError("EXCERPT_NOT_IN_FETCHED_SOURCE")
    if source.authority == SourceType.SEARCH_SNIPPET:
        raise ValueError("SEARCH_SNIPPET_IS_NOT_FETCHED_EVIDENCE")
    value = claim.value
    new_only = claim.field == "project_policy" and value == "NEW_ONLY"
    if value is not None and not new_only:
        values = value if isinstance(value, tuple) else (value,)
        if any(not v or normalize(v) not in excerpt for v in values):
            raise ValueError("NORMALIZED_VALUE_NOT_SUPPORTED_BY_QUOTE")
    if claim.state == "NOT_APPLICABLE" and normalize(claim.not_applicable_reason) not in excerpt:
        raise ValueError("NA_REASON_NOT_SUPPORTED")
    start = text.find(excerpt)
    # Check the entire containing sentence, not a model-selected fragment that could
    # conceal a negation or alternative. Unsupported compound clauses remain unknown.
    sentence_start = text.rfind(".", 0, start) + 1
    sentence_end = text.find(".", start)
    context = text[sentence_start : sentence_end + 1 if sentence_end >= 0 else len(text)]
    # A later/earlier exception must not disappear when the model trims its quote.
    # This narrow policy declines automatic review of any qualified source; it is
    # intentionally conservative until section/applicability interpretation exists.
    ambiguous = any(
        word in " " + text + " "
        for word in (
            " not ",
            " no ",
            " or ",
            " unless ",
            " except ",
            " example",
            " may ",
            " optionally ",
            " optional ",
            " if ",
        )
    )
    reviewed = False
    if claim.state == "CANDIDATE" and not ambiguous and source.authority in HARD_AUTHORITIES:
        if claim.field == "required_technology" and value is not None:
            terms = value if isinstance(value, tuple) else (value,)
            # Admit complete controlled clauses, not substrings of product names,
            # conditional tracks, obligations on judges, or descriptive prose.
            reviewed = len(terms) == 1 and context.strip().rstrip(".") in {
                subject + phrase + normalize(terms[0])
                for subject in ("projects ", "the project ", "submissions ", "the submission ")
                for phrase in (
                    "must use ",
                    "are required to use ",
                    "must be built with ",
                    "must be built using ",
                )
            }
        elif new_only:
            reviewed = context.strip().rstrip(".") in (
                "projects must be new",
                "project must be new",
                "must create a new project",
                "projects must be newly created",
                "project must be newly created",
            )
    if new_only and not reviewed:
        value = None
    category = FIELD_CATEGORY.get(claim.field, Category.REWARD_CONDITIONS)
    digest = hashlib.sha256(claim.model_dump_json().encode()).hexdigest()
    evidence = EvidenceRecord(
        schema_version="1",
        id="evidence_" + digest[:24],
        version=1,
        created_at=source.retrieved_at,
        updated_at=source.retrieved_at,
        provenance=Provenance.DOCUMENTED,
        source_id=source.id,
        original_url=source.original_url,
        final_url=source.final_url,
        retrieved_at=source.retrieved_at,
        source_type=source.authority,
        content_hash=source.content_hash,
        supporting_excerpt=claim.excerpt,
        normalized_field=category,
        extraction_state=ExtractionState.REVIEWED if reviewed else ExtractionState.UNVERIFIED,
    )
    return ValidatedClaim(
        claim=claim,
        evidence=evidence,
        normalized_value=value,
        support_state="CONTROLLED_CLAUSE_VERIFIED"
        if reviewed
        else "UNKNOWN"
        if value is None
        else "QUOTE_ONLY",
    )
