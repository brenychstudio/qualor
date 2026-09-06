"""Snapshot metadata; reviewed extraction is an explicit assertion, not hash-derived truth."""

from typing import Annotated

from pydantic import StringConstraints

from .base import NonEmpty, Record, UtcInstant
from .enums import Category, ExtractionState, SourceType
from .opportunity import OriginalSourceUrl


class EvidenceRecord(Record):
    source_id: NonEmpty | None = None
    original_url: OriginalSourceUrl
    final_url: OriginalSourceUrl
    retrieved_at: UtcInstant
    source_type: SourceType
    content_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]
    supporting_excerpt: NonEmpty
    normalized_field: Category
    extraction_state: ExtractionState
    last_refresh_failed_at: UtcInstant | None = None
