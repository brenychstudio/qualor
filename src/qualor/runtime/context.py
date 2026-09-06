"""Bounded references keep fetched documents out of ordinary agent context."""

import json

from pydantic import Field

from qualor.domain.base import Contract, NonEmpty, UtcInstant
from qualor.domain.enums import SourceType

MAX_AGENT_SOURCE_REF_EXCERPT_BYTES = 512
MAX_AGENT_TOOL_RESULT_BYTES = 4096


def utf8_prefix(value: str, maximum_bytes: int) -> str:
    """Return a valid UTF-8 prefix without exceeding the explicit byte ceiling."""

    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[:maximum_bytes].decode("utf-8", errors="ignore")


class FetchedSourceRef(Contract):
    source_id: NonEmpty
    candidate_id: NonEmpty
    url: NonEmpty
    source_url: NonEmpty
    title: str | None = Field(default=None, max_length=200)
    source_type: SourceType
    content_type: NonEmpty
    content_length: int = Field(ge=1)
    retrieved_at: UtcInstant
    bounded_excerpt: str = Field(max_length=MAX_AGENT_SOURCE_REF_EXCERPT_BYTES)


def bounded_agent_result(payload: dict) -> dict:
    """Fail closed before an oversized tool observation enters Strands history."""

    if len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")) > (
        MAX_AGENT_TOOL_RESULT_BYTES
    ):
        raise ValueError("AGENT_TOOL_RESULT_TOO_LARGE")
    return payload
