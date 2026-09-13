"""Opaque run-scoped capabilities for exact fetched-source evidence spans."""

import hashlib
import hmac
import secrets
from typing import Self

from pydantic import Field, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.evidence import MAX_EVIDENCE_EXCERPT_CHARS

from .sources import SourceDocument

MAX_EVIDENCE_SPAN_BYTES = 800
MAX_EXTRACTION_SOURCE_BYTES = 9_000
# Mirrors the scheduler's MAX_EXTRACTION_JOB_SPAN_IDS, which imports this module.
MAX_SECTION_SPAN_IDS = 12


class EvidenceSpan(Contract):
    """An exact, bounded slice of the canonical fetched-source text."""

    span_id: str = Field(pattern=r"^span_[a-f0-9]{32}$")
    source_id: NonEmpty
    exact_text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)

    @model_validator(mode="after")
    def exact_offsets(self) -> Self:
        if self.end_offset - self.start_offset != len(self.exact_text):
            raise ValueError("SPAN_OFFSETS_DO_NOT_MATCH_TEXT")
        if len(self.exact_text) > MAX_EVIDENCE_EXCERPT_CHARS:
            raise ValueError("EVIDENCE_SPAN_TOO_MANY_CHARACTERS")
        if len(self.exact_text.encode("utf-8")) > MAX_EVIDENCE_SPAN_BYTES:
            raise ValueError("EVIDENCE_SPAN_TOO_LARGE")
        return self


def extraction_window(source_text: str, focus: str) -> tuple[int, str]:
    """Return the same bounded canonical-text window used for extraction."""

    encoded = source_text.encode("utf-8")
    if len(encoded) <= MAX_EXTRACTION_SOURCE_BYTES:
        return 0, source_text
    position = source_text.casefold().find(focus.casefold())
    start = max(0, position - 1_000) if position >= 0 else 0
    end = start
    used = 0
    while end < len(source_text):
        size = len(source_text[end].encode("utf-8"))
        if used + size > MAX_EXTRACTION_SOURCE_BYTES:
            break
        used += size
        end += 1
    return start, source_text[start:end]


def _max_character_end(
    text: str, start: int, byte_limit: int, character_limit: int
) -> int:
    end = start
    used = 0
    while end < len(text) and end - start < character_limit:
        size = len(text[end].encode("utf-8"))
        if used + size > byte_limit:
            break
        used += size
        end += 1
    return end


def _semantic_end(text: str, start: int, maximum: int) -> int:
    """Prefer paragraph/list/sentence boundaries without exceeding either cap."""

    if maximum == len(text):
        return maximum
    minimum = start + max(1, (maximum - start) // 2)
    region = text[start:maximum]
    for separator in ("\n\n", "\n", ". ", "; ", " "):
        position = region.rfind(separator)
        candidate = start + position + (1 if separator in {". ", "; "} else len(separator))
        if position >= 0 and candidate >= minimum:
            return candidate
    return maximum


def _segments(text: str, *, absolute_start: int) -> tuple[tuple[int, int, str], ...]:
    result = []
    cursor = 0
    while cursor < len(text):
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text):
            break
        maximum = _max_character_end(
            text,
            cursor,
            MAX_EVIDENCE_SPAN_BYTES,
            MAX_EVIDENCE_EXCERPT_CHARS,
        )
        end = _semantic_end(text, cursor, maximum)
        while end > cursor and text[end - 1].isspace():
            end -= 1
        if end <= cursor:
            end = maximum
        exact = text[cursor:end]
        result.append((absolute_start + cursor, absolute_start + end, exact))
        cursor = max(end, maximum if end <= cursor else end)
    return tuple(result)


def _section_segments(text: str, *, absolute_start: int) -> tuple[tuple[int, int, str], ...]:
    """Structural capabilities for an explicit section range.

    Paragraph and list/line layout are the boundaries, so a label and its value stay
    separately selectable without multiplying dense prose into one span per sentence.
    A line still over either bound falls through to the size-bound segmenter. Every
    non-whitespace character keeps exactly one capability at its original offset.

    A section whose lines would not fit one extraction job keeps the size-bound
    segmentation instead, so finer layout never costs the section its reachability.
    """

    result = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        exact = line.strip()
        if exact:
            begin = cursor + len(line) - len(line.lstrip())
            if (
                len(exact) > MAX_EVIDENCE_EXCERPT_CHARS
                or len(exact.encode("utf-8")) > MAX_EVIDENCE_SPAN_BYTES
            ):
                result.extend(_segments(exact, absolute_start=absolute_start + begin))
            else:
                result.append(
                    (absolute_start + begin, absolute_start + begin + len(exact), exact)
                )
        cursor += len(line)
    if len(result) > MAX_SECTION_SPAN_IDS:
        return _segments(text, absolute_start=absolute_start)
    return tuple(result)


class EvidenceSpanRegistry:
    """Issues unforgeable span capabilities scoped to one run/extractor instance."""

    def __init__(self, *, secret: bytes | None = None):
        secret = secret or secrets.token_bytes(32)
        if len(secret) < 32:
            raise ValueError("SPAN_REGISTRY_SECRET_TOO_SHORT")
        self._secret = secret
        self._spans: dict[str, EvidenceSpan] = {}
        self.last_registered_span_ids: tuple[str, ...] = ()

    def _register_range(
        self,
        source: SourceDocument,
        *,
        start_offset: int,
        end_offset: int,
        segmenter=_segments,
    ) -> tuple[EvidenceSpan, ...]:
        spans = []
        text = source.text[start_offset:end_offset]
        for start, end, exact_text in segmenter(text, absolute_start=start_offset):
            material = (
                f"{source.id}\0{start}\0{end}\0".encode()
                + hashlib.sha256(exact_text.encode("utf-8")).digest()
            )
            span_id = "span_" + hmac.new(self._secret, material, hashlib.sha256).hexdigest()[:32]
            span = EvidenceSpan(
                span_id=span_id,
                source_id=source.id,
                exact_text=exact_text,
                start_offset=start,
                end_offset=end,
            )
            self._spans[span_id] = span
            spans.append(span)
        self.last_registered_span_ids = tuple(span.span_id for span in spans)
        return tuple(spans)

    def register(self, source: SourceDocument, focus: str) -> tuple[EvidenceSpan, ...]:
        window_start, window = extraction_window(source.text, focus)
        return self._register_range(
            source,
            start_offset=window_start,
            end_offset=window_start + len(window),
        )

    def register_section(
        self, source: SourceDocument, *, start_offset: int, end_offset: int
    ) -> tuple[EvidenceSpan, ...]:
        """Issue capabilities only for an explicit exact section range."""

        if (
            isinstance(start_offset, bool)
            or isinstance(end_offset, bool)
            or not isinstance(start_offset, int)
            or not isinstance(end_offset, int)
            or start_offset < 0
            or end_offset <= start_offset
            or end_offset > len(source.text)
        ):
            raise ValueError("SECTION_OFFSETS_INVALID")
        return self._register_range(
            source,
            start_offset=start_offset,
            end_offset=end_offset,
            segmenter=_section_segments,
        )

    def resolve(self, source_id: str, span_id: str) -> EvidenceSpan:
        span = self._spans.get(span_id)
        if span is None:
            raise ValueError("SPAN_REFERENCE_NOT_FOUND")
        if span.source_id != source_id:
            raise ValueError("SPAN_SOURCE_MISMATCH")
        return span
