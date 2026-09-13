"""Section candidates carry capabilities, never model-authored evidence."""

import json

import pytest
from pydantic import ValidationError

from qualor.domain.enums import Category
from qualor.runtime.acquisition_coverage import AcquisitionOutcome, CoverageLedger
from qualor.runtime.extraction import BedrockClaimExtractor
from qualor.runtime.live_cli import live_budget
from qualor.runtime.section_scheduler import ExtractionJob, NoExtractionJob, SectionScheduler
from qualor.runtime.sections import index_source
from qualor.runtime.spans import EvidenceSpanRegistry

GLOBAL_MARKER = "This section applies to all sections. " + ("Padding words here. " * 18)


def global_context_source(body, *, target="An MIT license is required."):
    """Twelve capabilities reached through explicit global scope, not sibling smear."""

    return (
        "1. License\n" + target + "\n"
        "2. General Conditions\n" + GLOBAL_MARKER + "\n" + body
    )


def setup_job(document, text="License\nAn MIT license is required.", *, registry=None):
    source = document(text)
    registry = registry or EvidenceSpanRegistry(secret=b"s" * 32)
    index = index_source(source, registry)
    target = index.sections[0]
    required = set()
    pending = list(target.context_section_ids)
    while pending:
        section_id = pending.pop()
        if section_id == target.section_id or section_id in required:
            continue
        required.add(section_id)
        pending.extend(
            next(s for s in index.sections if s.section_id == section_id).context_section_ids
        )
    context = tuple(s for s in index.sections if s.section_id in required)
    job = ExtractionJob(
        job_id="extraction_job_" + "a" * 32,
        source_id=source.id,
        source_revision=index.source_revision,
        section_id=target.section_id,
        categories=(Category.LICENSE,),
        span_ids=tuple(sid for section in (target, *context) for sid in section.span_ids),
        context_section_ids=tuple(section.section_id for section in context),
        authority_revision=0,
    )
    assert isinstance(job, ExtractionJob)
    return source, index, job, registry


def candidate(job, **changes):
    from qualor.runtime.section_extraction import validate_section_payload

    item = dict(
        category=job.categories[0].value,
        proposed_value="MIT",
        source_id=job.source_id,
        section_id=job.section_id,
        span_ids=[job.span_ids[0]],
        qualifier_span_ids=[],
        exception_span_ids=[],
        confidence_class="HIGH",
        state="CANDIDATE",
    )
    item.update(changes)
    return validate_section_payload({"claims": [item]}).claims[0]


def ground(item, setup):
    from qualor.runtime.section_extraction import ground_section_claim

    source, index, job, registry = setup
    return ground_section_claim(item, source=source, index=index, job=job, registry=registry)


def test_exact_quotes_and_private_source_serialization(document):
    setup = setup_job(document)
    result = ground(candidate(setup[2]), setup)
    assert result.quotes == ("License\nAn MIT license is required.",)
    assert result.context.span_ids == setup[2].span_ids
    assert result.semantic_context_complete
    assert "source" not in result.model_dump()
    assert '"text"' not in result.model_dump_json()


@pytest.mark.parametrize("field", ["quote", "quotes", "excerpt"])
def test_model_authored_quotes_rejected(document, field):
    setup = setup_job(document)
    with pytest.raises(ValidationError):
        candidate(setup[2], **{field: "invented quote"})


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"source_id": "other"}, "EXTRACTION_SOURCE_REFERENCE_MISMATCH"),
        ({"section_id": "section_" + "f" * 32}, "EXTRACTION_SECTION_REFERENCE_MISMATCH"),
        ({"category": "DEADLINE"}, "EXTRACTION_CATEGORY_NOT_ALLOWED"),
        ({"span_ids": ["span_" + "f" * 32]}, "SPAN_REFERENCE_NOT_FOUND"),
        ({"qualifier_span_ids": ["span_" + "f" * 32]}, "SPAN_REFERENCE_NOT_FOUND"),
        ({"exception_span_ids": ["span_" + "f" * 32]}, "SPAN_REFERENCE_NOT_FOUND"),
    ],
)
def test_invalid_capabilities_are_operational(document, changes, reason):
    setup = setup_job(document)
    with pytest.raises(ValueError, match=reason):
        ground(candidate(setup[2], **changes), setup)


