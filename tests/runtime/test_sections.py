import hashlib
import importlib
import inspect

import pytest

from qualor.domain.enums import Category
from qualor.runtime.sections import index_source
from qualor.runtime.spans import EvidenceSpanRegistry


def _index(document, text: str):
    return index_source(document(text), EvidenceSpanRegistry(secret=b"r" * 32))


def test_sibling_body_category_does_not_smear_across_bounded_children(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "Rules\n"
        + ("General explanatory material. " * 50)
        + "\nAn MIT license is required.\n"
        + ("Operational background. " * 50)
        + "\nProjects must use Widget SDK."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"r" * 32))
    license_child = next(
        section
        for section in index.sections
        if "MIT license" in source.text[section.start_offset : section.end_offset]
    )
    technology_child = next(
        section
        for section in index.sections
        if "Widget SDK" in source.text[section.start_offset : section.end_offset]
    )

    assert Category.LICENSE in license_child.routing.body_categories
    assert Category.REQUIRED_TECHNOLOGY not in license_child.routing.body_categories
    assert Category.REQUIRED_TECHNOLOGY in technology_child.routing.body_categories
    assert Category.LICENSE not in technology_child.routing.body_categories


def test_logical_heading_routes_every_child_but_is_not_child_zero_body(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("License\n" + ("General details. " * 120))
    index = index_source(source, EvidenceSpanRegistry(secret=b"h" * 32))

    assert len(index.sections) > 1
    assert all(Category.LICENSE in s.routing.heading_categories for s in index.sections)
    assert Category.LICENSE not in index.sections[0].routing.body_categories
    assert all(s.candidate_categories == (Category.LICENSE,) for s in index.sections)


@pytest.mark.parametrize(
    ("text", "marker", "category"),
    [
        ("Participants must be eligible.", "OBLIGATION", Category.ENTRANT_TYPE),
        ("Residents may not enter.", "PROHIBITION", Category.GEOGRAPHY),
        ("Only incorporated companies qualify.", "LIMITATION", Category.LEGAL_ENTITY),
        (
            "Projects must use an API or SDK.",
            "TECHNOLOGY_OR_LICENSE",
            Category.REQUIRED_TECHNOLOGY,
        ),
        (
            "Copyright license is required.",
            "TECHNOLOGY_OR_LICENSE",
            Category.LICENSE,
        ),
        (
            "Funding support is prohibited.",
            "FINANCIAL_OR_REWARD",
            Category.FINANCIAL_SUPPORT,
        ),
        (
            "Award winners are subject to verification.",
            "FINANCIAL_OR_REWARD",
            Category.REWARD_CONDITIONS,
        ),
        ("Submit before the deadline.", "SUBMISSION_OR_TIME", Category.DEADLINE),
        (
            "Judging criteria use points and tie rules.",
            "EVALUATION_OR_SELECTION",
            Category.REWARD_CONDITIONS,
        ),
    ],
)
def test_rule_like_detector_is_generic_and_category_bounded(text, marker, category):
    from qualor.runtime.sections import RuleLikeMarker, detect_rule_like_routing

    routed = detect_rule_like_routing(heading_text=None, body_text=text)

    assert routed.rule_like
    assert RuleLikeMarker(marker) in routed.marker_codes
    assert category in routed.category_hints


def test_rule_like_without_category_hint_remains_unclassified():
    from qualor.runtime.sections import detect_rule_like_routing

    routed = detect_rule_like_routing(
        heading_text=None,
        body_text="Unless otherwise specified, this condition applies.",
    )

    assert routed.rule_like
    assert routed.category_hints == ()


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Widget SDK documentation is available.", Category.REQUIRED_TECHNOLOGY),
        ("Eligible teams participate in the event.", Category.ENTRANT_TYPE),
        ("Prize judging criteria are described below.", Category.REWARD_CONDITIONS),
    ],
)
def test_broad_rule_like_discovery_is_not_a_local_mandatory_signal(
    document, text, category
):
    from qualor.runtime.sections import SectionRoutingReason

    section = _index(document, text).sections[0]

    assert section.routing.rule_like
    assert category in section.routing.body_categories
    assert category in section.routing.rule_like_category_hints
    assert SectionRoutingReason.RULE_LIKE_MARKER not in section.routing.reason_codes


@pytest.mark.parametrize(
    "text",
    [
        "Projects must use Widget SDK.",
        "Applicants may not be incorporated companies.",
        "Only residents of Spain may enter.",
        "Technology\n- Widget SDK integration details.",
        "License: MIT.",
    ],
)
def test_exact_local_mandatory_predicates_are_recorded(document, text):
    from qualor.runtime.sections import SectionRoutingReason

    section = _index(document, text).sections[-1]

    assert section.routing.body_categories
    assert section.routing.rule_like
    assert SectionRoutingReason.RULE_LIKE_MARKER in section.routing.reason_codes


