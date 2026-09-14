"""Independent source-to-expression cases; adapters never decide eligibility."""

from datetime import UTC, datetime

import pytest

from qualor.domain.enums import Category, Operator, SubjectReference


@pytest.fixture(autouse=True)
def deterministic_timezone_database(monkeypatch):
    """Two owned 2027 TZif tables exercise real ZoneInfo fold/gap behavior offline."""
    import io
    import struct
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    def zone(key):
        definitions = {
            "America/Los_Angeles": (
                (datetime(2027, 3, 14, 10, tzinfo=UTC), datetime(2027, 11, 7, 9, tzinfo=UTC)),
                (-28800, -25200),
                b"PST\0PDT\0",
                4,
            ),
            "Europe/Madrid": (
                (datetime(2027, 3, 28, 1, tzinfo=UTC), datetime(2027, 10, 31, 1, tzinfo=UTC)),
                (3600, 7200),
                b"CET\0CEST\0",
                4,
            ),
        }
        if key not in definitions:
            raise ZoneInfoNotFoundError(key)
        dates, offsets, labels, dst_label = definitions[key]
        header = b"TZif\0" + b"\0" * 15 + struct.pack(">6l", 0, 0, 0, 2, 2, len(labels))
        transitions = struct.pack(">2l", *(int(date.timestamp()) for date in dates)) + b"\x01\x00"
        types = struct.pack(">lbb", offsets[0], 0, 0) + struct.pack(
            ">lbb", offsets[1], 1, dst_label
        )
        return ZoneInfo.from_file(io.BytesIO(header + transitions + types + labels), key=key)

    monkeypatch.setattr("qualor.runtime.adapters.deadline.ZoneInfo", zone)


def compile_candidate(candidate):
    from qualor.runtime.adapters import adapt_candidate

    return adapt_candidate(candidate, evaluated_at=candidate.source.retrieved_at)


def nodes(rule):
    yield rule
    for child in rule.children:
        yield from nodes(child)


@pytest.mark.parametrize(
    "category,value,quote,operator,subject,operands",
    [
        (
            "DEADLINE",
            ("2027-02-01T10:00:00Z", "2027-03-01T11:00:00+01:00"),
            "Submissions are accepted from 2027-02-01T10:00:00Z to 2027-03-01T11:00:00+01:00.",
            "DATE_BETWEEN",
            "EVALUATED_AT",
            (datetime(2027, 2, 1, 10, tzinfo=UTC), datetime(2027, 3, 1, 10, tzinfo=UTC)),
        ),
        ("ENTRANT_TYPE", "INDIVIDUAL", "Open to individuals.", "IN", "LEGAL_FORM", ("INDIVIDUAL",)),
        (
            "LEGAL_ENTITY",
            "INCORPORATED_COMPANY",
            "Applicants must be incorporated companies.",
            "IN",
            "LEGAL_FORM",
            ("INCORPORATED_COMPANY",),
        ),
        (
            "PROJECT_POLICY",
            "NEW_ONLY",
            "Projects must be newly created.",
            "BOOL_IS",
            "NEW_PROJECT",
            (True,),
        ),
        (
            "LICENSE",
            "MIT",
            "Projects must intend to use the MIT license.",
            "IN",
            "LICENSE",
            ("MIT",),
        ),
        (
            "REQUIRED_TECHNOLOGY",
            "Widget SDK",
            "Build an agent using Widget SDK.",
            "IN",
            "REQUIRED_TECHNOLOGY",
            ("Widget SDK",),
        ),
        (
            "FINANCIAL_SUPPORT",
            "REQUIRED",
            "Projects must have sponsor support.",
            "BOOL_IS",
            "FINANCIAL_SUPPORT",
            (True,),
        ),
        (
            "REWARD_CONDITIONS",
            "REQUIRED",
            "Projects must meet reward conditions.",
            "BOOL_IS",
            "REWARD_CONDITIONS",
            (True,),
        ),
    ],
    ids=lambda value: value if isinstance(value, str) and value in Category.__members__ else None,
)
def test_family_source_to_typed_expression(
    grounded_candidate, category, value, quote, operator, subject, operands
):
    candidate = grounded_candidate(category, value, quote)
    result = compile_candidate(candidate)
    assert result.normalization_status == "SUPPORTED"
    assert len(result.rules) == 1
    rule = result.rules[0]
    assert rule.operator == Operator[operator]
    assert rule.subject_reference == SubjectReference[subject]
    assert tuple(item.value for item in rule.operands) == operands
    assert rule.supported
    assert rule.clause_context == candidate.context
    assert result.evidence[0].supporting_excerpt == quote
    assert result.evidence[0].clause_context == candidate.context
    assert rule.evidence_ids == (result.evidence[0].id,)
    assert result.evidence[0].extraction_state == "REVIEWED"
    assert result.evidence[0].provenance == "DOCUMENTED"


@pytest.mark.parametrize("category", list(Category))
def test_high_confidence_unknown_never_becomes_authority(grounded_candidate, category):
    candidate = grounded_candidate(
        category, None, "Official terms need clarification.", state="UNKNOWN"
    )
    result = compile_candidate(candidate)
    assert result.normalization_status == "UNKNOWN"
    assert result.normalized_value is None
    assert result.rules and all(not rule.supported for rule in result.rules)
    assert all(rule.subject_reference is None for rule in result.rules)
    assert result.reason_codes


@pytest.mark.parametrize(
    "value,quote,operator,expected",
    [
        (
            ("Copper SDK", "Silver API"),
            "Projects must use Copper SDK and Silver API.",
            "AND",
            (("Copper SDK",), ("Silver API",)),
        ),
        (
            ("Copper SDK", "Silver API"),
            "Projects must use Copper SDK or Silver API.",
            "IN",
            ("Copper SDK", "Silver API"),
        ),
        (
            "Research and Development SDK",
            'Build a tool with "Research and Development SDK".',
            "IN",
            ("Research and Development SDK",),
        ),
    ],
)
def test_technology_boolean_scope(grounded_candidate, value, quote, operator, expected):
    result = compile_candidate(grounded_candidate("REQUIRED_TECHNOLOGY", value, quote))
    root = result.rules[0]
    assert result.normalization_status == "SUPPORTED"
    assert root.operator == operator
    actual = (
        tuple(tuple(v.value for v in child.operands) for child in root.children)
        if root.children
        else tuple(v.value for v in root.operands)
    )
    assert actual == expected


