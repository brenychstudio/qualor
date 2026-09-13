"""Deterministic, full-document indexing of canonical fetched-source text."""

import hashlib
import re
from typing import Self
from urllib.parse import urldefrag, urlsplit, urlunsplit

from pydantic import Field, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category
from qualor.domain.evidence import MAX_EVIDENCE_EXCERPT_CHARS

from .sources import SourceDocument
from .spans import MAX_EVIDENCE_SPAN_BYTES, EvidenceSpanRegistry

INDEXER_VERSION = "section-index-v1"
MAX_CONTEXT_SECTION_IDS = 12

_NUMBERED_HEADING = re.compile(
    r"^(?:section\s+)?(?P<number>\d+(?:\.\d+)*)(?:[.)]|\s*[:\-])?\s+",
    re.IGNORECASE,
)
_SECTION_NUMBER = r"\d+(?:\.\d+)*"
_SECTION_REFERENCE = re.compile(
    rf"\bsections?\s+(?P<targets>{_SECTION_NUMBER}"
    rf"(?:\s*(?:,\s*(?:and\s+)?|and\s+){_SECTION_NUMBER})*)",
    re.IGNORECASE,
)
_REFERENCE_INTENT = re.compile(
    r"\b(?:subject to|pursuant to|under|see|as provided in|provided in)\b"
    r"[^.;\n]{0,48}?\bsections?\b[^.;\n]*",
    re.IGNORECASE,
)
_UNSUPPORTED_REFERENCE_SUFFIX = re.compile(
    r"^\s*(?:[-/&()]|and\b|through\b|to\b|or\b)", re.IGNORECASE
)
_HEADING_TERMS = (
    "submission period",
    "deadline",
    "eligibility",
    "geography",
    "residency",
    "legal",
    "entity",
    "project requirements",
    "new work",
    "license",
    "technology",
    "financial",
    "support",
    "prizes",
    "reward",
    "verification",
)
_GLOBAL_SCOPE = (
    "applies to all sections",
    "applicable to all sections",
    "governs all sections",
    "throughout these rules",
)
_UNBOUNDED_CONTEXT = (
    "unless otherwise stated",
    "unless otherwise specified",
    "unless otherwise provided",
    "except as otherwise provided",
)
_CATEGORY_TERMS = {
    Category.DEADLINE: (
        "deadline",
        "submission period",
        "submit by",
        "closing date",
        "closes on",
        "opens on",
    ),
    Category.ENTRANT_TYPE: (
        "eligibility",
        "eligible",
        "entrant",
        "applicant",
        "participant",
        "individual",
        "team",
    ),
    Category.GEOGRAPHY: (
        "eligibility",
        "geography",
        "residency",
        "resident",
        "country",
        "countries",
        "citizen",
    ),
    Category.LEGAL_ENTITY: (
        "eligibility",
        "legal entity",
        "incorporated",
        "company",
        "nonprofit",
        "sole trader",
    ),
    Category.PROJECT_POLICY: (
        "project requirements",
        "submission requirements",
        "new work",
        "new project",
        "existing work",
        "existing project",
    ),
    Category.LICENSE: ("license", "licensed", "mit", "apache", "open source", "open-source"),
    Category.REQUIRED_TECHNOLOGY: (
        "technology",
        " sdk",
        "sdk ",
        " api",
        "api ",
        "framework",
    ),
    Category.FINANCIAL_SUPPORT: (
        "financial support",
        "sponsor support",
        "funding",
        "cloud credit",
        "cloud credits",
    ),
    Category.REWARD_CONDITIONS: (
        "prize",
        "reward",
        "award",
        "winner",
        "verification",
    ),
}


