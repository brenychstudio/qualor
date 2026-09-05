from datetime import UTC, datetime, timedelta

import pytest

from qualor.conflicts import (
    ActiveSubmission,
    ConflictCategory,
    ConflictRule,
    ConflictStatus,
    assess_conflicts,
)
from qualor.domain.evidence import EvidenceRecord
from qualor.domain.opportunity import OpportunityRecord
from qualor.domain.profiles import ProjectProfile

NOW = datetime(2026, 9, 5, tzinfo=UTC)
CLEAR = "NO_CONFLICT_DETECTED_IN_CHECKED_RULES"
BLOCK = "BLOCKED_BY_EXPLICIT_RULE"
REVIEW = "REVIEW_REQUIRED"


def fact(value):
    return dict(value=value, provenance="USER_ASSERTED")


def meta(id):
    return dict(
        id=id,
        schema_version="1",
        version=1,
        created_at=NOW,
        updated_at=NOW,
        provenance="USER_ASSERTED",
    )


def project(**changes):
    fields = dict(
        name="Synthetic",
        is_new_project=fact(True),
        code_provenance=fact("ORIGINAL"),
        project_lineage=fact(()),
        reused_components=fact(()),
        reuse_disclosed=fact(True),
        license_intent=fact("MIT"),
        has_sponsor_support=fact(False),
    )
    fields.update(changes)
    return ProjectProfile(**meta("project"), **fields)


def opportunity():
    return OpportunityRecord(
        **meta("opp"),
        organizer="Synthetic",
        program_name="Test",
        edition="2026",
        canonical_rules_url="https://example.com/rules",
    )


def rules(active=None, **changes):
    return tuple(
        ConflictRule(
            id=c.value,
            category=c,
            applies=fact(c.value == active),
            supported=True,
            evidence_ids=(c.value,),
            allowed_licenses=fact(("MIT",)),
            **changes,
        )
        for c in ConflictCategory
    )


def evidence(**changes):
    result = []
    for c in ConflictCategory:
        fields = dict(
            original_url="https://example.com/rules",
            final_url="https://example.com/rules",
            retrieved_at=NOW,
            source_type="SYNTHETIC_FIXTURE",
            content_hash="a" * 64,
            supporting_excerpt="Synthetic explicit policy",
            extraction_state="REVIEWED",
            normalized_field={"LICENSE": "LICENSE", "SPONSOR_SUPPORT": "FINANCIAL_SUPPORT"}.get(
                c.value, "PROJECT_POLICY"
            ),
        )
        fields.update(changes)
        result.append(EvidenceRecord(**meta(c.value), **fields))
    return tuple(result)


def submission(**changes):
    fields = dict(
        contest="external",
        project_id="other",
        project_lineage=fact(()),
        code_origin=fact("ORIGINAL"),
        sponsor_support=fact(False),
        submission_dates=(),
        license=fact("MIT"),
        reused_components=fact(()),
        rules_evidence_refs=tuple(c.value for c in ConflictCategory),
        facts_provenance="USER_ASSERTED",
        conflict_rules=rules(),
    )
    fields.update(changes)
    return ActiveSubmission(**meta("submission"), **fields)


def assess(p=None, r=None, s=(), e=None, at=NOW):
    return assess_conflicts(
        p or project(),
        opportunity(),
        rules() if r is None else r,
        s,
        evidence() if e is None else e,
        at,
    )


def test_b37_qualified_clear_has_scoped_complete_coverage():
    result = assess(s=(submission(),))
    assert result.status == CLEAR
    assert len(result.checked_rule_categories) == 14
    assert result.missing_rule_categories == ()
    assert result.evidence_ids
    assert result.evaluated_at == NOW


def test_b38_no_absolute_clear_status():
    with pytest.raises(ValueError):
        ConflictStatus("NO_CONFLICT")


@pytest.mark.parametrize(
    "category,changes,subs",
    [
        ("NEW_PROJECT", dict(project_lineage=fact(("old",))), ()),
        ("EXCLUSIVE_SUBMISSION", {}, (submission(),)),
        ("LICENSE", dict(license_intent=fact("GPL")), ()),
        ("SPONSOR_SUPPORT", dict(has_sponsor_support=fact(True)), ()),
        (
            "SAME_PROJECT",
            dict(project_lineage=fact(("shared",))),
            (submission(project_lineage=fact(("shared",))),),
        ),
        ("EXISTING_PROJECT", dict(is_new_project=fact(False)), ()),
        ("DISCLOSURE", dict(reused_components=fact(("library",)), reuse_disclosed=fact(False)), ()),
    ],
)
def test_all_explicit_violations_including_b35(category, changes, subs):
    assert assess(project(**changes), rules(category), subs).status == BLOCK


@pytest.mark.parametrize("category", [c.value for c in ConflictCategory])
def test_each_category_can_be_checked_without_violation(category):
    assert assess(r=rules(category)).status == CLEAR


@pytest.mark.parametrize(
    "category,changes,subs",
    [
        ("NEW_PROJECT", dict(project_lineage={}), ()),
        ("SPONSOR_SUPPORT", dict(has_sponsor_support={}), ()),
        ("DISCLOSURE", dict(reused_components=fact(("library",)), reuse_disclosed={}), ()),
        ("SAME_PROJECT", dict(project_lineage={}), (submission(),)),
        ("LICENSE", dict(license_intent={}), ()),
        ("EXISTING_PROJECT", dict(is_new_project={}), ()),
    ],
)
def test_unknown_facts_require_review(category, changes, subs):
    assert assess(project(**changes), rules(category), subs).status == REVIEW