@pytest.mark.parametrize(
    "quote",
    [
        "Projects may optionally use Copper SDK.",
        "Using Copper SDK is optional for deployment.",
        "Using Copper SDK earns bonus points.",
    ],
)
def test_technology_optional_is_not_mandatory(grounded_candidate, quote):
    result = compile_candidate(grounded_candidate("REQUIRED_TECHNOLOGY", "Copper SDK", quote))
    assert result.rules == ()
    assert result.reason_codes == ("OPTIONAL_TECHNOLOGY",)


@pytest.mark.parametrize(
    "quote",
    [
        "Projects must use Copper SDK only if entering the advanced track.",
        "Projects must use Copper SDK, except invited exhibitors.",
        "Projects must not use Copper SDK.",
        "Projects must use Copper SDK and obtain written approval.",
    ],
)
def test_technology_unrepresented_tail_never_disappears(grounded_candidate, quote):
    candidate = grounded_candidate(
        "REQUIRED_TECHNOLOGY",
        "Copper SDK",
        quote,
        qualifiers=(quote,),
        exceptions=(quote,) if "except" in quote else (),
    )
    result = compile_candidate(candidate)
    assert any(not node.supported for rule in result.rules for node in nodes(rule))
    assert result.reason_codes
    assert result.evidence[0].supporting_excerpt == quote


def test_technology_candidate_cannot_change_required_value(grounded_candidate):
    result = compile_candidate(
        grounded_candidate("REQUIRED_TECHNOLOGY", "Other SDK", "Build a tool using Copper SDK.")
    )
    assert result.normalization_status == "UNSUPPORTED"
    assert all(not rule.supported for rule in result.rules)


@pytest.mark.parametrize(
    "source,value,want",
    [
        ("2027-07-06T17:00:00-07:00", "2027-07-07T00:00:00Z", "2027-07-07T00:00:00+00:00"),
        (
            "Tuesday, July 6, 2027 at 5:00 PM Pacific Time",
            "2027-07-07T00:00:00Z",
            "2027-07-07T00:00:00+00:00",
        ),
        ("July 6, 2027 at 17:00 UTC+02:00", "2027-07-06T15:00:00Z", "2027-07-06T15:00:00+00:00"),
        (
            "July 6, 2027 at 17:00 Europe/Madrid",
            "2027-07-06T15:00:00Z",
            "2027-07-06T15:00:00+00:00",
        ),
    ],
)
def test_deadline_lone_close_never_invents_opening(grounded_candidate, source, value, want):
    result = compile_candidate(grounded_candidate("DEADLINE", value, f"Deadline: {source}."))
    assert result.normalization_status == "SUPPORTED"
    assert result.normalized_value == want
    assert all(not rule.supported and rule.subject_reference is None for rule in result.rules)
    assert all(rule.operator != Operator.DATE_BETWEEN for rule in result.rules)
    assert "DEADLINE_OPENING_BOUND_ABSENT" in result.reason_codes


@pytest.mark.parametrize(
    "source",
    [
        "07/06/2027 17:00 UTC",
        "July 6 at 17:00 UTC",
        "July 6, 2027 at 17:00",
        "July 6, 2027 at 17:00 CST",
        "Monday, July 6, 2027 at 17:00 UTC",
        "November 7, 2027 at 01:30 America/Los_Angeles",
        "March 14, 2027 at 02:30 America/Los_Angeles",
        "2027-07-06T17:00:00-00:00",
        "July 6, 2027 at 17:00 UTC+25:00",
        "2027-07-06",
        "2027-07-06T17:00:00Z or later",
    ],
)
def test_deadline_ambiguous_or_unsupported_date_is_not_authority(grounded_candidate, source):
    result = compile_candidate(grounded_candidate("DEADLINE", source, f"Deadline: {source}."))
    assert result.normalization_status in {"AMBIGUOUS", "UNSUPPORTED", "UNKNOWN"}
    assert result.normalized_value is None
    assert all(not rule.supported for rule in result.rules)
    assert result.reason_codes


def test_deadline_interval_resolves_each_zone_independently(grounded_candidate):
    quote = (
        "Submissions are accepted from July 6, 2027 at 17:00 UTC "
        "to July 8, 2027 at 17:00 Pacific Time."
    )
    result = compile_candidate(
        grounded_candidate("DEADLINE", ("2027-07-06T17:00:00Z", "2027-07-09T00:00:00Z"), quote)
    )
    assert result.normalization_status == "SUPPORTED"
    assert tuple(v.value for v in result.rules[0].operands) == (
        datetime(2027, 7, 6, 17, tzinfo=UTC),
        datetime(2027, 7, 9, tzinfo=UTC),
    )


def test_deadline_exception_blocks_authority_and_keeps_quote(grounded_candidate):
    quote = "Deadline: 2027-07-06T17:00:00Z."
    exception = "Except invited teams, who submit a week later."
    result = compile_candidate(
        grounded_candidate("DEADLINE", "2027-07-06T17:00:00Z", quote, exceptions=(exception,))
    )
    assert result.normalization_status == "UNKNOWN"
    assert result.normalized_value is None
    assert tuple(e.supporting_excerpt for e in result.evidence) == (quote, exception)


@pytest.mark.parametrize(
    "quote,value,operator,want",
    [
        (
            "Open to individuals or sole traders.",
            ("INDIVIDUAL", "SOLE_TRADER"),
            "OR",
            ("INDIVIDUAL", "SOLE_TRADER"),
        ),
        ("Open to teams of 2 to 5 members.", "TEAM", "BETWEEN", (2, 5)),
        ("Teams must have at most 4 members.", "TEAM", "LTE", (4,)),
        ("Teams must have at least 2 members.", "TEAM", "GTE", (2,)),
    ],
)
def test_entrant_alternatives_and_numeric_team_scope(
    grounded_candidate, quote, value, operator, want
):
    result = compile_candidate(grounded_candidate("ENTRANT_TYPE", value, quote))
    root = result.rules[0]
    assert result.normalization_status == "SUPPORTED"
    assert root.operator == operator
    operands = (
        tuple(v.value for child in root.children for v in child.operands)
        if root.children
        else tuple(v.value for v in root.operands)
    )
    assert operands == want


