"""Section-scoped model proposals grounded only in run-issued source capabilities."""

import hashlib
import re
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, StrictBool, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category
from qualor.domain.evidence import ClauseContext

from .extraction import (
    EXTRACTION_SYSTEM_CONTRACT,
    MAX_EXTRACTED_CLAIMS_PER_CALL,
    _require_json_array,
    _structured_extraction_request,
)
from .normalization import NormalizedValue
from .section_scheduler import ExtractionJob
from .sections import SectionIndex, _source_revision
from .sources import SourceDocument
from .spans import MAX_EXTRACTION_SOURCE_BYTES, EvidenceSpan, EvidenceSpanRegistry

SpanId = Annotated[str, Field(pattern=r"^span_[a-f0-9]{32}$")]
SpanIds = Annotated[tuple[SpanId, ...], Field(max_length=12)]
_QUALIFIER = re.compile(
    r"\b(?:if|only|provided(?:\s+that)?|subject\s+to|conditional|conditioned|"
    r"pursuant\s+to|as\s+long\s+as|depending|contingent|must\s+not|may\s+not|"
    r"not|neither|without)\b",
    re.IGNORECASE,
)
_EXCEPTION = re.compile(r"\b(?:unless|except|excluding|exempt|exemption)\b", re.IGNORECASE)


class SectionCandidateTransport(Contract):
    category: Category
    proposed_value: NormalizedValue
    source_id: NonEmpty
    section_id: NonEmpty
    span_ids: Annotated[SpanIds, Field(min_length=1)]
    qualifier_span_ids: SpanIds
    exception_span_ids: SpanIds
    confidence_class: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    state: Literal["CANDIDATE", "UNKNOWN"]

    @model_validator(mode="after")
    def explicit_state_and_unique_spans(self) -> Self:
        if (self.state == "UNKNOWN") != (self.proposed_value is None):
            raise ValueError("UNKNOWN forbids a value; CANDIDATE requires one")
        for span_ids in (self.span_ids, self.qualifier_span_ids, self.exception_span_ids):
            if len(set(span_ids)) != len(span_ids):
                raise ValueError("DUPLICATE_EXTRACTION_SPAN")
        return self


class SectionCandidateBatch(Contract):
    claims: Annotated[
        list[SectionCandidateTransport],
        BeforeValidator(_require_json_array),
        Field(max_length=MAX_EXTRACTED_CLAIMS_PER_CALL),
    ]


class GroundedSectionCandidate(Contract):
    candidate: SectionCandidateTransport
    quotes: tuple[str, ...]
    context: ClauseContext
    source: SourceDocument = Field(exclude=True, repr=False)
    semantic_context_complete: StrictBool


def validate_section_payload(payload: object) -> SectionCandidateBatch:
    return SectionCandidateBatch.model_validate(payload)