def test_prior_run_and_out_of_job_spans_rejected(document):
    setup = setup_job(document, "License\nAn MIT license is required.\n2 Notes\nOrdinary notes.")
    prior = setup_job(document, setup[0].text, registry=EvidenceSpanRegistry(secret=b"p" * 32))
    with pytest.raises(ValueError, match="SPAN_REFERENCE_NOT_FOUND"):
        ground(candidate(setup[2], span_ids=[prior[2].span_ids[0]]), setup)
    outside = setup[1].sections[-1].span_ids[0]
    with pytest.raises(ValueError, match="EXTRACTION_SPAN_NOT_ALLOWED"):
        ground(candidate(setup[2], span_ids=[outside]), setup)


def test_stale_source_revision_rejected(document):
    setup = setup_job(document)
    changed = document("License\nAn Apache license is required.")
    with pytest.raises(ValueError, match="EXTRACTION_SOURCE_REVISION_MISMATCH"):
        ground(candidate(setup[2]), (changed, *setup[1:]))


def test_spans_preserve_source_order_and_individual_quotes(document):
    setup = setup_job(document, global_context_source("Ordinary detail line.\n" * 310))
    spans = sorted(
        setup[2].span_ids, key=lambda sid: setup[3].resolve(setup[0].id, sid).start_offset
    )
    result = ground(candidate(setup[2], span_ids=spans), setup)
    assert len(result.quotes) > 1
    assert all(quote in setup[0].text for quote in result.quotes)
    with pytest.raises(ValueError, match="EXTRACTION_SPAN_ORDER_INVALID"):
        ground(candidate(setup[2], span_ids=list(reversed(spans))), setup)
    with pytest.raises(ValidationError):
        candidate(setup[2], span_ids=[spans[0], spans[0]])


def test_third_candidate_and_non_json_array_rejected(document):
    from qualor.runtime.section_extraction import validate_section_payload

    item = candidate(setup_job(document)[2]).model_dump(mode="json")
    for claims in ([item, item, item], (item,)):
        with pytest.raises(ValidationError):
            validate_section_payload({"claims": claims})


@pytest.mark.parametrize("state,value", [("CANDIDATE", None), ("UNKNOWN", "MIT")])
def test_explicit_unknown_state_value_contract(document, state, value):
    with pytest.raises(ValidationError):
        candidate(setup_job(document)[2], state=state, proposed_value=value)


def test_unknown_is_not_semantic_support_even_with_high_confidence(document):
    setup = setup_job(document)
    result = ground(candidate(setup[2], state="UNKNOWN", proposed_value=None), setup)
    assert not result.semantic_context_complete
    assert result.candidate.confidence_class == "HIGH"
    assert "supported" not in result.model_dump()


def test_omitted_local_qualifier_is_retained_and_incomplete(document):
    setup = setup_job(document, "License\nAn MIT license is required only if awarded a prize.")
    result = ground(candidate(setup[2]), setup)
    assert not result.semantic_context_complete
    assert result.context.qualifiers == (setup[0].text,)
    complete = ground(candidate(setup[2], qualifier_span_ids=list(setup[2].span_ids)), setup)
    assert complete.semantic_context_complete


def test_remote_exception_retained_but_unrelated_condition_not_applied(document):
    setup = setup_job(
        document,
        "1 License\nAn MIT license is required, subject to Section 3.\n"
        "2 Notes\nVisitors may leave unless the doors are closed.\n"
        "3 Exemptions\nExcept invited exhibitors, entrants must license their work.",
    )
    result = ground(candidate(setup[2]), setup)
    assert not result.semantic_context_complete
    assert result.context.context_section_ids == (setup[1].sections[2].section_id,)
    assert result.context.exceptions == (
        "3 Exemptions\nExcept invited exhibitors, entrants must license their work.",
    )
    assert all(
        "doors" not in quote for quote in result.context.qualifiers + result.context.exceptions
    )
    independent = setup_job(
        document,
        "1 License\nAn MIT license is required.\n2 Notes\nVisitors may leave unless doors close.",
    )
    assert ground(candidate(independent[2]), independent).semantic_context_complete


def test_request_is_scoped_and_uses_existing_guard_name(document):
    from qualor.runtime.section_extraction import build_section_extraction_request

    source, index, job, registry = setup_job(
        document, "License\nAn MIT license is required.\n2 Notes\nPRIVATE UNRELATED BODY."
    )
    request = build_section_extraction_request(source, index, job, registry, max_output_tokens=1024)
    body = json.loads(request["messages"][0]["content"][0]["text"])
    assert body["allowed_categories"] == ["LICENSE"]
    assert body["section_id"] == job.section_id
    assert [span["span_id"] for span in body["EVIDENCE_SPANS"]] == list(job.span_ids)
    assert "PRIVATE UNRELATED BODY" not in json.dumps(request)
    assert (
        request["outputConfig"]["textFormat"]["structure"]["jsonSchema"]["name"]
        == "return_extracted_claims"
    )