def test_entrant_age_and_representative_stay_in_their_alternative(grounded_candidate):
    quote = (
        "Open to individuals aged at least 18 or teams of 2 to 5 members "
        "with an authorized representative."
    )
    result = compile_candidate(grounded_candidate("ENTRANT_TYPE", ("INDIVIDUAL", "TEAM"), quote))
    root = result.rules[0]
    assert root.operator == "OR" and len(root.children) == 2
    for branch in root.children:
        assert branch.operator == "AND"
        assert branch.children[0].supported
        assert not branch.children[1].supported
        assert branch.children[1].subject_reference is None
    assert root.children[0].children[0].subject_reference == SubjectReference.LEGAL_FORM
    assert root.children[1].children[0].subject_reference == SubjectReference.TEAM_SIZE
    assert result.conditional


@pytest.mark.parametrize(
    "quote", ["Teams may enter.", "Open to individuals unless affiliated with the organizer."]
)
def test_entrant_unrepresented_scope_is_unresolved(grounded_candidate, quote):
    value = "TEAM" if quote.startswith("Teams") else "INDIVIDUAL"
    result = compile_candidate(
        grounded_candidate(
            "ENTRANT_TYPE", value, quote, exceptions=(quote,) if "unless" in quote else ()
        )
    )
    assert any(not n.supported for rule in result.rules for n in nodes(rule))
    if "unless" in quote:
        assert not result.rules[0].supported


def test_entrant_negative_permission_is_not_positive(grounded_candidate):
    quote = "Individuals may not enter."
    result = compile_candidate(
        grounded_candidate("ENTRANT_TYPE", "INDIVIDUAL", quote, qualifiers=(quote,))
    )
    assert not result.rules[0].supported or result.rules[0].operator == "NOT_IN"


def test_legal_entity_alternatives_retain_unrepresented_classes(grounded_candidate):
    result = compile_candidate(
        grounded_candidate(
            "LEGAL_ENTITY",
            ("INCORPORATED_COMPANY", "UNIVERSITY"),
            "Open to incorporated companies or universities.",
        )
    )
    root = result.rules[0]
    assert root.operator == "OR"
    assert root.children[0].operands[0].value == "INCORPORATED_COMPANY"
    assert root.children[0].supported
    assert not root.children[1].supported
    assert root.children[1].subject_reference is None


def test_legal_entity_complete_incorporation_bounds(grounded_candidate):
    from datetime import date

    quote = (
        "Applicants must be incorporated companies incorporated between 2020-01-01 and 2025-12-31."
    )
    result = compile_candidate(grounded_candidate("LEGAL_ENTITY", "INCORPORATED_COMPANY", quote))
    root = result.rules[0]
    assert root.operator == "AND"
    bound = root.children[1]
    assert bound.operator == "DATE_BETWEEN"
    assert bound.subject_reference == SubjectReference.INCORPORATION_DATE
    assert tuple(v.value for v in bound.operands) == (date(2020, 1, 1), date(2025, 12, 31))


@pytest.mark.parametrize(
    "tail",
    [
        "incorporated before 2025-12-31",
        "incorporated within the last seven years",
        "with an authorized representative",
        "except subsidiaries",
    ],
)
def test_legal_entity_unrepresented_date_or_representation_is_retained(grounded_candidate, tail):
    quote = f"Applicants must be incorporated companies {tail}."
    result = compile_candidate(
        grounded_candidate(
            "LEGAL_ENTITY",
            "INCORPORATED_COMPANY",
            quote,
            exceptions=(quote,) if "except" in tail else (),
        )
    )
    assert any(not n.supported for r in result.rules for n in nodes(r))
    assert result.reason_codes
    assert not any(
        n.operator == "DATE_BETWEEN" and n.supported for r in result.rules for n in nodes(r)
    )


def test_legal_entity_proposal_cannot_infer_company(grounded_candidate):
    result = compile_candidate(
        grounded_candidate("LEGAL_ENTITY", "INCORPORATED_COMPANY", "Open to independent studios.")
    )
    assert not any(
        n.supported and n.subject_reference == SubjectReference.LEGAL_FORM
        for r in result.rules
        for n in nodes(r)
    )


@pytest.mark.parametrize(
    "quote,value,operator,subject",
    [
        (
            "Entrants must not reside in Canada or Mexico.",
            ("Canada", "Mexico"),
            "NOT_IN",
            "RESIDENCE",
        ),
        (
            "Entrants must be citizens of Canada or Mexico.",
            ("Canada", "Mexico"),
            "IN",
            "CITIZENSHIP",
        ),
        ("Residents of Canada are excluded.", "Canada", "NOT_IN", "RESIDENCE"),
    ],
)
def test_geography_retains_actor_and_polarity_without_executable_subject(
    grounded_candidate, quote, value, operator, subject
):
    result = compile_candidate(
        grounded_candidate("GEOGRAPHY", value, quote, text=quote, qualifiers=(quote,))
    )
    assert result.normalization_status == "UNKNOWN"
    assert result.rules[0].operator == operator
    assert result.rules[0].subject_reference is None
    assert not result.rules[0].supported
    assert result.evidence[0].supporting_excerpt == quote
    assert tuple(v.value for v in result.rules[0].operands) == (
        value if isinstance(value, tuple) else (value,)
    )


def test_geography_open_legal_catchall_is_a_required_unresolved_conjunct(grounded_candidate):
    quote = (
        "Entrants must not reside in Canada or any jurisdiction "
        "where participation is prohibited by law."
    )
    result = compile_candidate(
        grounded_candidate("GEOGRAPHY", "Canada", quote, text=quote, qualifiers=(quote,))
    )
    root = result.rules[0]
    assert not root.supported and root.operator == "AND"
    assert root.children[0].operator == "NOT_IN"
    assert root.children[0].operands[0].value == "Canada"
    assert not root.children[1].supported and root.children[1].subject_reference is None
    assert "GEOGRAPHY_EXTERNAL_COMPLIANCE_REQUIRED" in result.reason_codes
    assert result.conditional


@pytest.mark.parametrize(
    "quote,value",
    [
        ("Entrants must reside in the province of Quebec.", "the province of Quebec"),
        ("Entrants must reside in Quebec, Canada.", "Quebec, Canada"),
        ("Open to Canada.", "Canada"),
        ("Entrants must reside in Canada.", "CA"),
        ("Entrants must reside in Canada except sponsor employees.", "Canada"),
    ],
)
def test_geography_no_country_mapping_or_applicability_guess(grounded_candidate, quote, value):
    result = compile_candidate(
        grounded_candidate(
            "GEOGRAPHY", value, quote, exceptions=(quote,) if "except" in quote else ()
        )
    )
    assert not result.rules[0].supported
    assert result.reason_codes
    assert result.evidence[0].supporting_excerpt == quote