def test_structural_rule_item_and_definition_entry_are_recorded(document):
    from qualor.runtime.sections import (
        RuleLikeMarker,
        SectionRoutingReason,
        detect_rule_like_routing,
        index_source,
    )
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("License\n- License: MIT is required.\n")
    section = index_source(source, EvidenceSpanRegistry(secret=b"s" * 32)).sections[0]

    assert RuleLikeMarker.STRUCTURAL_RULE_ITEM in detect_rule_like_routing(
        heading_text="License", body_text="- License: MIT is required."
    ).marker_codes
    assert Category.LICENSE in section.routing.body_categories
    assert SectionRoutingReason.RULE_LIKE_MARKER in section.routing.reason_codes


def test_routing_source_has_no_archive_or_contest_specific_branches():
    source = inspect.getsource(
        importlib.import_module("qualor.runtime.sections")
    ).casefold()
    forbidden = (
        "devpost",
        "agents for humans",
        "official-rules.raw",
        "e3f7640c",
        "agentsforhumans",
        "aws.amazon.com",
    )

    assert not any(value in source for value in forbidden)


def test_candidate_categories_must_equal_local_body_heading_union(document):
    from qualor.runtime.sections import SourceSection, index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    section = index_source(
        document("License\nGeneral details."),
        EvidenceSpanRegistry(secret=b"v" * 32),
    ).sections[0]
    payload = section.model_dump()
    payload["candidate_categories"] = [Category.DEADLINE]

    with pytest.raises(ValueError, match="CANDIDATE_CATEGORY_ROUTING_MISMATCH"):
        SourceSection.model_validate(payload)


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