def test_b36_missing_external_rules_require_review():
    result = assess(s=(submission(conflict_rules=()),))
    assert result.status == REVIEW
    assert len(result.missing_rule_categories) == 7


def test_external_exclusivity_is_checked_against_proposed_submission():
    assert assess(s=(submission(conflict_rules=rules("EXCLUSIVE_SUBMISSION")),)).status == BLOCK


@pytest.mark.parametrize(
    "changes",
    [
        dict(source_type="SEARCH_SNIPPET"),
        dict(source_type="THIRD_PARTY"),
        dict(normalized_field="DEADLINE"),
        dict(extraction_state="UNVERIFIED"),
        dict(retrieved_at=NOW - timedelta(hours=6)),
        dict(retrieved_at=NOW + timedelta(seconds=1)),
    ],
)
def test_unusable_evidence_even_for_not_applicable_requires_review(changes):
    assert assess(e=evidence(**changes)).status == REVIEW


def test_missing_evidence_and_unsupported_rules_require_review():
    assert assess(e=()).status == REVIEW
    modified = (rules()[0].model_copy(update={"supported": False}),) + rules()[1:]
    assert assess(r=modified).status == REVIEW


def test_confirmed_violation_outranks_missing_coverage():
    assert (
        assess(
            project(is_new_project=fact(False)),
            rules("EXISTING_PROJECT")[5:6],
            (submission(conflict_rules=()),),
        ).status
        == BLOCK
    )


@pytest.mark.parametrize("kind", ["rule_id", "category", "submission", "evidence", "contest"])
def test_ambiguous_duplicates_rejected(kind):
    r, s, e = rules(), (), evidence()
    if kind == "rule_id":
        r = (r[0], r[1].model_copy(update={"id": r[0].id}))
    if kind == "category":
        r += (r[0].model_copy(update={"id": "extra"}),)
    if kind == "submission":
        s = (submission(), submission())
    if kind == "contest":
        s = (submission(), submission().model_copy(update={"id": "another"}))
    if kind == "evidence":
        e += (e[0],)
    with pytest.raises(ValueError):
        assess(r=r, s=s, e=e)


def test_public_inputs_revalidated_and_aware_time_required():
    with pytest.raises(ValueError):
        assess(p=project().model_copy(update={"reuse_disclosed": {"value": True}}))
    with pytest.raises(ValueError):
        assess(at=NOW.replace(tzinfo=None))


def test_repeated_evidence_ids_within_rule_are_rejected():
    r = rules()
    ambiguous = r[0].model_copy(update={"evidence_ids": (r[0].id, r[0].id)})
    with pytest.raises(ValueError):
        assess(r=(ambiguous,) + r[1:])


def test_fabricated_nested_external_rule_is_revalidated():
    s = submission().model_copy(
        update={"conflict_rules": (rules()[0].model_copy(update={"supported": "yes"}),)}
    )
    with pytest.raises(ValueError):
        assess(s=(s,))


@pytest.mark.parametrize(
    "category,changes",
    [
        ("NEW_PROJECT", dict(is_new_project=fact(False), project_lineage={})),
        ("NEW_PROJECT", dict(code_provenance=fact("MIXED"), is_new_project={})),
        ("NEW_PROJECT", dict(reused_components=fact(("old",)), project_lineage={})),
    ],
)
def test_explicit_new_project_violation_survives_other_unknown_facts(category, changes):
    assert assess(project(**changes), rules(category)).status == BLOCK


def test_same_id_violation_survives_unknown_lineage():
    assert (
        assess(
            r=rules("SAME_PROJECT"), s=(submission(project_id="project", project_lineage={}),)
        ).status
        == BLOCK
    )


def test_unknown_applicability_and_unsupported_violation_require_review():
    r = rules("NEW_PROJECT")
    for updates in ({"applies": {}}, {"supported": False}):
        modified = (r[0].model_copy(update=updates),) + r[1:]
        assert assess(project(is_new_project=fact(False)), modified).status == REVIEW


def test_missing_allowed_licenses_requires_review():
    r = rules("LICENSE")
    modified = tuple(
        x.model_copy(update={"allowed_licenses": {}}) if x.category == "LICENSE" else x for x in r
    )
    assert assess(r=modified).status == REVIEW


def test_external_rules_need_explicit_submission_evidence_references():
    assert assess(s=(submission(rules_evidence_refs=()),)).status == REVIEW


@pytest.mark.parametrize(
    "category,updates",
    [
        ("LICENSE", dict(license=fact("GPL"))),
        ("SPONSOR_SUPPORT", dict(sponsor_support=fact(True))),
        ("NEW_PROJECT", dict(code_origin=fact("REUSED"))),
        ("DISCLOSURE", dict(reused_components=fact(("library",)))),
    ],
)
def test_same_project_disagreeing_relevant_facts_require_review(category, updates):
    assert (
        assess(r=rules(category), s=(submission(project_id="project", **updates),)).status == REVIEW
    )


def test_confirmed_violation_outranks_same_project_fact_disagreement():
    assert (
        assess(
            project(license_intent=fact("GPL")),
            rules("LICENSE"),
            (submission(project_id="project"),),
        ).status
        == BLOCK
    )