def test_geography_condition_retains_bounded_exact_internal_context(grounded_candidate):
    from pydantic import ValidationError

    from qualor.runtime.adapters.geography import GeographyCondition

    candidate = grounded_candidate("GEOGRAPHY", "Canada", "Entrants must reside in Canada.")
    condition = GeographyCondition(
        explicitly_allowed=("Canada",),
        explicitly_excluded=(),
        open_ended_legal_restriction=True,
        requires_external_compliance_check=True,
        qualifiers=(" exact ",),
        exceptions=(),
        provenance=candidate.context,
    )
    assert condition.qualifiers == (" exact ",)
    assert condition.provenance == candidate.context
    with pytest.raises(ValidationError):
        GeographyCondition(**(condition.model_dump() | {"explicitly_allowed": ("x",) * 13}))


@pytest.mark.parametrize(
    "quote,value,want",
    [
        ("Projects must be new.", "NEW_ONLY", True),
        ("Projects must not be new.", "EXISTING_ONLY", False),
    ],
)
def test_project_policy_explicit_boolean_polarity(grounded_candidate, quote, value, want):
    result = compile_candidate(
        grounded_candidate("PROJECT_POLICY", value, quote, text=quote, qualifiers=(quote,))
    )
    assert result.normalization_status == "SUPPORTED"
    assert result.rules[0].operands[0].value is want


@pytest.mark.parametrize(
    "tail",
    [
        "during the submission period",
        "and disclose all reused components",
        "without reusing prior work",
    ],
)
def test_project_policy_temporal_reuse_disclosure_remain_conjuncts(grounded_candidate, tail):
    quote = f"Projects must be newly created {tail}."
    result = compile_candidate(
        grounded_candidate("PROJECT_POLICY", "NEW_ONLY", quote, text=quote, qualifiers=(quote,))
    )
    root = result.rules[0]
    assert root.operator == "AND" and root.supported
    assert root.children[0].subject_reference == SubjectReference.NEW_PROJECT
    assert root.children[0].operands[0].value is True
    assert not root.children[1].supported and root.children[1].subject_reference is None
    assert result.conditional


@pytest.mark.parametrize(
    "quote",
    [
        "Existing projects may enter.",
        "Projects must be new or existing.",
        "Projects must be new except demonstrations.",
    ],
)
def test_project_policy_permission_or_exception_is_not_newness_fact(grounded_candidate, quote):
    result = compile_candidate(
        grounded_candidate(
            "PROJECT_POLICY",
            "NEW_ONLY",
            quote,
            text=quote,
            exceptions=(quote,) if "except" in quote else (),
        )
    )
    assert not result.rules[0].supported


def test_license_intent_alternatives_use_or(grounded_candidate):
    result = compile_candidate(
        grounded_candidate(
            "LICENSE",
            ("MIT", "Apache-2.0"),
            "Projects must intend to use the MIT or Apache-2.0 license.",
        )
    )
    root = result.rules[0]
    assert result.normalization_status == "SUPPORTED"
    assert root.operator == "OR"
    assert tuple(child.operands[0].value for child in root.children) == ("MIT", "Apache-2.0")
    assert all(child.subject_reference == SubjectReference.LICENSE for child in root.children)


@pytest.mark.parametrize(
    "quote",
    [
        "Projects must be licensed under MIT or Apache-2.0.",
        "The public repository must use the MIT or Apache-2.0 license.",
    ],
)
def test_license_actual_publication_is_not_intent_compliance(grounded_candidate, quote):
    result = compile_candidate(grounded_candidate("LICENSE", ("MIT", "Apache-2.0"), quote))
    all_nodes = [n for rule in result.rules for n in nodes(rule)]
    assert set(v.value for n in all_nodes for v in n.operands) == {"MIT", "Apache-2.0"}
    assert not any(n.subject_reference == SubjectReference.LICENSE for n in all_nodes)
    assert any(not n.supported for n in all_nodes)
    assert "LICENSE_ACTUAL_COMPLIANCE_UNREPRESENTED" in result.reason_codes
    assert result.normalized_value == ("MIT", "Apache-2.0")


@pytest.mark.parametrize(
    "quote",
    [
        "Projects must not use the MIT license.",
        "Projects must intend to use the MIT license unless awarded a special exemption.",
        "Projects must intend to use the MIT license and publish the repository.",
    ],
)
def test_license_negative_and_unrepresented_conditions_never_vanish(grounded_candidate, quote):
    result = compile_candidate(
        grounded_candidate(
            "LICENSE",
            "MIT",
            quote,
            text=quote,
            qualifiers=(quote,),
            exceptions=(quote,) if "unless" in quote else (),
        )
    )
    assert any(not n.supported for rule in result.rules for n in nodes(rule))
    assert result.reason_codes


def test_license_cannot_drop_a_source_alternative(grounded_candidate):
    result = compile_candidate(
        grounded_candidate(
            "LICENSE", "MIT", "Projects must intend to use the MIT or Apache-2.0 license."
        )
    )
    assert not result.rules[0].supported


def test_financial_support_exact_prohibition(grounded_candidate):
    quote = "Projects must not have sponsor support."
    result = compile_candidate(
        grounded_candidate(
            "FINANCIAL_SUPPORT", "PROHIBITED", quote, text=quote, qualifiers=(quote,)
        )
    )
    assert result.normalization_status == "SUPPORTED"
    assert result.rules[0].subject_reference == SubjectReference.FINANCIAL_SUPPORT
    assert result.rules[0].operands[0].value is False


@pytest.mark.parametrize(
    "quote",
    [
        "Entrants must not have sponsor support.",
        "Projects must not have sponsor support during 2025.",
        "Projects must not have preferential support from sponsor employees.",
        "Projects must not have sponsor support except publicly available credits.",
        "Projects may receive sponsor support or community donations.",
    ],
)
def test_financial_support_actor_time_preferences_exception_not_broad_fact(
    grounded_candidate, quote
):
    result = compile_candidate(
        grounded_candidate(
            "FINANCIAL_SUPPORT",
            "PROHIBITED",
            quote,
            text=quote,
            qualifiers=(quote,),
            exceptions=(quote,) if "except" in quote else (),
        )
    )
    assert not result.rules[0].supported
    assert result.reason_codes


def test_financial_support_separate_disclosure_remains_required(grounded_candidate):
    quote = "Projects must have sponsor support and disclose all funding."
    result = compile_candidate(grounded_candidate("FINANCIAL_SUPPORT", "REQUIRED", quote))
    root = result.rules[0]
    assert root.operator == "AND" and root.supported
    assert root.children[0].subject_reference == SubjectReference.FINANCIAL_SUPPORT
    assert not root.children[1].supported
    assert result.conditional


