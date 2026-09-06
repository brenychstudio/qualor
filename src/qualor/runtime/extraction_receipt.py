"""Safe Converse envelope metadata; no response text or source content retained."""

import hashlib
from dataclasses import dataclass

STOP_FAILURES = {
    "max_tokens": "EXTRACTION_OUTPUT_TRUNCATED",
    "malformed_model_output": "BEDROCK_MALFORMED_MODEL_OUTPUT",
    "malformed_tool_use": "BEDROCK_MALFORMED_MODEL_OUTPUT",
    "content_filtered": "BEDROCK_CONTENT_FILTERED",
    "guardrail_intervened": "BEDROCK_GUARDRAIL_INTERVENED",
    "model_context_window_exceeded": "BEDROCK_CONTEXT_WINDOW_EXCEEDED",
}
KNOWN_STOPS = frozenset(STOP_FAILURES) | {"end_turn", "tool_use", "stop_sequence"}
KNOWN_BLOCKS = frozenset({"text", "reasoningContent", "toolUse", "guardContent"})


@dataclass(frozen=True)
class StructuredExtractionReceipt:
    stop_reason: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    content_block_count: int
    content_block_types: tuple[str, ...]
    response_text_bytes: int
    json_decode_state: str
    schema_validation_state: str
    model_id: str
    max_output_tokens: int
    latency_ms: int | None
    response_sha256: str | None


def _counter(value):
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def response_metadata(response: object, *, model_id: str, maximum: int):
    """Return a receipt and transient text blocks; unknown names are never echoed."""

    data = response if isinstance(response, dict) else {}
    stop = data.get("stopReason")
    stop = (
        stop
        if isinstance(stop, str) and stop in KNOWN_STOPS
        else ("UNAVAILABLE" if stop is None else "UNRECOGNIZED")
    )
    output = data.get("output")
    message = output.get("message") if isinstance(output, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    content = content if isinstance(content, list) else []
    types, texts = [], []
    for block in content:
        if not isinstance(block, dict) or len(block) != 1:
            types.append("INVALID")
            continue
        kind = next(iter(block))
        types.append(kind if kind in KNOWN_BLOCKS else "UNRECOGNIZED")
        if kind == "text" and isinstance(block[kind], str):
            texts.append(block[kind])
    usage = data.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    metrics = data.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    raw = "".join(texts).encode("utf-8")
    receipt = StructuredExtractionReceipt(
        stop_reason=stop,
        input_tokens=_counter(usage.get("inputTokens")),
        output_tokens=_counter(usage.get("outputTokens")),
        total_tokens=_counter(usage.get("totalTokens")),
        content_block_count=len(content),
        content_block_types=tuple(dict.fromkeys(types))[:16],
        response_text_bytes=len(raw),
        json_decode_state="NOT_ATTEMPTED",
        schema_validation_state="NOT_ATTEMPTED",
        model_id=model_id,
        max_output_tokens=maximum,
        latency_ms=_counter(metrics.get("latencyMs")),
        response_sha256=hashlib.sha256(raw).hexdigest() if texts else None,
    )
    return receipt, texts