def _job_context(source, index, job, registry):
    """Validate exact source bindings and retain the full governing context closure."""

    if source.id != index.source_id or source.id != job.source_id:
        raise ValueError("EXTRACTION_SOURCE_REFERENCE_MISMATCH")
    if (
        index.source_revision != _source_revision(source)
        or job.source_revision != index.source_revision
    ):
        raise ValueError("EXTRACTION_SOURCE_REVISION_MISMATCH")
    sections = {section.section_id: section for section in index.sections}
    if job.section_id not in sections:
        raise ValueError("EXTRACTION_SECTION_REFERENCE_MISMATCH")
    target = sections[job.section_id]
    pending = [target.section_id]
    required = set()
    complete = not source.truncated
    while pending:
        section_id = pending.pop()
        if section_id in required:
            continue
        section = sections.get(section_id)
        if section is None:
            raise ValueError("EXTRACTION_SECTION_REFERENCE_MISMATCH")
        required.add(section_id)
        complete = complete and section.context_complete
        pending.extend(section.context_section_ids)
        if section.parent_id is not None:
            pending.append(section.parent_id)
    context_ids = tuple(
        section.section_id
        for section in sorted(sections.values(), key=lambda section: section.start_offset)
        if section.section_id in required and section.section_id != target.section_id
    )
    if tuple(job.context_section_ids) != context_ids:
        raise ValueError("EXTRACTION_JOB_CONTEXT_MISMATCH")
    admitted = (target, *(sections[section_id] for section_id in context_ids))
    expected_ids = tuple(
        dict.fromkeys(span_id for section in admitted for span_id in section.span_ids)
    )
    if job.span_ids != expected_ids or not expected_ids:
        raise ValueError("EXTRACTION_JOB_SPAN_MISMATCH")
    spans = {}
    for section in admitted:
        text = source.text[section.start_offset : section.end_offset]
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != section.section_hash:
            raise ValueError("EXTRACTION_SOURCE_REVISION_MISMATCH")
        if not section.span_ids:
            complete = False
        cursor = section.start_offset
        for span_id in section.span_ids:
            span = registry.resolve(source.id, span_id)
            if not (
                section.start_offset <= span.start_offset < span.end_offset <= section.end_offset
                and source.text[span.start_offset : span.end_offset] == span.exact_text
            ):
                raise ValueError("EXTRACTION_SPAN_SOURCE_MISMATCH")
            if span.start_offset < cursor or source.text[cursor : span.start_offset].strip():
                raise ValueError("EXTRACTION_JOB_SPAN_MISMATCH")
            cursor = span.end_offset
            spans[span_id] = span
        if source.text[cursor : section.end_offset].strip():
            raise ValueError("EXTRACTION_JOB_SPAN_MISMATCH")
    if len(spans) > 12 or len(context_ids) > 12:
        raise ValueError("EXTRACTION_CONTEXT_TOO_LARGE")
    if (
        sum(len(span.exact_text.encode("utf-8")) for span in spans.values())
        > MAX_EXTRACTION_SOURCE_BYTES
    ):
        raise ValueError("EXTRACTION_CONTEXT_TOO_LARGE")
    return target, context_ids, spans, complete


def _selected_spans(span_ids, *, source, allowed, registry) -> tuple[EvidenceSpan, ...]:
    result = tuple(registry.resolve(source.id, span_id) for span_id in span_ids)
    if any(span.span_id not in allowed for span in result):
        raise ValueError("EXTRACTION_SPAN_NOT_ALLOWED")
    if tuple(span.start_offset for span in result) != tuple(
        sorted(span.start_offset for span in result)
    ):
        raise ValueError("EXTRACTION_SPAN_ORDER_INVALID")
    return result


def _condition_spans(pattern, source, ordered) -> set[str]:
    """Inspect continuous exact clause text, including markers split across spans."""

    groups = []
    for span in ordered:
        if groups and not source.text[groups[-1][-1].end_offset : span.start_offset].strip():
            groups[-1].append(span)
        else:
            groups.append([span])
    detected = set()
    for group in groups:
        start = group[0].start_offset
        text = source.text[start : group[-1].end_offset]
        for match in pattern.finditer(text):
            clause_start = max(text.rfind(mark, 0, match.start()) for mark in ".;\n") + 1
            ends = [position for mark in ".;\n" if (position := text.find(mark, match.end())) >= 0]
            clause_end = min(ends) + 1 if ends else len(text)
            detected.update(
                span.span_id
                for span in group
                if span.start_offset < start + clause_end and span.end_offset > start + clause_start
            )
    return detected


