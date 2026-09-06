"""Snapshot metadata; reviewed extraction is an explicit assertion, not hash-derived truth."""

from typing import Annotated

from pydantic import StringConstraints

from .base import NonEmpty, Record, UtcInstant
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
