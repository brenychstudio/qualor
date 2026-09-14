"""Deterministic runtime test factories with no external side effects."""

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from archived_compiler_support import ArchiveInputError, load_archived_rules

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.enums import Provenance
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.runtime.run_models import StudioInput
from qualor.runtime.sources import SourceDocument


@pytest.fixture
def archived_source():
    """Optional local archive fixture; required mode never converts absence into a skip."""

    selected = os.environ.get("QUALOR_ARCHIVE_DIR")
    required = os.environ.get("QUALOR_REQUIRE_ARCHIVE") == "1"
    if not selected:
        if required:
            raise ArchiveInputError("ARCHIVE_DIRECTORY_INVALID")
        pytest.skip("ARCHIVE_SOURCE_UNAVAILABLE")
    try:
        return load_archived_rules(Path(selected))
    except ArchiveInputError as exc:
        if required or str(exc) not in {
            "ARCHIVE_DIRECTORY_INVALID",
            "ARCHIVE_MANIFEST_MISSING",
            "ARCHIVE_RAW_ARTIFACT_MISSING",
        }:
            raise
        pytest.skip("ARCHIVE_SOURCE_UNAVAILABLE")


@pytest.fixture
def studio_inputs():
    """Synthetic independent facts with no source-derived applicant state."""
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    metadata = {
        "schema_version": "1",
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "provenance": Provenance.USER_ASSERTED,
    }
    founder = FounderProfile(id="independent-founder", **metadata)
    project = ProjectProfile(
        id="independent-project",
        name="Synthetic independent project",
        **metadata,
    )
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Evaluate only independently supplied facts",
        allowed_hosts=("example.org",),
        founder=founder,
        projects=(ProjectDecisionInput(project=project, effort=EffortAssumptions(items=())),),
    )


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


@pytest.fixture
def grounded_candidate(document):
    """Ground supplied exact test substrings; never manufacture rule authority."""

    from qualor.domain.enums import Category
    from qualor.runtime.acquisition_plan import build_acquisition_plan
    from qualor.runtime.section_extraction import SectionCandidateTransport, ground_section_claim
    from qualor.runtime.section_scheduler import ExtractionJob
    from qualor.runtime.sections import SectionIndex, index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    def make_candidate(
        category,
        value,
        quote,
        *,
        text=None,
        qualifiers=(),
        exceptions=(),
        confidence="HIGH",
        state="CANDIDATE",
    ):
        quotes = (quote,) if isinstance(quote, str) else tuple(quote)
        excerpts = (*quotes, *qualifiers, *exceptions)
        category_value = Category(category)
        category_labels = {
            Category.DEADLINE: "SUBMISSION PERIOD",
            Category.ENTRANT_TYPE: "ELIGIBLE ENTRANTS",
            Category.GEOGRAPHY: "GEOGRAPHY",
            Category.LEGAL_ENTITY: "LEGAL ENTITY",
            Category.PROJECT_POLICY: "PROJECT REQUIREMENTS",
            Category.LICENSE: "LICENSE",
            Category.REQUIRED_TECHNOLOGY: "TECHNOLOGY",
            Category.FINANCIAL_SUPPORT: "FINANCIAL SUPPORT",
            Category.REWARD_CONDITIONS: "PRIZE CONDITIONS",
        }
        source_text = text if text is not None else "\n".join(excerpts)
        # Keep original fixture quotations intact while giving the target section
        # a real generic local routing term.  No post-index routing is fabricated.
        source = document(f"{category_labels[category_value]}; {source_text}")
        registry = EvidenceSpanRegistry(secret=b"fixture-section-capabilities-0000")
        index = index_source(source, registry)
        ranges = {}
        for excerpt in excerpts:
            start = source.text.find(excerpt)
            if start < 0:
                raise ValueError("TEST_EXCERPT_NOT_IN_SOURCE")
            ranges[excerpt] = (start, start + len(excerpt))
        # Partition indexed sections at supplied excerpt boundaries. The remaining text
        # stays in the job context, so tests cannot silently discard other conditions.
        sections = []
        for section in index.sections:
            cuts = {section.start_offset, section.end_offset}
            for start, end in ranges.values():
                cuts.update(
                    point
                    for point in (start, end)
                    if section.start_offset < point < section.end_offset
                )
            cuts = sorted(cuts)
            spans = tuple(
                span
                for start, end in zip(cuts, cuts[1:], strict=False)
                for span in registry.register_section(source, start_offset=start, end_offset=end)
            )
            sections.append(
                section.model_copy(update={"span_ids": tuple(s.span_id for s in spans)})
            )
        exact_ids = {}
        for excerpt, (start, end) in ranges.items():
            matches = [
                span_id
                for section in sections
                for span_id in section.span_ids
                if (span := registry.resolve(source.id, span_id)).start_offset == start
                and span.end_offset == end
                and span.exact_text == excerpt
            ]
            if len(matches) != 1:
                raise ValueError("TEST_EXCERPT_MUST_FIT_ONE_EXACT_SPAN")
            exact_ids[excerpt] = matches[0]
        target = next(s for s in sections if exact_ids[quotes[0]] in s.span_ids)
        contexts = tuple(
            section.section_id for section in sections if section.section_id != target.section_id
        )
        target = target.model_copy(update={"context_section_ids": contexts})
        index = SectionIndex(
            source_id=index.source_id,
            source_revision=index.source_revision,
            indexer_version=index.indexer_version,
            sections=tuple(target if s.section_id == target.section_id else s for s in sections),
        )
        plan = build_acquisition_plan(index)
        item = next(
            item
            for item in plan.items
            if item.section_id == target.section_id and category_value in item.categories
        )
        context_sections = tuple(
            section for section in index.sections if section.section_id in contexts
        )
        job = ExtractionJob(
            job_id="extraction_job_" + "f" * 32,
            source_id=source.id,
            source_revision=index.source_revision,
            section_id=target.section_id,
            categories=(Category(category),),
            span_ids=tuple(sid for s in (target, *context_sections) for sid in s.span_ids),
            context_section_ids=contexts,
            authority_revision=0,
            plan_id=plan.plan_id,
            plan_item_id=item.item_id,
            tier=item.tier,
        )

        def ids(values):
            return tuple(exact_ids[value] for value in sorted(values, key=lambda x: ranges[x][0]))

        candidate = SectionCandidateTransport(
            category=category,
            proposed_value=value,
            source_id=source.id,
            section_id=target.section_id,
            span_ids=ids(quotes),
            qualifier_span_ids=ids(qualifiers),
            exception_span_ids=ids(exceptions),
            confidence_class=confidence,
            state=state,
        )
        return ground_section_claim(
            candidate, source=source, index=index, job=job, registry=registry
        )

    return make_candidate