class SourceSection(Contract):
    section_id: str = Field(pattern=r"^section_[a-f0-9]{32}$")
    source_id: NonEmpty
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    heading: str | None = None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    span_ids: tuple[str, ...]
    section_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_categories: tuple[Category, ...] = ()
    parent_id: str | None = None
    context_section_ids: tuple[str, ...] = ()
    context_complete: bool = True

    @model_validator(mode="after")
    def valid_section(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("SECTION_OFFSETS_INVALID")
        if len(set(self.span_ids)) != len(self.span_ids):
            raise ValueError("DUPLICATE_SECTION_SPAN")
        if len(set(self.context_section_ids)) != len(self.context_section_ids):
            raise ValueError("DUPLICATE_SECTION_CONTEXT")
        return self


class SectionIndex(Contract):
    source_id: NonEmpty
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    indexer_version: NonEmpty
    sections: tuple[SourceSection, ...]

    @model_validator(mode="after")
    def consistent_index(self) -> Self:
        ids = {section.section_id for section in self.sections}
        if len(ids) != len(self.sections):
            raise ValueError("DUPLICATE_SECTION_ID")
        for section in self.sections:
            if (
                section.source_id != self.source_id
                or section.source_revision != self.source_revision
            ):
                raise ValueError("SECTION_SOURCE_MISMATCH")
            if section.parent_id is not None and section.parent_id not in ids:
                raise ValueError("SECTION_PARENT_NOT_FOUND")
            if any(context_id not in ids for context_id in section.context_section_ids):
                raise ValueError("SECTION_CONTEXT_NOT_FOUND")
        return self


def _normalized_url(url: str) -> str:
    parts = urlsplit(urldefrag(url).url)
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port not in (None, 443) else ""
    return urlunsplit((parts.scheme.lower(), host + port, parts.path or "/", parts.query, ""))


def _source_revision(source: SourceDocument) -> str:
    material = f"{_normalized_url(source.final_url)}\0{source.content_hash}".encode()
    return hashlib.sha256(material).hexdigest()


def _section_id(
    source_revision: str, start_offset: int, end_offset: int, section_hash: str
) -> str:
    material = (
        f"{source_revision}\0{INDEXER_VERSION}\0{start_offset}\0{end_offset}\0{section_hash}"
    ).encode()
    return "section_" + hashlib.sha256(material).hexdigest()[:32]


def _is_heading(line: str) -> bool:
    candidate = line.strip()
    if not candidate or len(candidate) > 100 or candidate.endswith((".", "!", "?", ";")):
        return False
    folded = candidate.casefold()
    return bool(_NUMBERED_HEADING.match(candidate)) or any(
        term in folded for term in _HEADING_TERMS
    )


def _logical_regions(text: str) -> tuple[tuple[int, int, str | None], ...]:
    headings = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        exact = line.rstrip("\r\n")
        if _is_heading(exact):
            headings.append((cursor, exact))
        cursor += len(line)
    if not headings:
        return ((0, len(text), None),)
    regions = []
    if headings[0][0] > 0:
        regions.append((0, headings[0][0], None))
    for position, (start, heading) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(text)
        regions.append((start, end, heading))
    return tuple(regions)


def _maximum_end(text: str, start: int, end: int) -> int:
    cursor = start
    used = 0
    while cursor < end and cursor - start < MAX_EVIDENCE_EXCERPT_CHARS:
        size = len(text[cursor].encode("utf-8"))
        if used + size > MAX_EVIDENCE_SPAN_BYTES:
            break
        used += size
        cursor += 1
    return cursor


def _bounded_ranges(text: str, start: int, end: int) -> tuple[tuple[int, int], ...]:
    ranges = []
    cursor = start
    while cursor < end:
        maximum = _maximum_end(text, cursor, end)
        if maximum <= cursor:
            raise ValueError("SECTION_CHARACTER_EXCEEDS_BYTE_LIMIT")
        boundary = maximum
        if maximum < end:
            minimum = cursor + max(1, (maximum - cursor) // 2)
            region = text[cursor:maximum]
            for separator in ("\n\n", "\n", ". ", "; ", " "):
                position = region.rfind(separator)
                candidate = cursor + position + len(separator)
                if position >= 0 and candidate >= minimum:
                    boundary = candidate
                    break
        ranges.append((cursor, boundary))
        cursor = boundary
    return tuple(ranges)


def _categories(text: str) -> tuple[Category, ...]:
    folded = " " + " ".join(text.casefold().split()) + " "
    return tuple(
        category
        for category in Category
        if any(
            re.search(r"(?<!\w)mit(?!\w)", folded) if term == "mit" else term in folded
            for term in _CATEGORY_TERMS[category]
        )
    )


def _heading_number(heading: str | None) -> str | None:
    if heading is None:
        return None
    match = _NUMBERED_HEADING.match(heading.strip())
    return match.group("number") if match else None


def _section_references(text: str) -> tuple[tuple[str, ...], bool]:
    references = []
    numeric_matches = tuple(_SECTION_REFERENCE.finditer(text))
    unsupported = False
    for match in numeric_matches:
        for number in re.findall(_SECTION_NUMBER, match.group("targets")):
            if number not in references:
                references.append(number)
        if _UNSUPPORTED_REFERENCE_SUFFIX.match(text[match.end() :]):
            unsupported = True
    for intent in _REFERENCE_INTENT.finditer(text):
        if not any(
            intent.start() <= numeric.start() and numeric.end() <= intent.end()
            for numeric in numeric_matches
        ):
            unsupported = True
    return tuple(references), unsupported


def index_source(source: SourceDocument, registry: EvidenceSpanRegistry) -> SectionIndex:
    revision = _source_revision(source)
    drafts = []
    logical_groups = []
    for logical_start, logical_end, heading in _logical_regions(source.text):
        ranges = _bounded_ranges(source.text, logical_start, logical_end)
        group_indexes = []
        logical_categories = _categories(source.text[logical_start:logical_end])
        parent_id = None
        for position, (start, end) in enumerate(ranges):
            exact_text = source.text[start:end]
            section_hash = hashlib.sha256(exact_text.encode("utf-8")).hexdigest()
            identifier = _section_id(revision, start, end, section_hash)
            if position == 0:
                parent_id = identifier
            spans = registry.register_section(source, start_offset=start, end_offset=end)
            drafts.append(
                {
                    "section_id": identifier,
                    "source_id": source.id,
                    "source_revision": revision,
                    "heading": heading if position == 0 else None,
                    "start_offset": start,
                    "end_offset": end,
                    "span_ids": tuple(span.span_id for span in spans),
                    "section_hash": section_hash,
                    "candidate_categories": logical_categories,
                    "parent_id": parent_id if position else None,
                }
            )
            group_indexes.append(len(drafts) - 1)
        logical_groups.append((group_indexes, logical_start, logical_end, heading))

    numbered = {}
    global_ids = []
    for indexes, logical_start, logical_end, heading in logical_groups:
        group_ids = [drafts[index]["section_id"] for index in indexes]
        number = _heading_number(heading)
        if number is not None:
            numbered.setdefault(number, []).append(group_ids)
        folded = source.text[logical_start:logical_end].casefold()
        if any(marker in folded for marker in _GLOBAL_SCOPE):
            global_ids.extend(group_ids)

    sections = []
    for indexes, logical_start, logical_end, _heading in logical_groups:
        folded = source.text[logical_start:logical_end].casefold()
        references, unsupported_reference = _section_references(folded)
        unresolved = any(reference not in numbered for reference in references)
        ambiguous = any(len(numbered.get(reference, ())) > 1 for reference in references)
        unbounded = any(marker in folded for marker in _UNBOUNDED_CONTEXT)
        referenced_ids = [
            context_id
            for reference in references
            if reference in numbered
            for target_group in numbered[reference]
            for context_id in target_group
        ]
        group_ids = [drafts[index]["section_id"] for index in indexes]
        for draft_index in indexes:
            draft = drafts[draft_index]
            ordered_context = []
            for context_id in (
                ([draft["parent_id"]] if draft["parent_id"] is not None else [])
                + group_ids
                + global_ids
                + referenced_ids
            ):
                if context_id != draft["section_id"] and context_id not in ordered_context:
                    ordered_context.append(context_id)
            overflow = len(ordered_context) > MAX_CONTEXT_SECTION_IDS
            draft["context_section_ids"] = tuple(ordered_context[:MAX_CONTEXT_SECTION_IDS])
            draft["context_complete"] = not (
                unresolved
                or ambiguous
                or unsupported_reference
                or unbounded
                or overflow
            )
            sections.append(SourceSection(**draft))

    return SectionIndex(
        source_id=source.id,
        source_revision=revision,
        indexer_version=INDEXER_VERSION,
        sections=tuple(sections),
    )
