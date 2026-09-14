"""Deterministic, full-document indexing of canonical fetched-source text."""

import hashlib
import re
from enum import StrEnum
from typing import Literal, Self
from urllib.parse import urldefrag, urlsplit, urlunsplit

from pydantic import Field, StrictBool, model_validator

from qualor.domain.base import Contract, NonEmpty
from qualor.domain.enums import Category
from qualor.domain.evidence import MAX_EVIDENCE_EXCERPT_CHARS

from .sources import SourceDocument
from .spans import MAX_EVIDENCE_SPAN_BYTES, EvidenceSpanRegistry

INDEXER_VERSION = "section-index-v2"
ROUTING_VERSION = "bounded-acquisition-routing-v1"
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
_SEMANTIC_SEPARATORS = ("\n\n", "\n", ". ", "; ")
_WEAK_SEPARATORS = (" ",)
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


class SectionRoutingReason(StrEnum):
    BODY_CATEGORY_TERM = "BODY_CATEGORY_TERM"
    HEADING_CATEGORY_TERM = "HEADING_CATEGORY_TERM"
    RULE_LIKE_MARKER = "RULE_LIKE_MARKER"
    STRUCTURAL_REFERENCE = "STRUCTURAL_REFERENCE"
    GLOBAL_SCOPE = "GLOBAL_SCOPE"


class RuleLikeMarker(StrEnum):
    OBLIGATION = "OBLIGATION"
    PROHIBITION = "PROHIBITION"
    LIMITATION = "LIMITATION"
    PERMISSION_OR_SCOPE = "PERMISSION_OR_SCOPE"
    TECHNOLOGY_OR_LICENSE = "TECHNOLOGY_OR_LICENSE"
    FINANCIAL_OR_REWARD = "FINANCIAL_OR_REWARD"
    SUBMISSION_OR_TIME = "SUBMISSION_OR_TIME"
    EVALUATION_OR_SELECTION = "EVALUATION_OR_SELECTION"
    STRUCTURAL_RULE_ITEM = "STRUCTURAL_RULE_ITEM"


class RuleLikeRouting(Contract):
    rule_like: StrictBool
    category_hints: tuple[Category, ...]
    marker_codes: tuple[RuleLikeMarker, ...]

    @model_validator(mode="after")
    def unique_values(self) -> Self:
        if len(set(self.category_hints)) != len(self.category_hints):
            raise ValueError("DUPLICATE_RULE_LIKE_CATEGORY_HINT")
        if len(set(self.marker_codes)) != len(self.marker_codes):
            raise ValueError("DUPLICATE_RULE_LIKE_MARKER")
        return self


class SectionRoutingMetadata(Contract):
    routing_version: Literal["bounded-acquisition-routing-v1"] = ROUTING_VERSION
    body_categories: tuple[Category, ...]
    heading_categories: tuple[Category, ...]
    rule_like: StrictBool
    rule_like_category_hints: tuple[Category, ...]
    reason_codes: tuple[SectionRoutingReason, ...]

    @model_validator(mode="after")
    def unique_values(self) -> Self:
        for values, code in (
            (self.body_categories, "DUPLICATE_BODY_CATEGORY"),
            (self.heading_categories, "DUPLICATE_HEADING_CATEGORY"),
            (self.rule_like_category_hints, "DUPLICATE_RULE_LIKE_CATEGORY_HINT"),
            (self.reason_codes, "DUPLICATE_ROUTING_REASON"),
        ):
            if len(set(values)) != len(values):
                raise ValueError(code)
        return self