def test_twelve_fitting_spans_are_retained_and_utf8_overflow_refused(document):
    from qualor.runtime.section_extraction import build_section_extraction_request

    fitting = setup_job(document, global_context_source("Ordinary detail line.\n" * 310))
    request = build_section_extraction_request(*fitting, max_output_tokens=1024)
    assert len(fitting[2].span_ids) == 12
    assert len(json.loads(request["messages"][0]["content"][0]["text"])["EVIDENCE_SPANS"]) == 12
    # Twelve capabilities still fit the span bound while exceeding the byte bound.
    wide = ("界" * 260) + "\n"
    oversized = setup_job(document, global_context_source(wide * 10, target=("界" * 260)))
    assert len(oversized[2].span_ids) == 12
    with pytest.raises(ValueError, match="EXTRACTION_CONTEXT_TOO_LARGE"):
        build_section_extraction_request(*oversized, max_output_tokens=1024)


def response(text, stop="end_turn"):
    return {
        "stopReason": stop,
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": 100, "outputTokens": 100, "totalTokens": 200},
    }


@pytest.mark.parametrize(
    "value,reason,decode,schema",
    [
        (response("{"), "JSON_DECODE_FAILED", "FAILED", "NOT_ATTEMPTED"),
        (
            response('{"claims": [{"quote": "invented"}]}'),
            "EXTRACTION_SCHEMA_REJECTED",
            "PASS",
            "FAILED",
        ),
        (
            response("{}", "max_tokens"),
            "EXTRACTION_OUTPUT_TRUNCATED",
            "NOT_ATTEMPTED",
            "NOT_ATTEMPTED",
        ),
        (
            RuntimeError("private provider detail"),
            "BEDROCK_PROVIDER_ERROR",
            "NOT_ATTEMPTED",
            "NOT_ATTEMPTED",
        ),
    ],
)
def test_shared_provider_receipts_and_no_retry(document, value, reason, decode, schema):
    class Client:
        calls = 0

        def converse(self, **request):
            self.calls += 1
            if isinstance(value, Exception):
                raise value
            return value

    client = Client()
    extractor = BedrockClaimExtractor(client)
    source, index, job, _ = setup_job(document, registry=extractor.span_registry)
    with pytest.raises(ValueError, match=reason):
        extractor.extract_section(source, index, job)
    assert client.calls == 1
    assert extractor.receipts[-1].json_decode_state == decode
    assert extractor.receipts[-1].schema_validation_state == schema


def test_extract_section_grounds_with_its_own_registry(document):
    class Client:
        def converse(self, **request):
            body = json.loads(request["messages"][0]["content"][0]["text"])
            assert body["source_id"] == source.id
            item = candidate(job).model_dump(mode="json")
            return response(json.dumps({"claims": [item]}))

    extractor = BedrockClaimExtractor(Client())
    source, index, job, _ = setup_job(document, registry=extractor.span_registry)
    result = extractor.extract_section(source, index, job)
    assert result[0].quotes == (source.text,)
    assert extractor.last_created_span_ids == job.span_ids
    assert extractor.last_selected_span_ids == job.span_ids


def test_clause_context_is_additive_bounded_and_preserves_exact_whitespace():
    from qualor.domain.evidence import ClauseContext

    context = dict(
        source_id="s",
        section_id="t",
        span_ids=["a"],
        qualifiers=[" exact "],
        exceptions=[],
        context_section_ids=[],
        context_complete=True,
    )
    assert ClauseContext(**context).qualifiers == (" exact ",)
    for updates in (
        {"span_ids": ["a", "a"]},
        {"span_ids": [str(i) for i in range(13)]},
        {"qualifiers": ["x" * 701]},
        {"context_section_ids": ["x"] * 13},
    ):
        with pytest.raises(ValidationError):
            ClauseContext(**(context | updates))


def test_truncated_source_retains_quotes_but_context_is_incomplete(document):
    from qualor.runtime.section_extraction import build_section_extraction_request

    source, index, job, registry = setup_job(document)
    source = source.model_copy(update={"truncated": True})
    grounded = ground(candidate(job), (source, index, job, registry))
    assert grounded.quotes == (source.text,)
    assert not grounded.context.context_complete
    assert not grounded.semantic_context_complete
    with pytest.raises(ValueError, match="EXTRACTION_CONTEXT_UNRESOLVED"):
        build_section_extraction_request(source, index, job, registry, max_output_tokens=1024)


