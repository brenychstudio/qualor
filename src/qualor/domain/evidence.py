"""Snapshot metadata; reviewed extraction is an explicit assertion, not hash-derived truth."""

from typing import Annotated, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from .base import Contract, NonEmpty, Record, UtcInstant
from .enums import Category, ExtractionState, SourceType
from .opportunity import OriginalSourceUrl

MAX_EVIDENCE_EXCERPT_CHARS = 700
EvidenceExcerpt = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_EVIDENCE_EXCERPT_CHARS,
    ),
]


class ClauseContext(Contract):
    """Bounded exact excerpts and identities of applicable governing clauses."""

    source_id: NonEmpty
    section_id: NonEmpty
    span_ids: Annotated[tuple[NonEmpty, ...], Field(max_length=12)]
    qualifiers: Annotated[
        tuple[Annotated[str, StringConstraints(strict=True, min_length=1, max_length=700)], ...],
        Field(max_length=12),
    ]
    exceptions: Annotated[
        tuple[Annotated[str, StringConstraints(strict=True, min_length=1, max_length=700)], ...],
        Field(max_length=12),
    ]
    context_section_ids: Annotated[tuple[NonEmpty, ...], Field(max_length=12)]
    context_complete: StrictBool

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        for references in (self.span_ids, self.context_section_ids):
            if len(set(references)) != len(references):
                raise ValueError("DUPLICATE_CLAUSE_CONTEXT_REFERENCE")
        return self


class EvidenceRecord(Record):
    source_id: NonEmpty | None = None
    original_url: OriginalSourceUrl
    final_url: OriginalSourceUrl
    retrieved_at: UtcInstant
    source_type: SourceType
    content_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]
    supporting_excerpt: EvidenceExcerpt
    normalized_field: Category
    extraction_state: ExtractionState
    last_refresh_failed_at: UtcInstant | None = None
    clause_context: ClauseContext | None = None
