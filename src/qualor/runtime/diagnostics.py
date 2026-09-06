"""Bounded boundary observations; never serialize exception messages or input values."""

from typing import Annotated, Literal

from pydantic import Field, ValidationError

from qualor.domain.base import Contract

Component = Literal[
    "orchestration",
    "search_web",
    "fetch_official_source",
    "record_evidence",
    "evaluate_current_state",
    "strands_model",
    "extraction",
    "claim_validation",
    "evidence_admission",
    "unknown_tool",
]
Event = Literal[
    "TOOL_REQUESTED",
    "TOOL_RESULT",
    "SOURCE_FETCH_RESULT",
    "EXTRACTION_REQUESTED",
    "EXTRACTION_RESULT",
    "CLAIM_VALIDATION_RESULT",
    "EVIDENCE_ADMISSION_ATTEMPT",
    "EVIDENCE_ADMISSION_RESULT",
]
FIELDS = frozenset(
    {
        "query",
        "include_domains",
        "url",
        "candidate_id",
        "budget",
        "current_cost_usd",
        "attempted_cost_usd",
        "remaining_cost_usd",
        "projected_cost_usd",
        "focus",
        "claims",
        "source_id",
        "source_url",
        "field",
        "value",
        "excerpt",
        "state",
        "confidence",
        "not_applicable_reason",
        "status",
        "reason_code",
        "recoverable",
        "missing_fields",
        "safe_summary",
        "component",
        "observations",
        "evidence_id",
        "text",
        "authority",
        "retrieved_at",
        "text_truncated",
        "mode",
        "results",
        "termination_reason",
        "recommendation",
        "best_project",
        "candidates",
        "validation_issues",
    }
)


def shape(value: object, depth: int = 0) -> str:
    if isinstance(value, dict):
        if depth >= 2:
            return "object"
        parts = [
            (k if k in FIELDS else "UNRECOGNIZED_FIELD") + ":" + shape(v, depth + 1)
            for k, v in list(value.items())[:16]
        ]
        return ("object{" + ",".join(parts) + "}")[:500]
    if isinstance(value, (list, tuple)):
        return "array[" + (shape(value[0], depth + 1) if value else "empty") + "]"
    return {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        type(None): "null",
    }.get(type(value), "object")


class Rejection(Contract):
    status: Literal["REJECTED"] = "REJECTED"
    reason_code: str = Field(max_length=80)
    component: Component
    safe_summary: str = Field(max_length=250)
    recoverable: Literal["YES", "NO"]
    missing_fields: Annotated[tuple[str, ...], Field(max_length=16)] = ()
    validation_issues: Annotated[tuple[str, ...], Field(max_length=16)] = ()


class BoundaryEvent(Contract):
    sequence: int = Field(ge=1)
    event: Event
    component: Component
    status: Literal["REQUESTED", "ACCEPTED", "REJECTED", "OBSERVED"]
    reason_code: str = Field(max_length=80)
    safe_summary: str = Field(max_length=250)
    recoverable: Literal["YES", "NO"] = "NO"
    missing_fields: Annotated[tuple[str, ...], Field(max_length=16)] = ()
    validation_issues: Annotated[tuple[str, ...], Field(max_length=16)] = ()
    input_shape: str = Field(default="", max_length=500)
    output_shape: str = Field(default="", max_length=500)
    source_ids: Annotated[tuple[str, ...], Field(max_length=40)] = ()
    requested_url_sanitized: str | None = Field(default=None, max_length=500)
    candidate_url_count: int = Field(default=0, ge=0, le=25)
    candidate_domains: Annotated[tuple[str, ...], Field(max_length=10)] = ()
    closest_candidate_urls_sanitized: Annotated[tuple[str, ...], Field(max_length=5)] = ()
    budget_current_cost_usd: str | None = Field(default=None, max_length=40)
    budget_attempted_cost_usd: str | None = Field(default=None, max_length=40)
    budget_remaining_cost_usd: str | None = Field(default=None, max_length=40)
    budget_projected_cost_usd: str | None = Field(default=None, max_length=40)


