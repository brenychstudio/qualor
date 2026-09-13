import hashlib

from qualor.domain.enums import Category


def _stable_section_fields(index):
    return [
        section.model_dump(exclude={"span_ids"})
        for section in index.sections
    ]


def test_late_license_section_is_reachable(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    text = (
        "Introduction\n"
        + ("General background.\n" * 700)
        + "\nLicense\nAn MIT license is required."
    )
    source = document(text)
    index = index_source(source, EvidenceSpanRegistry())
    reached = [section for section in index.sections if section.start_offset > 9_000]

    assert reached
    assert any(
        "MIT" in source.text[section.start_offset : section.end_offset]
        for section in reached
    )
    assert not hasattr(index, "eligibility")


def test_section_identity_is_stable_but_span_capabilities_are_run_scoped(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("Eligibility\nIndividuals resident in Spain may enter.")
    first = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    second = index_source(source, EvidenceSpanRegistry(secret=b"b" * 32))

    assert first.source_revision == second.source_revision
    assert _stable_section_fields(first) == _stable_section_fields(second)
    assert [section.span_ids for section in first.sections] != [
        section.span_ids for section in second.sections
    ]


def test_content_revision_invalidates_section_identity(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    text = "License\nAn MIT license is required."
    first = index_source(document(text), EvidenceSpanRegistry(secret=b"a" * 32))
    revised_hash = hashlib.sha256(b"a different raw response").hexdigest()
    revised = index_source(
        document(text, content_hash=revised_hash),
        EvidenceSpanRegistry(secret=b"a" * 32),
    )

    assert first.source_revision != revised.source_revision
    assert [section.section_id for section in first.sections] != [
        section.section_id for section in revised.sections
    ]


def test_sections_cover_exact_source_offsets_in_order(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    text = (
        "Opening paragraph.\n\n"
        "Eligibility\nIndividuals may enter.\n\n"
        "License\nMIT is required.\n"
    )
    source = document(text)
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))

    assert index.sections[0].start_offset == 0
    assert index.sections[-1].end_offset == len(text)
    assert all(
        left.end_offset == right.start_offset
        for left, right in zip(index.sections, index.sections[1:], strict=False)
    )
    for section in index.sections:
        exact = source.text[section.start_offset : section.end_offset]
        assert hashlib.sha256(exact.encode("utf-8")).hexdigest() == section.section_hash
        assert all(
            source.text[span.start_offset : span.end_offset] == span.exact_text
            for span in (
                EvidenceSpanRegistry(secret=b"c" * 32).register_section(
                    source,
                    start_offset=section.start_offset,
                    end_offset=section.end_offset,
                )
            )
        )


def test_oversized_children_preserve_parent_and_referenced_context(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    text = (
        "1. General Conditions\n"
        "This section applies to all sections. Entrants must be adults.\n"
        "2. Eligibility\n"
        + ("Eligible teams provide background details. " * 45)
        + "\n3. License\nSubject to section 1, projects must use the MIT license.\n"
        "4. Technology\nSubject to section 99, projects must use Widget SDK."
    )
    source = document(text)
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    by_heading = {section.heading: section for section in index.sections if section.heading}
    eligibility = by_heading["2. Eligibility"]
    children = [
        section for section in index.sections if section.parent_id == eligibility.section_id
    ]

    assert children
    assert all(eligibility.section_id in child.context_section_ids for child in children)
    assert all(child.context_complete for child in children)
    general = by_heading["1. General Conditions"]
    license_section = by_heading["3. License"]
    assert general.section_id in license_section.context_section_ids
    technology = by_heading["4. Technology"]
    assert not technology.context_complete


def test_unclassified_headingless_content_remains_indexed(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("Ordinary background notes without a classified rule.\n" * 30)
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))

    assert index.sections
    assert index.sections[0].heading is None
    assert all(section.candidate_categories == () for section in index.sections)
    assert index.sections[0].start_offset == 0
    assert index.sections[-1].end_offset == len(source.text)


def test_category_terms_are_routing_hints_only(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "Eligibility\n"
        "Residents and incorporated companies may enter.\n"
        "Project Requirements\n"
        "New work must use Widget SDK and an MIT license.\n"
        "Prizes\nCash rewards require winner verification."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    categories = {
        section.heading: set(section.candidate_categories)
        for section in index.sections
        if section.heading
    }

    assert {
        Category.ENTRANT_TYPE,
        Category.GEOGRAPHY,
        Category.LEGAL_ENTITY,
    } <= categories["Eligibility"]
    assert {
        Category.PROJECT_POLICY,
        Category.LICENSE,
        Category.REQUIRED_TECHNOLOGY,
    } <= categories["Project Requirements"]
    assert Category.REWARD_CONDITIONS in categories["Prizes"]
    assert not hasattr(index, "rules")
    assert not hasattr(index, "eligibility")


def test_unrelated_local_may_is_not_treated_as_global_context(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Schedule\nOrganizers may change the event date.\n"
        "2. Eligibility\nIndividuals are eligible."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    schedule = next(section for section in index.sections if section.heading == "1. Schedule")
    eligibility = next(section for section in index.sections if section.heading == "2. Eligibility")

    assert schedule.section_id not in eligibility.context_section_ids


def test_reference_to_oversized_section_keeps_all_bounded_context(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. General Conditions\n"
        + ("Background detail remains applicable. " * 30)
        + "Entrants must be adults.\n"
        "2. License\nSubject to section 1, projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    license_section = next(
        section for section in index.sections if section.heading == "2. License"
    )
    general_parent = next(
        section for section in index.sections if section.heading == "1. General Conditions"
    )
    general_ids = {
        section.section_id
        for section in index.sections
        if section.section_id == general_parent.section_id
        or section.parent_id == general_parent.section_id
    }

    assert len(general_ids) > 1
    assert general_ids <= set(license_section.context_section_ids)
    assert license_section.context_complete


def test_duplicate_numbered_headings_preserve_all_targets_as_ambiguous(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. General Conditions\nEntrants must be adults.\n"
        "1. Additional Conditions\nEntrants must register first.\n"
        "2. License\nSubject to section 1, projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    first = next(
        section for section in index.sections if section.heading == "1. General Conditions"
    )
    duplicate = next(
        section
        for section in index.sections
        if section.heading == "1. Additional Conditions"
    )
    license_section = next(
        section for section in index.sections if section.heading == "2. License"
    )

    assert {first.section_id, duplicate.section_id} <= set(
        license_section.context_section_ids
    )
    assert not license_section.context_complete


def test_plural_compound_section_reference_preserves_each_target(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Eligibility\nIndividuals may enter.\n"
        "2. Geography\nResidents of Spain may enter.\n"
        "3. License\nSubject to sections 1 and 2, projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    targets = {
        section.section_id
        for section in index.sections
        if section.heading in {"1. Eligibility", "2. Geography"}
    }
    license_section = next(
        section for section in index.sections if section.heading == "3. License"
    )

    assert targets <= set(license_section.context_section_ids)
    assert license_section.context_complete


def test_unsupported_section_reference_remains_incomplete(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Eligibility\nIndividuals may enter.\n"
        "2. License\nSubject to the preceding section, projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    license_section = next(
        section for section in index.sections if section.heading == "2. License"
    )

    assert not license_section.context_complete


def test_unparsed_compound_section_reference_remains_incomplete(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Eligibility\nIndividuals may enter.\n"
        "2. Geography\nResidents of Spain may enter.\n"
        "3. License\nSubject to sections 1 & 2, projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    license_section = next(
        section for section in index.sections if section.heading == "3. License"
    )

    assert not license_section.context_complete


def test_submit_does_not_route_to_license_from_mit_substring(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("Submission Deadline\nSubmit applications by September 30.")
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    section = index.sections[0]

    assert Category.DEADLINE in section.candidate_categories
    assert Category.LICENSE not in section.candidate_categories


def test_canonical_source_text_preserves_existing_parser_behavior(monkeypatch):
    from qualor.runtime import sources

    html, truncated = sources.canonical_source_text(
        b"<h1>Rules</h1><script>ignore</script><p>Exact quote.</p>",
        "text/html",
    )
    json_text, json_truncated = sources.canonical_source_text(
        b'{"name":"QUALOR"}', "application/json"
    )
    monkeypatch.setattr(sources, "MAX_SOURCE_CHARACTERS", 4)
    clipped, clipped_flag = sources.canonical_source_text(b"abcdef", "text/plain")

    assert html == "Rules\nExact quote."
    assert not truncated
    assert json_text == '{"name": "QUALOR"}'
    assert not json_truncated
    assert clipped == "abcd"
    assert clipped_flag