_RULE_MARKERS = {
    RuleLikeMarker.OBLIGATION: re.compile(
        r"\b(?:must|required|shall|condition|subject\s+to)\b", re.IGNORECASE
    ),
    RuleLikeMarker.PROHIBITION: re.compile(
        r"\b(?:must\s+not|may\s+not|prohibited|ineligible)\b", re.IGNORECASE
    ),
    RuleLikeMarker.LIMITATION: re.compile(
        r"\b(?:only|unless|except)\b", re.IGNORECASE
    ),
    RuleLikeMarker.PERMISSION_OR_SCOPE: re.compile(
        r"\b(?:eligible|resident|participant|team|project)\w*\b", re.IGNORECASE
    ),
    RuleLikeMarker.TECHNOLOGY_OR_LICENSE: re.compile(
        r"\b(?:licen[cs]e|copyright|technology|api|sdk)\w*\b", re.IGNORECASE
    ),
    RuleLikeMarker.FINANCIAL_OR_REWARD: re.compile(
        r"\b(?:funding|support|prize|award|winner)\w*\b", re.IGNORECASE
    ),
    RuleLikeMarker.SUBMISSION_OR_TIME: re.compile(
        r"\b(?:submit|submission|deadline)\w*\b", re.IGNORECASE
    ),
    RuleLikeMarker.EVALUATION_OR_SELECTION: re.compile(
        r"\b(?:judge|judging|criteria|score|points?|tie)\w*\b", re.IGNORECASE
    ),
}
_STRUCTURAL_RULE_PREFIX = re.compile(
    r"^\s*(?:[-*\u2022]\s+|(?:\d+|[A-Za-z])[.):]\s+)"
)
_DEFINITION_ENTRY = re.compile(r"^\s*[^\n:—-]+\s*(?::|—|-)\s*\S+")
_RULE_CATEGORY_TERMS = {
    Category.DEADLINE: re.compile(r"\b(?:submit|submission|deadline)\w*\b"),
    Category.ENTRANT_TYPE: re.compile(
        r"\b(?:eligible|entrant|applicant|participant|individual|team)\w*\b"
    ),
    Category.GEOGRAPHY: re.compile(r"\b(?:resident|residency|country|citizen)\w*\b"),
    Category.LEGAL_ENTITY: re.compile(
        r"\b(?:legal\s+entity|incorporated|company|nonprofit|sole\s+trader)\b"
    ),
    Category.PROJECT_POLICY: re.compile(r"\b(?:project|new\s+work|existing\s+work)\w*\b"),
    Category.LICENSE: re.compile(r"\b(?:licen[cs]e|copyright|mit|apache)\w*\b"),
    Category.REQUIRED_TECHNOLOGY: re.compile(r"\b(?:technology|api|sdk|framework)\w*\b"),
    Category.FINANCIAL_SUPPORT: re.compile(r"\b(?:funding|support|cloud\s+credits?)\w*\b"),
    Category.REWARD_CONDITIONS: re.compile(
        r"\b(?:prize|reward|award|winner|verification|judge|judging|criteria|score|points?|tie)\w*\b"
    ),
}


def _has_governing_marker(markers: tuple[RuleLikeMarker, ...]) -> bool:
    return any(
        marker
        in {
            RuleLikeMarker.OBLIGATION,
            RuleLikeMarker.PROHIBITION,
            RuleLikeMarker.LIMITATION,
        }
        for marker in markers
    )


def _is_structural_rule_item(
    body_text: str,
    heading_categories: tuple[Category, ...],
    markers: tuple[RuleLikeMarker, ...],
) -> bool:
    return bool(_STRUCTURAL_RULE_PREFIX.match(body_text)) and bool(
        heading_categories or _has_governing_marker(markers)
    )


def detect_rule_like_routing(
    *, heading_text: str | None, body_text: str
) -> RuleLikeRouting:
    normalized_body = " ".join(body_text.casefold().split())
    marker_codes = tuple(
        marker
        for marker in RuleLikeMarker
        if marker in _RULE_MARKERS
        and _RULE_MARKERS[marker].search(normalized_body)
    )
    heading_categories = _categories(heading_text or "")
    if _is_structural_rule_item(body_text, heading_categories, marker_codes):
        marker_codes += (RuleLikeMarker.STRUCTURAL_RULE_ITEM,)
    category_hints = tuple(
        category
        for category in Category
        if _RULE_CATEGORY_TERMS[category].search(normalized_body)
    )
    definition_entry = bool(_DEFINITION_ENTRY.match(body_text))
    return RuleLikeRouting(
        rule_like=bool(marker_codes or definition_entry),
        category_hints=category_hints,
        marker_codes=marker_codes,
    )