CODEBOOK = {
    "MODEL_CALL_FAILED": (
        "The bounded model invocation failed; raw SDK error text is withheld.",
        "NO",
    ),
    "CLAIM_BATCH_LIMIT": ("At most 12 claims may be sent in one tool call.", "YES"),
    "CLAIM_LIMIT": ("The bounded run claim inventory is full; stop recording claims.", "NO"),
    "UNSUPPORTED_SOURCE_ENCODING": (
        "The HTTP response encoding is unsupported; no decoding fallback.",
        "NO",
    ),
    "SOURCE_SIZE_LIMIT": ("Source response exceeded the maximum byte size.", "NO"),
    "CLAIM_FIELD_UNSUPPORTED": (
        "Use a normalized field from the strict ExtractedClaim schema.",
        "YES",
    ),
    "EVIDENCE_MODEL_VALIDATION_FAILED": (
        "EvidenceRecord construction rejected the validated inputs; inspect admission.",
        "NO",
    ),
    "URL_NOT_DISCOVERED": (
        "Use an exact URL returned by search_web; search for the missing URL.",
        "YES",
    ),
    "CANDIDATE_NOT_FOUND": (
        "Use one current-run candidate_id returned by search_web; no new search is required.",
        "YES",
    ),
    "CLAIM_SOURCE_REFERENCE_MISSING": (
        "Fetch the source first and use its returned ID and URL.",
        "YES",
    ),
    "CLAIM_EXCERPT_MISSING": (
        "Provide an exact excerpt present in the fetched source window.",
        "YES",
    ),
    "CLAIM_VALUE_UNSUPPORTED": (
        "Use only values supported by the excerpt, or retain UNKNOWN.",
        "YES",
    ),
    "TOOL_ARGUMENT_VALIDATION_FAILED": (
        "Correct the listed fields using the strict tool schema.",
        "YES",
    ),
    "EXTRACTION_SCHEMA_REJECTED": (
        "Use the ExtractedClaim schema; do not supply a verdict or EvidenceRecord.",
        "YES",
    ),
    "TOOL_RESULT_PROTOCOL_ERROR": (
        "Tool execution failed outside the validated handoff; stop or inspect.",
        "NO",
    ),
    "TOOL_NOT_AVAILABLE": (
        "Use only search_web, fetch_official_source, record_evidence or evaluate_current_state.",
        "YES",
    ),
    "FETCH_CONTENT_TYPE_REJECTED": ("Select an authorized HTML, JSON or plain text source.", "YES"),
    "FETCH_BODY_EMPTY": (
        "No usable source text was returned; select another discovered official source.",
        "YES",
    ),
    "SOURCE_HTTP_403": (
        "Source denied HTTP access. Select another discovered authorized official source.",
        "YES",
    ),
    "SOURCE_HTTP_404": ("Source was not found. Search for a current official URL.", "YES"),
    "SOURCE_HTTP_429": ("Source rate limited the request; no automatic retry.", "NO"),
    "SOURCE_URL_NOT_AUTHORIZED": (
        "Use HTTPS on an operator-approved host with no private destination.",
        "YES",
    ),
    "SOURCE_ADDRESS_NOT_PUBLIC": (
        "Source resolved to a prohibited network; do not fetch it.",
        "NO",
    ),
    "SOURCE_REDIRECT_LIMIT": (
        "Source redirect chain was rejected; select another official source.",
        "YES",
    ),
    "SOURCE_SIZE_OR_TIME_LIMIT": ("Source exceeded its bounded size or time allowance.", "NO"),
    "BUDGET_EXHAUSTED": ("No remaining authorized call or cost allowance. Stop.", "NO"),
    "TOOL_OR_CLAIM_REJECTED": (
        "Operation failed; raw service error text is intentionally withheld.",
        "NO",
    ),
}
ALIASES = {
    "CLAIM_REQUIRES_FETCHED_SOURCE": "CLAIM_SOURCE_REFERENCE_MISSING",
    "EXCERPT_NOT_IN_FETCHED_SOURCE": "CLAIM_EXCERPT_MISSING",
    "NORMALIZED_VALUE_NOT_SUPPORTED_BY_QUOTE": "CLAIM_VALUE_UNSUPPORTED",
    "NA_REASON_NOT_SUPPORTED": "CLAIM_VALUE_UNSUPPORTED",
    "UNSUPPORTED_SOURCE_TYPE": "FETCH_CONTENT_TYPE_REJECTED",
}


def reject(exc: Exception, *, component: Component, code: str | None = None) -> Rejection:
    chain, current = [], exc
    while current is not None and id(current) not in {id(e) for e in chain}:
        chain.append(current)
        current = current.__cause__
    validation = next((e for e in chain if isinstance(e, ValidationError)), None)
    missing, issues = [], []
    if validation:
        for error in validation.errors(include_input=False, include_context=False):
            location = ".".join(
                str(p) if isinstance(p, int) or p in FIELDS else "UNRECOGNIZED_FIELD"
                for p in error["loc"]
            )[:150]
            error_type = (
                error["type"]
                if error["type"]
                in {
                    "missing",
                    "literal_error",
                    "extra_forbidden",
                    "string_type",
                    "list_type",
                    "tuple_type",
                    "string_too_short",
                    "string_too_long",
                    "too_long",
                    "too_short",
                    "model_type",
                    "value_error",
                    "int_type",
                    "bool_type",
                    "string_pattern_mismatch",
                }
                else "OTHER_VALIDATION_ERROR"
            )
            issues.append(location + ":" + error_type)
            if error["type"] == "missing":
                missing.append(location)
        code = code or (
            "EXTRACTION_SCHEMA_REJECTED"
            if component == "extraction"
            else "TOOL_ARGUMENT_VALIDATION_FAILED"
        )
        if validation.title == "SourceDocument" and any(
            e["loc"] == ("text",) and e["type"] == "string_too_short"
            for e in validation.errors(include_input=False, include_context=False)
        ):
            code = "FETCH_BODY_EMPTY"
        elif validation.title == "EvidenceRecord":
            code = "EVIDENCE_MODEL_VALIDATION_FAILED"
        elif any(
            e["loc"][-1:] == ("field",) and e["type"] == "literal_error"
            for e in validation.errors(include_input=False, include_context=False)
        ):
            code = "CLAIM_FIELD_UNSUPPORTED"
    text = str(exc)
    code = code or ALIASES.get(text, text)
    if (
        code.startswith("SOURCE_HTTP_")
        and len(code) == len("SOURCE_HTTP_") + 3
        and code[-3:].isdigit()
        and 100 <= int(code[-3:]) <= 599
    ):
        return Rejection(
            reason_code=code,
            component=component,
            safe_summary="Source HTTP status " + code[-3:] + "; no automatic retry.",
            recoverable="YES" if code in {"SOURCE_HTTP_403", "SOURCE_HTTP_404"} else "NO",
        )
    if code not in CODEBOOK:
        code = "TOOL_OR_CLAIM_REJECTED"
    summary, recoverable = CODEBOOK[code]
    return Rejection(
        reason_code=code,
        component=component,
        safe_summary=summary,
        recoverable=recoverable,
        missing_fields=tuple(missing[:16]),
        validation_issues=tuple(issues[:16]),
    )