def test_grounded_candidate_fixture_resolves_exact_substrings(grounded_candidate):
    result = grounded_candidate(
        Category.LICENSE,
        "MIT",
        "An MIT license is required.",
        qualifiers=("Only prize recipients must comply.",),
        exceptions=("Except invited exhibitors.",),
    )
    assert result.quotes == ("An MIT license is required.",)
    assert result.context.qualifiers == ("Only prize recipients must comply.",)
    assert result.context.exceptions == ("Except invited exhibitors.",)
    assert result.semantic_context_complete


def test_incomplete_or_missing_job_context_refused_before_client(document):
    class Client:
        calls = 0

        def converse(self, **request):
            self.calls += 1
            raise AssertionError("must not dispatch unsafe context")

    client = Client()
    extractor = BedrockClaimExtractor(client)
    source, index, job, _ = setup_job(
        document,
        "1 License\nAn MIT license is required, subject to Section 2.\n"
        "2 Conditions\nOnly prize recipients must comply.",
        registry=extractor.span_registry,
    )
    missing = job.model_copy(update={"context_section_ids": (), "span_ids": job.span_ids[:1]})
    with pytest.raises(ValueError, match="EXTRACTION_JOB_CONTEXT_MISMATCH"):
        extractor.extract_section(source, index, missing)
    incomplete = index.model_copy(
        update={
            "sections": (
                index.sections[0].model_copy(update={"context_complete": False}),
                *index.sections[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="EXTRACTION_CONTEXT_UNRESOLVED"):
        extractor.extract_section(source, incomplete, job)
    assert client.calls == 0


def test_split_conditional_phrase_is_not_lost_at_span_boundary(document):
    # The 700-character boundary lands between 'subject' and 'to'.
    setup = setup_job(document, "x" * 691 + " subject to approval.")
    result = ground(candidate(setup[2]), setup)
    # The forced cut may have severed the qualifier, so the boundary fails closed
    # rather than guessing which governing words landed in the neighbouring child.
    assert not result.semantic_context_complete
    assert not result.context.context_complete


def test_request_identifies_target_and_earlier_parent_in_source_order(document):
    from qualor.runtime.section_extraction import build_section_extraction_request

    source, index, job, registry = setup_job(document, "License\n" + "Exact license text. " * 45)
    parent, child = index.sections
    job = job.model_copy(
        update={
            "section_id": child.section_id,
            "context_section_ids": (parent.section_id,),
            "span_ids": (*child.span_ids, *parent.span_ids),
        }
    )
    request = build_section_extraction_request(source, index, job, registry, max_output_tokens=1024)
    body = json.loads(request["messages"][0]["content"][0]["text"])
    assert body["section_id"] == child.section_id
    assert [span["section_id"] for span in body["EVIDENCE_SPANS"]] == [
        parent.section_id,
        child.section_id,
    ]
    assert [span["span_id"] for span in body["EVIDENCE_SPANS"]] == [
        *parent.span_ids,
        *child.span_ids,
    ]


def test_index_cannot_hide_unrepresented_clause_text(document):
    from qualor.runtime.section_extraction import build_section_extraction_request

    source, index, job, registry = setup_job(document, "An MIT license is required, unless exempt.")
    span = registry.register_section(source, start_offset=0, end_offset=26)[0]
    index = index.model_copy(
        update={"sections": (index.sections[0].model_copy(update={"span_ids": (span.span_id,)}),)}
    )
    job = job.model_copy(update={"span_ids": (span.span_id,)})
    with pytest.raises(ValueError, match="EXTRACTION_JOB_SPAN_MISMATCH"):
        build_section_extraction_request(source, index, job, registry, max_output_tokens=1024)


def test_remote_governing_text_is_retained_without_condition_keywords(document):
    setup = setup_job(
        document,
        "1 License\nAn MIT license is required, subject to Section 2.\n"
        "2 Conditions\nEntrants need written authorization.",
    )
    result = ground(candidate(setup[2], qualifier_span_ids=[setup[2].span_ids[0]]), setup)
    assert not result.semantic_context_complete
    assert "2 Conditions\nEntrants need written authorization." in result.context.qualifiers


def _scheduled_license(index, heading):
    """Reach the requested section through real scheduler and ledger transitions."""

    ledger = CoverageLedger(index)
    scheduler = SectionScheduler(index, ledger, live_budget())
    target = next(section for section in index.sections if section.heading == heading)
    for step in range(24):
        job = scheduler.next_job(authority_revision=0, steps_remaining=24 - step, terminated=False)
        if isinstance(job, NoExtractionJob):
            return job
        if job.section_id == target.section_id and Category.LICENSE in job.categories:
            return job
        scheduler.begin(job)
        ledger.complete(
            job.section_id,
            {
                category: AcquisitionOutcome(
                    normalization_status="UNKNOWN",
                    supported_rule_ids=(),
                    conditional=False,
                    context_complete=False,
                    reason_code="CONTROLLED_UNKNOWN",
                )
                for category in job.categories
            },
            authority_revision=0,
        )
    raise AssertionError("Scheduler did not reach the target or a bounded terminal outcome")


def test_scheduled_numbered_license_requires_exact_parent_interpretation(document):
    source = document(
        "1. Project requirements\nThe following requirements apply only to teams.\n"
        "1.1 License\nAn MIT license is required."
    )
    registry = EvidenceSpanRegistry(secret=b"a" * 32)
    index = index_source(source, registry)
    parent, child = index.sections
    job = _scheduled_license(index, "1.1 License")
    assert isinstance(job, ExtractionJob)
    setup = source, index, job, registry
    item = candidate(job, category="LICENSE", span_ids=list(child.span_ids))
    omitted = ground(item, setup)
    assert not omitted.semantic_context_complete
    included = ground(item.model_copy(update={"qualifier_span_ids": parent.span_ids}), setup)
    assert included.semantic_context_complete
    assert omitted.quotes == included.quotes == ("1.1 License\nAn MIT license is required.",)
    assert included.context.context_section_ids == (parent.section_id,)
    assert included.context.qualifiers == (
        "1. Project requirements\nThe following requirements apply only to teams.",
    )


def test_scheduled_multilevel_license_retains_reference_and_isolates_sibling(document):
    source = document(
        "1. Project requirements\nThe following requirements apply only to teams.\n"
        "1.1 Entry requirements\nEntrants need written authorization.\n"
        "1.1.1 License\nAn MIT license is required, subject to Section 2.\n"
        "1.1.2 Visitor policy\nVisitors may enter only if accompanied.\n"
        "2. Exemptions\nExcept invited exhibitors, entrants must license their work."
    )
    registry = EvidenceSpanRegistry(secret=b"a" * 32)
    index = index_source(source, registry)
    ancestor, parent, child, sibling, reference = index.sections
    job = _scheduled_license(index, "1.1.1 License")
    assert isinstance(job, ExtractionJob)
    setup = source, index, job, registry
    item = candidate(
        job,
        category="LICENSE",
        span_ids=list(child.span_ids),
        qualifier_span_ids=[*ancestor.span_ids, *parent.span_ids, *child.span_ids],
    )
    omitted = ground(item, setup)
    assert not omitted.semantic_context_complete
    included = ground(item.model_copy(update={"exception_span_ids": reference.span_ids}), setup)
    assert included.semantic_context_complete
    assert (
        omitted.quotes
        == included.quotes
        == ("1.1.1 License\nAn MIT license is required, subject to Section 2.",)
    )
    assert included.context.context_section_ids == (
        ancestor.section_id,
        parent.section_id,
        reference.section_id,
    )
    assert included.context.exceptions == (
        "2. Exemptions\nExcept invited exhibitors, entrants must license their work.",
    )
    assert sibling.section_id not in included.context.context_section_ids
    assert not set(sibling.span_ids) & set(included.context.span_ids)
    assert all("Visitors" not in text for text in included.context.qualifiers)


def test_scheduled_license_cannot_bypass_unresolved_inherited_reference(document):
    source = document(
        "1. Project requirements\nThe following requirements apply only to teams.\n"
        "1.1 Entry requirements\nEntrants need authorization under Section 9.\n"
        "1.1.1 License\nAn MIT license is required."
    )
    registry = EvidenceSpanRegistry(secret=b"a" * 32)
    index = index_source(source, registry)
    outcome = _scheduled_license(index, "1.1.1 License")
    assert isinstance(outcome, NoExtractionJob)
    assert outcome.reason_code == "CONTEXT_UNRESOLVED"


def test_severed_qualifier_boundary_blocks_extraction_authority(document):
    """A forced cut must fail closed before any semantic support can be claimed."""

    from qualor.runtime.section_extraction import build_section_extraction_request

    source, index, job, registry = setup_job(document, "x" * 691 + " subject to approval.")
    target = next(s for s in index.sections if s.section_id == job.section_id)

    assert not target.context_complete
    with pytest.raises(ValueError, match="EXTRACTION_CONTEXT_UNRESOLVED"):
        build_section_extraction_request(source, index, job, registry, max_output_tokens=1024)
    assert not ground(candidate(job), (source, index, job, registry)).semantic_context_complete