@pytest.mark.parametrize(
    "quote",
    [
        "Winners must pass identity verification.",
        "Winners must pay applicable taxes.",
        "Awards are at the organizer's discretion.",
        "Projects must meet reward conditions unless exempt.",
        "Projects may meet reward conditions or decline the award.",
    ],
)
def test_reward_individual_conditions_are_not_declared_project_fact(grounded_candidate, quote):
    result = compile_candidate(
        grounded_candidate(
            "REWARD_CONDITIONS",
            "REQUIRED",
            quote,
            text=quote,
            exceptions=(quote,) if "unless" in quote else (),
        )
    )
    assert not result.rules[0].supported
    assert result.reason_codes


def test_reward_tax_is_an_unresolved_required_conjunct(grounded_candidate):
    quote = "Projects must meet reward conditions and winners must pay taxes."
    result = compile_candidate(grounded_candidate("REWARD_CONDITIONS", "REQUIRED", quote))
    root = result.rules[0]
    assert root.supported and root.operator == "AND"
    assert root.children[0].subject_reference == SubjectReference.REWARD_CONDITIONS
    assert not root.children[1].supported


@pytest.mark.parametrize(
    "quote,value,reason",
    [
        ("The total prize pool is USD 75000.", "USD 75000", "PRIZE_POOL_NOT_INDIVIDUAL_REWARD"),
        ("Winners receive USD 300 in cloud credits.", "USD 300", "CREDIT_NOT_CASH"),
    ],
)
def test_reward_pool_and_credits_never_become_guaranteed_cash(
    grounded_candidate, quote, value, reason
):
    result = compile_candidate(grounded_candidate("REWARD_CONDITIONS", value, quote))
    assert result.normalized_value is None
    assert all(not rule.supported and rule.subject_reference is None for rule in result.rules)
    assert reason in result.reason_codes