def ground_section_claim(
    candidate: SectionCandidateTransport,
    *,
    source: SourceDocument,
    index: SectionIndex,
    job: ExtractionJob,
    registry: EvidenceSpanRegistry,
) -> GroundedSectionCandidate:
    candidate = SectionCandidateTransport.model_validate(candidate)
    if candidate.source_id != source.id:
        raise ValueError("EXTRACTION_SOURCE_REFERENCE_MISMATCH")
    if candidate.section_id != job.section_id:
        raise ValueError("EXTRACTION_SECTION_REFERENCE_MISMATCH")
    if candidate.category not in job.categories:
        raise ValueError("EXTRACTION_CATEGORY_NOT_ALLOWED")
    target, context_ids, allowed, complete = _job_context(source, index, job, registry)
    selected = tuple(
        _selected_spans(ids, source=source, allowed=allowed, registry=registry)
        for ids in (candidate.span_ids, candidate.qualifier_span_ids, candidate.exception_span_ids)
    )
    quotes, qualifiers, exceptions = selected
    if not any(span.span_id in target.span_ids for span in quotes):
        raise ValueError("EXTRACTION_SECTION_SUPPORT_REQUIRED")
    ordered = tuple(sorted(allowed.values(), key=lambda span: span.start_offset))
    detected_qualifiers = _condition_spans(_QUALIFIER, source, ordered)
    detected_exceptions = _condition_spans(_EXCEPTION, source, ordered)
    # Every inherited/reference span governs this section, even when its wording
    # has no recognized condition marker. Retain it exactly and require explicit
    # interpretation; empty model arrays cannot erase that governing text.
    context_spans = set(allowed) - set(target.span_ids)
    detected_qualifiers |= context_spans - detected_exceptions
    qualifier_ids = {span.span_id for span in qualifiers}
    exception_ids = {span.span_id for span in exceptions}
    semantic_complete = (
        complete
        and candidate.state == "CANDIDATE"
        and detected_qualifiers <= qualifier_ids
        and detected_exceptions <= exception_ids
    )
    context = ClauseContext(
        source_id=source.id,
        section_id=target.section_id,
        span_ids=tuple(span.span_id for span in ordered),
        qualifiers=tuple(
            span.exact_text
            for span in ordered
            if span.span_id in qualifier_ids | detected_qualifiers
        ),
        exceptions=tuple(
            span.exact_text
            for span in ordered
            if span.span_id in exception_ids | detected_exceptions
        ),
        context_section_ids=context_ids,
        context_complete=complete,
    )
    return GroundedSectionCandidate(
        candidate=candidate,
        quotes=tuple(span.exact_text for span in quotes),
        context=context,
        source=source,
        semantic_context_complete=semantic_complete,
    )


def build_section_extraction_request(
    source: SourceDocument,
    index: SectionIndex,
    job: ExtractionJob,
    registry: EvidenceSpanRegistry,
    *,
    max_output_tokens: int,
) -> dict:
    target, context_ids, spans, complete = _job_context(source, index, job, registry)
    if not complete:
        raise ValueError("EXTRACTION_CONTEXT_UNRESOLVED")
    span_sections = {
        span_id: section.section_id for section in index.sections for span_id in section.span_ids
    }
    payload = {
        "source_id": source.id,
        "section_id": target.section_id,
        "source_url": source.final_url,
        "source_type": source.authority,
        "retrieved_at": str(source.retrieved_at),
        "allowed_categories": [category.value for category in job.categories],
        "context_section_ids": context_ids,
        "EVIDENCE_SPANS": [
            {
                "span_id": span.span_id,
                "section_id": span_sections[span.span_id],
                "exact_text": span.exact_text,
            }
            for span in sorted(spans.values(), key=lambda span: span.start_offset)
        ],
    }
    system = EXTRACTION_SYSTEM_CONTRACT.replace(
        "Select only a supplied supporting_span_id.",
        "Select supplied span_ids, qualifier_span_ids, and exception_span_ids in source order.",
    ) + (
        " Return only the allowed categories for the target section. Retain all applicable "
        "qualifiers and exceptions, including parent and referenced context. Confidence is "
        "commentary, never support. Unknown interpretation must remain UNKNOWN."
    )
    return _structured_extraction_request(
        payload, SectionCandidateBatch, max_output_tokens=max_output_tokens, system=system
    )