def test_numbered_child_inherits_direct_parent_context(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\n"
        "These requirements apply only to teams.\n"
        "1.1 License\n"
        "An MIT license is required."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    parent = next(
        section for section in index.sections if section.heading == "1. Project requirements"
    )
    child = next(section for section in index.sections if section.heading == "1.1 License")

    assert child.context_section_ids == (parent.section_id,)
    assert child.context_complete
    assert child.parent_id is None


def test_numbered_child_inherits_each_multilevel_ancestor_nearest_first(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "2. Project requirements\nRequirements apply to submitted projects.\n"
        "2.4 License\nProjects must use an approved license.\n"
        "2.4.3 Technology\nProjects must use Widget SDK.\n"
        "2.4.3.1 Financial support\nCredits are available."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    by_heading = {section.heading: section for section in index.sections if section.heading}
    child = by_heading["2.4.3.1 Financial support"]

    assert child.context_section_ids == (
        by_heading["2.4.3 Technology"].section_id,
        by_heading["2.4 License"].section_id,
        by_heading["2. Project requirements"].section_id,
    )
    assert child.context_complete


def test_numbered_sibling_is_not_inherited_as_ancestry(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\nRequirements apply to projects.\n"
        "1.1 License\nProjects must use MIT.\n"
        "1.2 Technology\nProjects must use Widget SDK."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    by_heading = {section.heading: section for section in index.sections if section.heading}
    sibling = by_heading["1.1 License"]
    child = by_heading["1.2 Technology"]

    assert child.context_section_ids == (by_heading["1. Project requirements"].section_id,)
    assert sibling.section_id not in child.context_section_ids
    assert child.context_complete


def test_numbered_child_with_missing_parent_is_incomplete(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("1.1 License\nProjects must use MIT.")
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    child = index.sections[0]

    assert child.context_section_ids == ()
    assert not child.context_complete


def test_numbered_child_with_ambiguous_ancestor_keeps_all_candidates(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\nRequirements apply to projects.\n"
        "1. Additional requirements\nAdditional requirements apply.\n"
        "1.1 License\nProjects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    ancestors = tuple(section.section_id for section in index.sections[:2])
    child = index.sections[2]

    assert child.context_section_ids == ancestors
    assert not child.context_complete


@pytest.mark.parametrize(
    ("text", "child_heading"),
    [
        (
            "1.1 License\nProjects must use MIT.\n"
            "1. Project requirements\nRequirements apply to projects.",
            "1.1 License",
        ),
        (
            "1. Project requirements\nRequirements apply to projects.\n"
            "2. Eligibility\nTeams may enter.\n"
            "1.1 License\nProjects must use MIT.",
            "1.1 License",
        ),
    ],
)
def test_structurally_inconsistent_numbered_ancestry_is_incomplete(
    document, text: str, child_heading: str
):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(text)
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    child = next(section for section in index.sections if section.heading == child_heading)

    assert not child.context_complete
    assert all(
        context.start_offset < child.start_offset
        for context in index.sections
        if context.section_id in child.context_section_ids
    )


def test_numbered_ancestry_over_context_bound_is_incomplete(document):
    from qualor.runtime.sections import MAX_CONTEXT_SECTION_IDS, index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\n"
        + ("This qualifier applies only to participating teams. " * 240)
        + "\n1.1 License\nProjects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    child = next(section for section in index.sections if section.heading == "1.1 License")

    assert len(child.context_section_ids) == MAX_CONTEXT_SECTION_IDS
    assert not child.context_complete


def test_numbered_child_inherits_unresolved_parent_context_state(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\n"
        "Subject to the preceding section, these requirements apply to teams.\n"
        "1.1 License\n"
        "Projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    parent, child = index.sections

    assert not parent.context_complete
    assert parent.section_id in child.context_section_ids
    assert not child.context_complete


def test_numbered_parent_qualifier_retains_separate_span_capability(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\n"
        "These requirements apply only to teams.\n"
        "1.1 License\n"
        "An MIT license is required."
    )
    registry = EvidenceSpanRegistry(secret=b"a" * 32)
    index = index_source(source, registry)
    parent, child = index.sections

    assert parent.section_id in child.context_section_ids
    assert parent.span_ids
    assert all(span_id not in child.span_ids for span_id in parent.span_ids)
    parent_quote = " ".join(
        registry.resolve(source.id, span_id).exact_text for span_id in parent.span_ids
    )
    assert "These requirements apply only to teams." in parent_quote


def test_numbered_child_span_remains_an_exact_child_only_quote(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. Project requirements\n"
        "These requirements apply only to teams.\n"
        "1.1 License\n"
        "An MIT license is required."
    )
    registry = EvidenceSpanRegistry(secret=b"a" * 32)
    index = index_source(source, registry)
    child = index.sections[1]
    spans = [registry.resolve(source.id, span_id) for span_id in child.span_ids]

    # Structural capabilities tile the child exactly: in order, inside its range, and
    # separated only by the whitespace that laid the lines out.
    assert [span.exact_text for span in spans] == ["1.1 License", "An MIT license is required."]
    cursor = child.start_offset
    for span in spans:
        assert child.start_offset <= span.start_offset < span.end_offset <= child.end_offset
        assert not source.text[cursor : span.start_offset].strip()
        cursor = span.end_offset
    assert not source.text[cursor : child.end_offset].strip()
    assert all("These requirements apply only to teams." not in s.exact_text for s in spans)


def test_explicit_reference_and_numbered_ancestry_are_both_preserved(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "3. Eligibility\nTeams may enter.\n"
        "1. Project requirements\nRequirements apply to projects.\n"
        "1.1 License\nSubject to section 3, projects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    by_heading = {section.heading: section for section in index.sections if section.heading}
    child = by_heading["1.1 License"]

    assert child.context_section_ids == (
        by_heading["1. Project requirements"].section_id,
        by_heading["3. Eligibility"].section_id,
    )
    assert child.context_complete


def test_nonnumbered_headings_do_not_gain_structural_ancestry(document):
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "Project requirements\nRequirements apply to projects.\nLicense\nProjects must use MIT."
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    parent, child = index.sections

    assert parent.section_id not in child.context_section_ids
    assert child.context_section_ids == ()
    assert child.context_complete


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


def test_unsafe_bounded_boundary_fails_closed_on_both_children(document):
    """A forced cut can sever a qualifier, so neither side may claim complete context."""

    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("x" * 691 + " subject to approval.")
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    before, after = index.sections[0], index.sections[1]

    assert len(index.sections) >= 2
    assert source.text[before.start_offset : before.end_offset].endswith("subject ")
    assert source.text[after.start_offset : after.end_offset].startswith("to approval.")
    assert not before.context_complete
    assert not after.context_complete


@pytest.mark.parametrize(
    "filler",
    [
        "Detail line.\n",
        "An MIT license is required. ",
        "an MIT license is required; ",
    ],
)
def test_semantic_boundaries_keep_bounded_children_complete(document, filler):
    """Paragraph, sentence and semicolon cuts are structural, so they stay resolvable."""

    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document("License\n" + filler * 80)
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))

    assert len(index.sections) >= 2
    assert all(section.context_complete for section in index.sections)


def test_unrelated_same_group_sibling_is_not_governing_context(document):
    """Bounded children share a parent, not every sibling that happened to fit beside them."""

    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "Project requirements\n"
        + ("Alpha background detail.\n" * 30)
        + ("Beta background detail.\n" * 30)
        + ("Gamma background detail.\n" * 30)
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    children = [section for section in index.sections if section.parent_id is not None]
    first, last = children[0], children[-1]

    assert len(children) >= 2
    assert last.parent_id in last.context_section_ids
    assert first.section_id not in last.context_section_ids
    assert last.section_id not in first.context_section_ids


def test_parent_ancestry_reference_and_global_context_are_all_retained(document):
    """Removing sibling smear must not weaken any canonically governing channel."""

    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    source = document(
        "1. General Conditions\n"
        "This section applies to all sections. Entrants must be adults.\n"
        "3. Eligibility\nTeams may enter.\n"
        "2. Project requirements\nRequirements apply to projects.\n"
        "2.1 License\nSubject to section 3, projects must use MIT.\n"
    )
    index = index_source(source, EvidenceSpanRegistry(secret=b"a" * 32))
    by_heading = {section.heading: section for section in index.sections if section.heading}
    child = by_heading["2.1 License"]

    assert by_heading["2. Project requirements"].section_id in child.context_section_ids
    assert by_heading["3. Eligibility"].section_id in child.context_section_ids
    assert by_heading["1. General Conditions"].section_id in child.context_section_ids
    assert child.context_complete