def test_deadline_missing_timezone_database_fails_closed(grounded_candidate, monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError

    def unavailable(key):
        raise ZoneInfoNotFoundError(key)

    monkeypatch.setattr("qualor.runtime.adapters.deadline.ZoneInfo", unavailable)
    result = compile_candidate(
        grounded_candidate(
            "DEADLINE", "2027-07-07T00:00:00Z", "Deadline: July 6, 2027 at 17:00 Pacific Time."
        )
    )
    assert result.normalization_status == "AMBIGUOUS"
    assert result.normalized_value is None


def test_compiler_deterministic_revision_and_expression_bound_ids(grounded_candidate):
    from datetime import timedelta

    from qualor.runtime.adapters import adapt_candidate

    candidate = grounded_candidate(
        "REQUIRED_TECHNOLOGY", "Copper SDK", "Build a tool with Copper SDK."
    )
    first = compile_candidate(candidate)
    second = adapt_candidate(
        candidate, evaluated_at=candidate.source.retrieved_at + timedelta(hours=1)
    )
    assert first.rules[0].id == second.rules[0].id
    assert first.evidence[0].id == second.evidence[0].id
    changed = candidate.model_copy(
        update={"source": candidate.source.model_copy(update={"content_hash": "f" * 64})}
    )
    assert compile_candidate(changed).rules[0].id != first.rules[0].id
    assert compile_candidate(changed).evidence[0].id != first.evidence[0].id
    assert first.rules[0].created_at == candidate.source.retrieved_at


def test_compiler_branch_residual_ids_are_unique(grounded_candidate):
    quote = (
        "Open to individuals aged at least 18 or teams of 2 to 5 members "
        "with an authorized representative."
    )
    result = compile_candidate(grounded_candidate("ENTRANT_TYPE", ("INDIVIDUAL", "TEAM"), quote))
    identifiers = [node.id for node in nodes(result.rules[0])]
    assert len(set(identifiers)) == len(identifiers)


def test_compiler_does_not_erase_first_line_as_heading(grounded_candidate):
    quotes = ("Projects must use Copper SDK", "Projects must use Silver API.")
    result = compile_candidate(grounded_candidate("REQUIRED_TECHNOLOGY", "Silver API", quotes))
    assert not result.rules[0].supported


@pytest.mark.parametrize(
    "family,value,quote",
    [
        ("LICENSE", "MIT", "Projects must intend to use the MIT license."),
        ("REQUIRED_TECHNOLOGY", "Copper SDK", "Build a tool using Copper SDK."),
        ("GEOGRAPHY", "Canada", "Entrants must reside in Canada."),
    ],
)
def test_compiler_governing_exception_omission_blocks_authority(
    grounded_candidate, family, value, quote
):
    exception = "Except invited exhibitors."
    candidate = grounded_candidate(family, value, quote, text=quote + "\n" + exception)
    assert not candidate.semantic_context_complete
    result = compile_candidate(candidate)
    assert result.normalization_status == "UNKNOWN"
    assert not result.rules[0].supported
    assert result.rules[0].clause_context == candidate.context
    assert exception in result.rules[0].clause_context.exceptions
    assert exception in tuple(record.supporting_excerpt for record in result.evidence)


def test_compiler_exact_multispan_and_remote_evidence_not_concatenated(grounded_candidate):
    quotes = ("Projects must intend to use the", "MIT license.")
    qualifier = "Only registered finalists must comply."
    candidate = grounded_candidate("LICENSE", "MIT", quotes, qualifiers=(qualifier,))
    result = compile_candidate(candidate)
    assert result.normalization_status == "UNKNOWN"
    assert tuple(record.supporting_excerpt for record in result.evidence) == (*quotes, qualifier)
    for node in nodes(result.rules[0]):
        assert node.evidence_ids == tuple(record.id for record in result.evidence)
        assert node.clause_context == candidate.context


def test_compiler_rejects_naive_clock(grounded_candidate):
    from qualor.runtime.adapters import adapt_candidate

    candidate = grounded_candidate("LICENSE", "MIT", "Projects must intend to use the MIT license.")
    with pytest.raises(ValueError, match="ADAPTER_CLOCK_REQUIRES_TIMEZONE"):
        adapt_candidate(candidate, evaluated_at=datetime(2027, 1, 1))


def test_compiler_bounds_rules_before_dropping_residuals(grounded_candidate):
    from qualor.runtime.adapters.base import Compiler

    candidate = grounded_candidate("LICENSE", "MIT", "Projects must intend to use the MIT license.")
    compiler = Compiler(candidate, candidate.source.retrieved_at)
    with pytest.raises(ValueError, match="ADAPTER_RULE_LIMIT"):
        compiler.finish(compiler.combine(tuple(compiler.unresolved() for _ in range(100))))


def test_compiler_evidence_overflow_fails_boundedly(grounded_candidate):
    quote = "Projects must intend to use the MIT license."
    candidate = grounded_candidate("LICENSE", "MIT", quote)
    # A malformed caller cannot make the bundle silently discard governing evidence.
    candidate = candidate.model_copy(update={"quotes": (quote,) * 41})
    with pytest.raises(ValueError, match="ADAPTER_EVIDENCE_LIMIT"):
        compile_candidate(candidate)


@pytest.mark.parametrize(
    "family,value,quote",
    [
        (
            "REQUIRED_TECHNOLOGY",
            "Copper SDK",
            "Projects must use Copper SDK only if entering the advanced track.",
        ),
        (
            "LICENSE",
            "MIT",
            "Projects must intend to use the MIT license unless granted an exemption.",
        ),
    ],
)
def test_qualified_literal_retains_typed_base_without_executable_applicability(
    grounded_candidate, family, value, quote
):
    result = compile_candidate(
        grounded_candidate(
            family,
            value,
            quote,
            text=quote,
            qualifiers=(quote,),
            exceptions=(quote,) if "unless" in quote else (),
        )
    )
    root = result.rules[0]
    assert not root.supported and root.operator == "AND"
    assert any(n.operands and n.operands[0].value == value for n in nodes(root))
    assert any(not n.supported and not n.operands for n in nodes(root))
    assert result.conditional


@pytest.mark.parametrize(
    "family,value,quote",
    [
        (
            "PROJECT_POLICY",
            "NEW_ONLY",
            "Projects must be new during the submission period except invited exhibits.",
        ),
        (
            "FINANCIAL_SUPPORT",
            "REQUIRED",
            "Projects must have sponsor support and disclose funding unless exempt.",
        ),
        (
            "REWARD_CONDITIONS",
            "REQUIRED",
            "Projects must meet reward conditions and pay taxes unless exempt.",
        ),
    ],
)
def test_exception_in_residual_cannot_leave_known_predicate_executable(
    grounded_candidate, family, value, quote
):
    result = compile_candidate(
        grounded_candidate(
            family, value, quote, text=quote, qualifiers=(quote,), exceptions=(quote,)
        )
    )
    assert not result.rules[0].supported
    assert result.normalization_status == "UNKNOWN"


def test_boolean_proposal_cannot_replace_a_source_alternative_with_one_literal(grounded_candidate):
    quote = "Projects must use Copper SDK or Silver API."
    result = compile_candidate(
        grounded_candidate("REQUIRED_TECHNOLOGY", "Copper SDK or Silver API", quote)
    )
    assert not result.rules[0].supported


@pytest.mark.parametrize(
    "quote,qualifiers",
    [
        (" Projects must intend to use the MIT license. ", ()),
        ("Projects must intend to use the MIT license.", (" Only finalists must comply. ",)),
    ],
)
def test_padded_evidence_fails_closed_before_existing_contract_can_rewrite_it(
    grounded_candidate, quote, qualifiers
):
    candidate = grounded_candidate("LICENSE", "MIT", quote.strip())
    candidate = candidate.model_copy(
        update={
            "quotes": (quote,),
            "context": candidate.context.model_copy(update={"qualifiers": qualifiers}),
            "source": candidate.source.model_copy(update={"text": "\n".join((quote, *qualifiers))}),
        }
    )
    with pytest.raises(ValueError, match="^ADAPTER_EVIDENCE_WHITESPACE_UNREPRESENTED$"):
        compile_candidate(candidate)


def test_source_literal_casing_cannot_create_a_spurious_stack_mismatch(grounded_candidate):
    result = compile_candidate(
        grounded_candidate("REQUIRED_TECHNOLOGY", "copper sdk", "Build a tool with Copper SDK.")
    )
    assert not result.rules[0].supported or result.rules[0].operands[0].value == "Copper SDK"


@pytest.mark.parametrize(
    "family,value,quote,founder,project",
    [
        (
            "LICENSE",
            "MIT",
            "The public repository must use the MIT license.",
            {},
            {"license_intent": {"value": "Proprietary", "provenance": "USER_ASSERTED"}},
        ),
        (
            "GEOGRAPHY",
            "Canada",
            "Entrants must not reside in Canada or any jurisdiction "
            "where participation is prohibited by law.",
            {"country_of_residence": {"value": "Mexico", "provenance": "USER_ASSERTED"}},
            {},
        ),
        (
            "ENTRANT_TYPE",
            ("INDIVIDUAL", "TEAM"),
            "Open to individuals aged at least 18 or teams of 2 to 5 members "
            "with an authorized representative.",
            {
                "legal_form": {"value": "INDIVIDUAL", "provenance": "USER_ASSERTED"},
                "team_size": {"value": 1, "provenance": "USER_ASSERTED"},
            },
            {},
        ),
        (
            "REQUIRED_TECHNOLOGY",
            "Copper SDK",
            "Projects must use Copper SDK only if entering the advanced track.",
            {},
            {"technology_stack": {"value": ("Other SDK",), "provenance": "USER_ASSERTED"}},
        ),
        (
            "GEOGRAPHY",
            "any jurisdiction where participation is prohibited by law",
            "Entrants must not reside in any jurisdiction "
            "where participation is prohibited by law.",
            {"country_of_residence": {"value": "Mexico", "provenance": "USER_ASSERTED"}},
            {},
        ),
        (
            "REQUIRED_TECHNOLOGY",
            "Copper SDK if entering the advanced track",
            "Projects must use Copper SDK if entering the advanced track.",
            {},
            {"technology_stack": {"value": ("Other SDK",), "provenance": "USER_ASSERTED"}},
        ),
    ],
)
def test_existing_engine_retains_unknown_for_unrepresented_compliance(
    grounded_candidate, family, value, quote, founder, project
):
    from qualor.domain.fixture import EvaluationContext
    from qualor.domain.opportunity import OpportunityRecord
    from qualor.domain.profiles import FounderProfile, ProjectProfile
    from qualor.eligibility.engine import evaluate_rules

    candidate = grounded_candidate(family, value, quote, text=quote, qualifiers=(quote,))
    result = compile_candidate(candidate)
    meta = dict(
        schema_version="1",
        version=1,
        created_at=candidate.source.retrieved_at,
        updated_at=candidate.source.retrieved_at,
        provenance="DOCUMENTED",
    )
    context = EvaluationContext(
        founder=FounderProfile(**meta, id="fixture_founder", **founder),
        project=ProjectProfile(**meta, id="fixture_project", name="Independent fixture", **project),
        opportunity=OpportunityRecord(
            **meta,
            id="fixture_opportunity",
            organizer="Fixture organizer",
            program_name="Generic program",
            edition="2027",
            canonical_rules_url=candidate.source.final_url,
        ),
        evidence=result.evidence,
        evaluated_at=candidate.source.retrieved_at,
        mode="FIXTURE",
    )
    evaluation = evaluate_rules(result.rules, context)
    assert evaluation[0].status == "UNKNOWN"


def test_geography_standalone_open_legal_scope_never_becomes_a_finite_exclusion(grounded_candidate):
    value = "any jurisdiction where participation is prohibited by law"
    quote = f"Entrants must not reside in {value}."
    result = compile_candidate(
        grounded_candidate("GEOGRAPHY", value, quote, text=quote, qualifiers=(quote,))
    )
    assert result.normalization_status in {"UNKNOWN", "UNSUPPORTED"}
    assert result.conditional
    assert "GEOGRAPHY_EXTERNAL_COMPLIANCE_REQUIRED" in result.reason_codes
    assert not any(n.supported and n.subject_reference for r in result.rules for n in nodes(r))
    assert result.evidence[0].supporting_excerpt == quote


@pytest.mark.parametrize("value", ["Copper SDK", "Copper SDK if entering the advanced track"])
def test_technology_bare_if_retains_base_only_under_unknown_applicability(
    grounded_candidate, value
):
    quote = "Projects must use Copper SDK if entering the advanced track."
    candidate = grounded_candidate(
        "REQUIRED_TECHNOLOGY", value, quote, text=quote, qualifiers=(quote,)
    )
    result = compile_candidate(candidate)
    assert not result.rules[0].supported
    assert result.conditional and result.normalization_status == "UNKNOWN"
    assert any(n.operands and n.operands[0].value == "Copper SDK" for n in nodes(result.rules[0]))
    assert all(n.clause_context == candidate.context for n in nodes(result.rules[0]))


def test_compiler_same_quote_at_distinct_grounded_positions_has_distinct_identity(document):
    from qualor.runtime.acquisition_plan import build_acquisition_plan
    from qualor.runtime.section_extraction import SectionCandidateTransport, ground_section_claim
    from qualor.runtime.section_scheduler import ExtractionJob
    from qualor.runtime.sections import index_source
    from qualor.runtime.spans import EvidenceSpanRegistry

    quote = "Projects must use Copper SDK."
    source = document(quote + " " + quote)
    registry = EvidenceSpanRegistry(secret=b"independent-span-identity-test-00")
    index = index_source(source, registry)
    first = registry.register_section(source, start_offset=0, end_offset=len(quote))[0]
    second = registry.register_section(
        source, start_offset=len(quote) + 1, end_offset=len(source.text)
    )[0]
    assert first.span_id != second.span_id and first.start_offset != second.start_offset
    section = index.sections[0].model_copy(update={"span_ids": (first.span_id, second.span_id)})
    index = index.model_copy(update={"sections": (section,)})
    plan = build_acquisition_plan(index)
    item = next(
        item
        for item in plan.items
        if item.section_id == section.section_id and Category.REQUIRED_TECHNOLOGY in item.categories
    )
    job = ExtractionJob(
        job_id="extraction_job_" + "a" * 32,
        source_id=source.id,
        source_revision=index.source_revision,
        section_id=section.section_id,
        categories=(Category.REQUIRED_TECHNOLOGY,),
        span_ids=section.span_ids,
        context_section_ids=(),
        authority_revision=0,
        plan_id=plan.plan_id,
        plan_item_id=item.item_id,
        tier=item.tier,
    )
    results = []
    for span in (first, second):
        candidate = SectionCandidateTransport(
            category="REQUIRED_TECHNOLOGY",
            proposed_value="Copper SDK",
            source_id=source.id,
            section_id=section.section_id,
            span_ids=(span.span_id,),
            qualifier_span_ids=(),
            exception_span_ids=(),
            confidence_class="HIGH",
            state="CANDIDATE",
        )
        grounded = ground_section_claim(
            candidate, source=source, index=index, job=job, registry=registry
        )
        result = compile_candidate(grounded)
        assert result.normalization_status == "SUPPORTED"
        assert result.evidence[0].supporting_excerpt == quote
        assert result == compile_candidate(grounded)
        results.append(result)
    assert results[0].evidence[0].id != results[1].evidence[0].id
    assert results[0].rules[0].id != results[1].rules[0].id


@pytest.mark.parametrize(
    "scope",
    [
        "any jurisdiction where participation is illegal",
        "any country in which entry is unlawful",
        "all territories where entry is restricted",
        "jurisdictions subject to applicable sanctions",
        "places where participation requires legal clearance",
        "Any Jurisdiction Where Participation Is Illegal",
        "Sanctioned Nations",
        "Restricted States",
    ],
)
def test_geography_abstract_scope_is_never_finite_literal_authority(grounded_candidate, scope):
    quote = f"Entrants must not reside in {scope}."
    candidate = grounded_candidate("GEOGRAPHY", scope, quote, text=quote, qualifiers=(quote,))
    result = compile_candidate(candidate)
    assert result.normalization_status in {"UNKNOWN", "UNSUPPORTED"}
    assert not any(
        node.supported and node.subject_reference is not None
        for rule in result.rules
        for node in nodes(rule)
    )
    assert result.reason_codes
    assert result.evidence[0].supporting_excerpt == quote


@pytest.mark.parametrize(
    "scope",
    [
        "Mexico",
        "Canada",
        "New Zealand",
        "United States",
        "MX",
        "NZ",
        "Brazil",
        "Japan",
        "Ghana",
        "Spain",
        "France",
    ],
)
def test_geography_named_scopes_are_retained_but_unresolved_without_positive_ontology(
    grounded_candidate, scope
):
    quote = f"Entrants must not reside in {scope}."
    result = compile_candidate(
        grounded_candidate("GEOGRAPHY", scope, quote, text=quote, qualifiers=(quote,))
    )
    assert result.normalization_status == "UNKNOWN"
    assert result.rules[0].operator == "NOT_IN"
    assert result.rules[0].operands[0].value == scope
    assert result.normalized_value == scope
    assert not result.rules[0].supported
    assert result.rules[0].subject_reference is None
    assert result.evidence[0].supporting_excerpt == quote


@pytest.mark.parametrize(
    "family,value,heading,clause",
    [
        ("LICENSE", "MIT", "License", "Projects must intend to use MIT licenses."),
        (
            "REQUIRED_TECHNOLOGY",
            "Copper SDK",
            "Technology requirements",
            "Build a tool using Copper SDK.",
        ),
    ],
)
def test_structural_heading_quote_parses_like_one_joined_quote(
    grounded_candidate, family, value, heading, clause
):
    """A heading arriving as its own capability must not change the parsing view."""

    from qualor.runtime.adapters.base import body

    class LegacyQuotes:
        """Legacy broad-focus grounding can still deliver heading and clause in one quote."""

        quotes = (heading + "\n" + clause,)

    structural = grounded_candidate(family, value, (heading, clause))

    assert body(LegacyQuotes()) == body(structural) == clause.rstrip(".")
    assert compile_candidate(structural).normalization_status == "SUPPORTED"
    assert compile_candidate(structural).normalized_value == value


@pytest.mark.parametrize(
    "first,second,family,value",
    [
        (
            "Projects must use Widget SDK.",
            "Projects must use Silver API.",
            "REQUIRED_TECHNOLOGY",
            "Widget SDK",
        ),
        (
            "Submission Period:",
            "Submissions close on January 2, 2026, 5:00 PM UTC.",
            "DEADLINE",
            "January 2, 2026",
        ),
        (
            "Judging Period:",
            "Judging closes on January 9, 2026, 5:00 PM UTC.",
            "REWARD_CONDITIONS",
            "Judging",
        ),
        (
            "Financial or Preferential Support",
            "Projects must have sponsor support.",
            "FINANCIAL_SUPPORT",
            "support",
        ),
    ],
)
def test_first_structural_quote_is_only_stripped_when_it_is_a_known_heading(
    grounded_candidate, first, second, family, value
):
    """Only the bounded heading vocabulary may be dropped from the parsing view."""

    from qualor.runtime.adapters.base import body

    candidate = grounded_candidate(family, value, (first, second))

    assert body(candidate).startswith(first.rstrip("."))


@pytest.fixture
def real_timezone_database(monkeypatch):
    """Use the packaged IANA database instead of the two synthetic 2027 tables."""

    from zoneinfo import ZoneInfo

    monkeypatch.setattr("qualor.runtime.adapters.deadline.ZoneInfo", ZoneInfo)
    return ZoneInfo


SUBMISSION_OPENING = "Monday, August 10, 2026 (9:00 am Pacific Time)"
SUBMISSION_CLOSING = "Monday, September 14, 2026 (5:00 pm Pacific Time)"
SUBMISSION_VALUE = SUBMISSION_OPENING + " – " + SUBMISSION_CLOSING + " (“Submission Period”)."


@pytest.mark.parametrize(
    "text,expected",
    [
        (SUBMISSION_OPENING, datetime(2026, 8, 10, 16, tzinfo=UTC)),
        (SUBMISSION_CLOSING, datetime(2026, 9, 15, 0, tzinfo=UTC)),
    ],
)
def test_parenthesized_dated_instant_resolves_through_zoneinfo(
    real_timezone_database, text, expected
):
    from qualor.runtime.adapters.deadline import parse_dated_instant

    assert parse_dated_instant(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Tuesday, August 10, 2026 (9:00 am Pacific Time)",
        "Monday, August 10 (9:00 am Pacific Time)",
        "Monday, August 10, 2026 (9:00 am)",
        "Monday, August 10, 2026 (9:00 am CST)",
        "08/10/2026 (9:00 am Pacific Time)",
        "Sunday, March 8, 2026 (2:30 am Pacific Time)",
        "Sunday, November 1, 2026 (1:30 am Pacific Time)",
    ],
)
def test_unresolvable_dated_instants_stay_none(real_timezone_database, text):
    from qualor.runtime.adapters.deadline import parse_dated_instant

    assert parse_dated_instant(text) is None


