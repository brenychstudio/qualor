"""Deterministic runtime test factories with no external side effects."""

import hashlib
from datetime import UTC, datetime

import pytest

from qualor.runtime.sources import SourceDocument


@pytest.fixture
def document():
    def make_document(text: str, *, content_hash: str | None = None) -> SourceDocument:
        return SourceDocument(
            id="source_example_rules",
            original_url="https://example.org/rules",
            final_url="https://example.org/rules",
            retrieved_at=datetime(2026, 9, 12, 11, 25, 52, tzinfo=UTC),
            content_hash=content_hash or hashlib.sha256(text.encode("utf-8")).hexdigest(),
            authority="OFFICIAL_RULES",
            content_type="text/plain",
            text=text,
        )

    return make_document
