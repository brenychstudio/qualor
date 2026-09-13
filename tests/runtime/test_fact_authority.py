"""Independent applicant and project fact authority boundaries."""

from datetime import UTC, datetime

import pytest

from qualor.domain.base import Fact
from qualor.domain.enums import CodeProvenance, Provenance

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)


def test_opportunity_rules_cannot_fill_independent_applicant_or_project_facts(
    studio_inputs, grounded_candidate
):
    from qualor.runtime.adapters import adapt_candidate
    from qualor.runtime.fact_authority import independent_decision_facts

    hostile_claims = (
        ("GEOGRAPHY", "Canada", "Entrants must reside in Canada."),
        ("GEOGRAPHY", "Canada", "Entrants must be citizens of Canada."),
        ("LEGAL_ENTITY", "INCORPORATED_COMPANY", "Applicants must be incorporated companies."),
        (
            "LEGAL_ENTITY",
            "INCORPORATED_COMPANY",
            "Applicants must be incorporated companies incorporated between "
            "2020-01-01 and 2025-12-31.",
        ),
        ("PROJECT_POLICY", "NEW_ONLY", "Projects must be newly created."),
        ("REQUIRED_TECHNOLOGY", "Widget SDK", "Build an agent using Widget SDK."),
        ("LICENSE", "MIT", "Projects must intend to use the MIT license."),
        ("FINANCIAL_SUPPORT", "REQUIRED", "Projects must have sponsor support."),
    )
    before = studio_inputs.model_dump_json()
    compiled = tuple(
        adapt_candidate(
            grounded_candidate(category, value, quote),
            evaluated_at=NOW,
        )
        for category, value, quote in hostile_claims
    )

    founder, projects = independent_decision_facts(studio_inputs)

    assert all(result.rules for result in compiled)
    assert founder is studio_inputs.founder
    assert projects is studio_inputs.projects
    assert projects[0] is studio_inputs.projects[0]
    assert projects[0].project is studio_inputs.projects[0].project
    assert (
        founder.country_of_residence.value,
        founder.citizenship.value,
        founder.legal_form.value,
        founder.incorporation_date.value,
    ) == (None, None, None, None)
    assert (
        projects[0].project.is_new_project.value,
        projects[0].project.technology_stack.value,
        projects[0].project.license_intent.value,
        projects[0].project.has_sponsor_support.value,
    ) == (None, None, None, None)
    assert studio_inputs.model_dump_json() == before


@pytest.mark.parametrize(
    ("fact", "scope", "verified_at", "expected"),
    [
        (
            Fact(value="Spain", provenance=Provenance.USER_ASSERTED),
            "OWNER",
            None,
            "OWNER_PROVIDED",
        ),
        (
            Fact(
                value="Spain",
                provenance=Provenance.DOCUMENTED,
                evidence_refs=("owner-document",),
            ),
            "OWNER",
            NOW,
            "UNKNOWN",
        ),
        (
            Fact(value=True, provenance=Provenance.USER_ASSERTED),
            "PROJECT",
            None,
            "PROJECT_STATE",
        ),
        (
            Fact(
                value=CodeProvenance.ORIGINAL,
                provenance=Provenance.DOCUMENTED,
                evidence_refs=("project-code-review",),
            ),
            "PROJECT",
            None,
            "PROJECT_STATE",
        ),
        (Fact(), "OWNER", NOW, "UNKNOWN"),
        (
            Fact(
                value="account state",
                provenance=Provenance.DOCUMENTED,
                evidence_refs=("account-evidence",),
            ),
            "ACCOUNT",
            NOW,
            "VERIFIED_ACCOUNT_STATE",
        ),
        (
            Fact(value="account state", provenance=Provenance.DOCUMENTED),
            "ACCOUNT",
            NOW,
            "UNKNOWN",
        ),
        (
            Fact(
                value="account state",
                provenance=Provenance.DOCUMENTED,
                evidence_refs=("account-evidence",),
            ),
            "ACCOUNT",
            None,
            "UNKNOWN",
        ),
        (
            Fact(
                value="account state",
                provenance=Provenance.USER_ASSERTED,
                evidence_refs=("account-evidence",),
            ),
            "ACCOUNT",
            NOW,
            "UNKNOWN",
        ),
        (
            Fact.model_construct(
                value=None,
                provenance=Provenance.USER_ASSERTED,
                evidence_refs=(),
            ),
            "OWNER",
            NOW,
            "UNKNOWN",
        ),
        (
            Fact.model_construct(
                value=None,
                provenance=Provenance.DOCUMENTED,
                evidence_refs=("project-evidence",),
            ),
            "PROJECT",
            NOW,
            "UNKNOWN",
        ),
        (
            Fact.model_construct(
                value=None,
                provenance=Provenance.DOCUMENTED,
                evidence_refs=("account-evidence",),
            ),
            "ACCOUNT",
            NOW,
            "UNKNOWN",
        ),
    ],
)
def test_fact_authority_requires_the_exact_scope_and_provenance_contract(
    fact, scope, verified_at, expected
):
    from qualor.runtime.fact_authority import fact_authority_class

    before = fact.model_dump_json()

    assert fact_authority_class(fact, scope=scope, verified_at=verified_at) == expected
    assert fact.model_dump_json() == before


def test_verified_login_receipt_does_not_supply_financial_eligibility(
    studio_inputs, grounded_candidate
):
    from qualor.runtime.adapters import adapt_candidate
    from qualor.runtime.fact_authority import fact_authority_class, independent_decision_facts

    login_receipt = Fact(
        value="LOGIN_SUCCEEDED",
        provenance=Provenance.DOCUMENTED,
        evidence_refs=("account-login-receipt",),
    )
    before = studio_inputs.model_dump_json()
    financial_rule = adapt_candidate(
        grounded_candidate(
            "FINANCIAL_SUPPORT", "REQUIRED", "Projects must have sponsor support."
        ),
        evaluated_at=NOW,
    )

    assert financial_rule.rules
    assert (
        fact_authority_class(login_receipt, scope="ACCOUNT", verified_at=NOW)
        == "VERIFIED_ACCOUNT_STATE"
    )
    _, projects = independent_decision_facts(studio_inputs)
    assert projects is studio_inputs.projects
    assert projects[0].project.has_sponsor_support is studio_inputs.projects[
        0
    ].project.has_sponsor_support
    assert projects[0].project.has_sponsor_support == Fact()
    assert studio_inputs.model_dump_json() == before