def test_submission_period_interval_compiles_to_executable_authority(
    grounded_candidate, real_timezone_database
):
    candidate = grounded_candidate(
        "DEADLINE",
        (SUBMISSION_OPENING, SUBMISSION_CLOSING),
        ("Submission Period:", SUBMISSION_VALUE),
    )
    result = compile_candidate(candidate)
    rule = result.rules[0]

    assert result.normalization_status == "SUPPORTED"
    assert rule.supported
    assert rule.operator is Operator.DATE_BETWEEN
    assert rule.subject_reference is SubjectReference.EVALUATED_AT
    assert [operand.value for operand in rule.operands] == [
        datetime(2026, 8, 10, 16, tzinfo=UTC),
        datetime(2026, 9, 15, 0, tzinfo=UTC),
    ]
    assert all(record.supporting_excerpt in candidate.source.text for record in result.evidence)


@pytest.mark.parametrize(
    "label,term",
    [("Judging Period:", "Judging Period"), ("Review Period:", "Review Period")],
)
def test_other_labelled_periods_are_not_submission_authority(
    grounded_candidate, real_timezone_database, label, term
):
    value = SUBMISSION_OPENING + " – " + SUBMISSION_CLOSING + f" (“{term}”)."
    candidate = grounded_candidate(
        "DEADLINE", (SUBMISSION_OPENING, SUBMISSION_CLOSING), (label, value)
    )

    assert compile_candidate(candidate).normalization_status != "SUPPORTED"


def test_winners_announced_is_not_submission_authority(grounded_candidate, real_timezone_database):
    candidate = grounded_candidate(
        "DEADLINE",
        SUBMISSION_CLOSING,
        ("Winners Announced:", "On or around " + SUBMISSION_CLOSING + "."),
    )

    assert compile_candidate(candidate).normalization_status != "SUPPORTED"


@pytest.mark.parametrize(
    "value",
    [
        SUBMISSION_OPENING + " (“Submission Period”).",
        SUBMISSION_CLOSING + " – " + SUBMISSION_OPENING + " (“Submission Period”).",
    ],
)
def test_incomplete_or_reversed_submission_intervals_stay_unresolved(
    grounded_candidate, real_timezone_database, value
):
    candidate = grounded_candidate(
        "DEADLINE", (SUBMISSION_OPENING, SUBMISSION_CLOSING), ("Submission Period:", value)
    )

    assert compile_candidate(candidate).normalization_status != "SUPPORTED"
