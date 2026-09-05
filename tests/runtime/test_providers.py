from dataclasses import fields

import pytest

from qualor.runtime import FetchedSource, ModelResponse, SearchCandidate


def test_C08_provider_outputs_cannot_set_final_eligibility_or_recommendation():
    forbidden = {"eligibility", "eligibility_gate", "recommendation", "decision"}
    for contract in (SearchCandidate, FetchedSource, ModelResponse):
        assert forbidden.isdisjoint(field.name for field in fields(contract))


def test_search_candidate_is_explicitly_candidate_only():
    candidate = SearchCandidate(
        url="https://example.com/opportunity",
        title="Candidate",
        snippet="Search result text",
    )
    assert candidate.can_create_candidate is True
    assert candidate.can_prove_hard_eligibility is False


def test_search_candidate_cannot_be_constructed_as_hard_evidence():
    with pytest.raises(TypeError):
        SearchCandidate(
            url="https://example.com/opportunity",
            title="Candidate",
            snippet="Search result text",
            can_prove_hard_eligibility=True,
        )