class SourceSection(Contract):
    section_id: str = Field(pattern=r"^section_[a-f0-9]{32}$")
    source_id: NonEmpty
    source_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    heading: str | None = None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    span_ids: tuple[str, ...]
    section_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    routing: SectionRoutingMetadata
    candidate_categories: tuple[Category, ...] = ()
    parent_id: str | None = None
    context_section_ids: tuple[str, ...] = ()
    context_complete: bool = True

    @model_validator(mode="after")
    def valid_section(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("SECTION_OFFSETS_INVALID")
        expected_categories = tuple(
            category
            for category in Category
            if category in self.routing.body_categories
            or category in self.routing.heading_categories
        )
        if self.candidate_categories != expected_categories:
            raise ValueError("CANDIDATE_CATEGORY_ROUTING_MISMATCH")
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


def _bounded_ranges(text: str, start: int, end: int) -> tuple[tuple[int, int, bool], ...]:
    """Split an oversized region, recording whether each cut is a structural boundary.

    A paragraph, line, sentence or semicolon cut ends a clause. An ordinary space or
    the hard size cap can sever one, so the caller must fail closed on those instead
    of guessing which governing text was cut in half.
    """

    ranges = []
    cursor = start
    while cursor < end:
        maximum = _maximum_end(text, cursor, end)
        if maximum <= cursor:
            raise ValueError("SECTION_CHARACTER_EXCEEDS_BYTE_LIMIT")
        boundary = maximum
        # The region's own end is not a cut, so it never severs a clause.
        boundary_safe = True
        if maximum < end:
            boundary_safe = False
            minimum = cursor + max(1, (maximum - cursor) // 2)
            region = text[cursor:maximum]
            for separator in (*_SEMANTIC_SEPARATORS, *_WEAK_SEPARATORS):
                position = region.rfind(separator)
                candidate = cursor + position + len(separator)
                if position >= 0 and candidate >= minimum:
                    boundary = candidate
                    boundary_safe = separator in _SEMANTIC_SEPARATORS
                    break
        ranges.append((cursor, boundary, boundary_safe))
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


def _body_without_heading(
    text: str,
    start: int,
    end: int,
    heading: str | None,
    logical_start: int,
) -> str:
    exact = text[start:end]
    if heading is None or start != logical_start or not exact.startswith(heading):
        return exact
    body_start = len(heading)
    if exact[body_start : body_start + 2] == "\r\n":
        body_start += 2
    elif exact[body_start : body_start + 1] in {"\r", "\n"}:
        body_start += 1
    return exact[body_start:]


def _heading_number(heading: str | None) -> str | None:
    if heading is None:
        return None
    match = _NUMBERED_HEADING.match(heading.strip())
    return match.group("number") if match else None


def _number_depth(number: str) -> int:
    return number.count(".") + 1


def _ancestor_numbers(number: str) -> tuple[str, ...]:
    parts = number.split(".")
    return tuple(".".join(parts[:depth]) for depth in range(len(parts) - 1, 0, -1))


def _structural_ancestry(
    number: str | None,
    start_offset: int,
    numbered: dict[str, list[tuple[int, list[str]]]],
    numbered_sequence: list[tuple[int, str]],
) -> tuple[tuple[str, ...], bool]:
    if number is None or "." not in number:
        return (), False

    context_ids = []
    incomplete = False
    for ancestor_number in _ancestor_numbers(number):
        candidates = numbered.get(ancestor_number, [])
        preceding = [group_ids for start, group_ids in candidates if start < start_offset]
        if not candidates or len(candidates) > 1 or not preceding:
            incomplete = True
        context_ids.extend(context_id for group_ids in preceding for context_id in group_ids)

        ancestor_depth = _number_depth(ancestor_number)
        preceding_at_depth = [
            preceding_number
            for preceding_start, preceding_number in numbered_sequence
            if preceding_start < start_offset and _number_depth(preceding_number) <= ancestor_depth
        ]
        if not preceding_at_depth or preceding_at_depth[-1] != ancestor_number:
            incomplete = True

    return tuple(context_ids), incomplete


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
    severed = set()
    for logical_start, logical_end, heading in _logical_regions(source.text):
        ranges = _bounded_ranges(source.text, logical_start, logical_end)
        group_indexes = []
        heading_categories = _categories(heading or "")
        parent_id = None
        for position, (start, end, boundary_safe) in enumerate(ranges):
            exact_text = source.text[start:end]
            body_text = _body_without_heading(
                source.text, start, end, heading, logical_start
            )
            body_categories = _categories(body_text)
            rule_like = detect_rule_like_routing(
                heading_text=heading,
                body_text=body_text,
            )
            candidate_categories = tuple(
                category
                for category in Category
                if category in body_categories or category in heading_categories
            )
            initial_reasons = {
                *(
                    (SectionRoutingReason.BODY_CATEGORY_TERM,)
                    if body_categories
                    else ()
                ),
                *(
                    (SectionRoutingReason.HEADING_CATEGORY_TERM,)
                    if heading_categories
                    else ()
                ),
                *(
                    (SectionRoutingReason.RULE_LIKE_MARKER,)
                    if rule_like.rule_like
                    else ()
                ),
            }
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
                    "routing": SectionRoutingMetadata(
                        body_categories=body_categories,
                        heading_categories=heading_categories,
                        rule_like=rule_like.rule_like,
                        rule_like_category_hints=rule_like.category_hints,
                        reason_codes=tuple(
                            reason
                            for reason in SectionRoutingReason
                            if reason in initial_reasons
                        ),
                    ),
                    "candidate_categories": candidate_categories,
                    "parent_id": parent_id if position else None,
                }
            )
            group_indexes.append(len(drafts) - 1)
            if not boundary_safe:
                # Either side of a forced cut may hold half of a governing clause.
                severed.update({len(drafts) - 1, len(drafts)})
        logical_groups.append((group_indexes, logical_start, logical_end, heading))

    numbered = {}
    numbered_sequence = []
    global_ids = []
    for indexes, logical_start, logical_end, heading in logical_groups:
        group_ids = [drafts[index]["section_id"] for index in indexes]
        number = _heading_number(heading)
        if number is not None:
            numbered.setdefault(number, []).append((logical_start, group_ids))
            numbered_sequence.append((logical_start, number))
        folded = source.text[logical_start:logical_end].casefold()
        if any(marker in folded for marker in _GLOBAL_SCOPE):
            global_ids.extend(group_ids)

    drafts_by_id = {draft["section_id"]: draft for draft in drafts}
    for indexes, logical_start, logical_end, heading in logical_groups:
        folded = source.text[logical_start:logical_end].casefold()
        references, unsupported_reference = _section_references(folded)
        unresolved = any(reference not in numbered for reference in references)
        ambiguous = any(len(numbered.get(reference, ())) > 1 for reference in references)
        unbounded = any(marker in folded for marker in _UNBOUNDED_CONTEXT)
        ancestry_ids, ancestry_incomplete = _structural_ancestry(
            _heading_number(heading), logical_start, numbered, numbered_sequence
        )
        inherited_incomplete = any(
            not drafts_by_id[context_id].get("context_complete", True)
            for context_id in ancestry_ids
        )
        referenced_ids = [
            context_id
            for reference in references
            if reference in numbered
            for _target_start, target_group in numbered[reference]
            for context_id in target_group
        ]
        group_ids = [drafts[index]["section_id"] for index in indexes]
        for draft_index in indexes:
            draft = drafts[draft_index]
            routing_reasons = set(draft["routing"].reason_codes)
            if references or unsupported_reference:
                routing_reasons.add(SectionRoutingReason.STRUCTURAL_REFERENCE)
            if any(marker in folded for marker in _GLOBAL_SCOPE):
                routing_reasons.add(SectionRoutingReason.GLOBAL_SCOPE)
            draft["routing"] = draft["routing"].model_copy(
                update={
                    "reason_codes": tuple(
                        reason
                        for reason in SectionRoutingReason
                        if reason in routing_reasons
                    )
                }
            )
            ordered_context = []
            # A bounded child inherits its parent, not every sibling that happened to
            # fit beside it. Structural ancestry, explicit references and expressly
            # global sections remain governing context in their own right.
            for context_id in (
                ([draft["parent_id"]] if draft["parent_id"] is not None else [])
                + list(ancestry_ids)
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
                or ancestry_incomplete
                or inherited_incomplete
                or overflow
                or draft_index in severed
            )

    sections = tuple(SourceSection(**draft) for draft in drafts)

    return SectionIndex(
        source_id=source.id,
        source_revision=revision,
        indexer_version=INDEXER_VERSION,
        sections=sections,
    )
