"""Hash-bound archived source input for offline canonical-compiler tests only."""

import hashlib
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from urllib.parse import urlsplit

from strands.models import BedrockModel

from qualor.decisions.fixture import ProjectDecisionInput
from qualor.domain.enums import Provenance
from qualor.domain.profiles import FounderProfile, ProjectProfile
from qualor.effort import EffortAssumptions
from qualor.runtime.run_models import StudioInput
from qualor.runtime.sources import SourceDocument, canonical_source_text

ARCHIVE_SOURCE_ID = "SRC-OFFICIAL-RULES"
ARCHIVE_RAW_ARTIFACT = "official-rules.raw"
ARCHIVE_TIMESTAMP = "2026-09-12T11:25:52Z"
ARCHIVE_SHA256 = "e3f7640c0bd1e78e3858d7d5a2dfb78bb560cac9b7982c29c5e57796116794a5"
_EXTERNAL_IO_DENIED = False


class ArchiveInputError(ValueError):
    """Bounded, non-sensitive failure from the offline archive authority boundary."""


@dataclass(frozen=True)
class ArchivedInput:
    directory: Path
    source: SourceDocument

    @property
    def evaluation_clock(self) -> datetime:
        return self.source.retrieved_at


@dataclass(frozen=True)
class ArchivedCompilerReport:
    """Safe, immutable observations from the archive-bound compiler acceptance path."""

    source_hash: str
    indexed_sections: int
    attempted_pairs: tuple[tuple[str, str, str], ...]
    reached_categories: tuple[str, ...]
    section_results: tuple[object, ...]
    raw_section_results: tuple[object, ...]
    effective_section_results: tuple[object, ...]
    coverage_states: MappingProxyType
    result: object
    receipts: tuple[object, ...]
    request_sequence: tuple[MappingProxyType, ...]
    gate_values: MappingProxyType


def _fail(code: str) -> None:
    raise ArchiveInputError(code)


def _deny_audited_external_io(event: str, _args: tuple[object, ...]) -> None:
    if _EXTERNAL_IO_DENIED and event in {
        "socket.connect",
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.gethostbyname_ex",
        "socket.getnameinfo",
    }:
        _fail("ARCHIVE_EXTERNAL_IO_DENIED")


sys.addaudithook(_deny_audited_external_io)


def _contained(root: Path, path: Path, *, missing_code: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail(missing_code)
    try:
        resolved.relative_to(root)
    except ValueError:
        _fail("ARCHIVE_SYMLINK_ESCAPE")
    return resolved


def _archive_root(directory: Path) -> Path:
    try:
        if not directory.is_dir():
            _fail("ARCHIVE_DIRECTORY_INVALID")
        return directory.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("ARCHIVE_DIRECTORY_INVALID")


def _rules_entry(root: Path) -> dict[str, object]:
    manifest_path = _contained(
        root, root / "source-manifest.json", missing_code="ARCHIVE_MANIFEST_MISSING"
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = manifest[ARCHIVE_SOURCE_ID]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        _fail("ARCHIVE_MANIFEST_INVALID")
    if not isinstance(entry, dict) or entry.get("SOURCE_ID") != ARCHIVE_SOURCE_ID:
        _fail("ARCHIVE_SOURCE_ID_INVALID")
    return entry


def _timestamp(entry: dict[str, object]) -> datetime:
    if entry.get("RETRIEVED_AT_UTC") != ARCHIVE_TIMESTAMP:
        _fail("ARCHIVE_TIMESTAMP_INVALID")
    return datetime.fromisoformat(ARCHIVE_TIMESTAMP.replace("Z", "+00:00")).astimezone(UTC)


def load_archived_rules(directory: Path) -> SourceDocument:
    """Load only the hash-bound official-rules archive; never fetch or fall back."""

    root = _archive_root(Path(directory))
    entry = _rules_entry(root)
    if entry.get("RAW_ARTIFACT") != ARCHIVE_RAW_ARTIFACT:
        _fail("ARCHIVE_RAW_ARTIFACT_INVALID")
    retrieved_at = _timestamp(entry)
    if entry.get("CONTENT_SHA256") != ARCHIVE_SHA256:
        _fail("ARCHIVE_MANIFEST_HASH_INVALID")
    if entry.get("SOURCE_AUTHORITY") != "OFFICIAL_RULES":
        _fail("ARCHIVE_AUTHORITY_INVALID")
    url = entry.get("CANONICAL_SOURCE")
    try:
        host = urlsplit(url).hostname if isinstance(url, str) else None
    except ValueError:
        host = None
    if not host:
        _fail("ARCHIVE_URL_INVALID")

    raw_path = _contained(
        root, root / ARCHIVE_RAW_ARTIFACT, missing_code="ARCHIVE_RAW_ARTIFACT_MISSING"
    )
    try:
        raw = raw_path.read_bytes()
    except OSError:
        _fail("ARCHIVE_RAW_ARTIFACT_MISSING")
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        _fail("ARCHIVE_RAW_HASH_MISMATCH")
    try:
        text, truncated = canonical_source_text(raw, "text/html")
        if not isinstance(text, str) or not text or type(truncated) is not bool:
            _fail("ARCHIVE_SOURCE_PARSE_INVALID")
        return SourceDocument(
            id=ARCHIVE_SOURCE_ID,
            original_url=url,
            final_url=url,
            retrieved_at=retrieved_at,
            content_hash=ARCHIVE_SHA256,
            authority="OFFICIAL_RULES",
            content_type="text/html",
            text=text,
            truncated=truncated,
        )
    except ArchiveInputError:
        raise
    except Exception:
        _fail("ARCHIVE_SOURCE_PARSE_INVALID")


def deny_external_io(monkeypatch) -> None:
    """Block real AWS and socket connection entry points in archive-bound tests."""

    import boto3

    def denied(*_args, **_kwargs):
        _fail("ARCHIVE_EXTERNAL_IO_DENIED")

    class DeniedSocket:
        def __init__(self, *_args, **_kwargs):
            pass

        def connect(self, *_args, **_kwargs):
            denied()

        def connect_ex(self, *_args, **_kwargs):
            denied()

    monkeypatch.setattr(sys.modules[__name__], "_EXTERNAL_IO_DENIED", True)
    monkeypatch.setattr(boto3.session.Session, "__init__", denied)
    monkeypatch.setattr(boto3.session.Session, "client", denied)
    monkeypatch.setattr(boto3, "Session", denied)
    monkeypatch.setattr(boto3, "client", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyaddr", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    monkeypatch.setattr(socket, "gethostbyname_ex", denied)
    monkeypatch.setattr(socket, "getnameinfo", denied)
    monkeypatch.setattr(socket, "socket", DeniedSocket)


def archived_studio_input() -> StudioInput:
    """Return synthetic, source-independent facts at the archive's fixed observation instant."""

    import os

    selected = os.environ.get("QUALOR_ARCHIVE_DIR")
    if not selected:
        _fail("ARCHIVE_DIRECTORY_INVALID")
    archive = ArchivedInput(directory=Path(selected), source=load_archived_rules(Path(selected)))
    metadata = {
        "schema_version": "1",
        "version": 1,
        "created_at": archive.evaluation_clock,
        "updated_at": archive.evaluation_clock,
        "provenance": Provenance.UNKNOWN,
    }
    host = urlsplit(archive.source.final_url).hostname
    if host is None:
        _fail("ARCHIVE_URL_INVALID")
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal="Evaluate controlled archived official-source rules",
        allowed_hosts=(host,),
        founder=FounderProfile(id="archived-controlled-founder", **metadata),
        projects=(
            ProjectDecisionInput(
                project=ProjectProfile(
                    id="archived-controlled-project",
                    name="Controlled compiler project",
                    **metadata,
                ),
                effort=EffortAssumptions(items=()),
            ),
        ),
    )


_SUBMISSION_PERIOD_READING = re.compile(
    r"(?P<opening>.+?)\s[–—-]\s(?P<closing>.+?)"
    r"\s*\(\s*[“”\"]?Submission Period[“”\"]?\s*\)\.?",
    re.IGNORECASE,
)


def _submission_period_reading(target_spans):
    """Read a self-defined submission range from admitted target capabilities only.

    Returns the capabilities that carry it and the two exact source endpoint
    strings, or None. No rule, value normalization, or verdict is produced here.
    """

    for position, span in enumerate(target_spans):
        match = _SUBMISSION_PERIOD_READING.fullmatch(span["exact_text"].strip())
        if match is None:
            continue
        selected = [
            item["span_id"]
            for item in target_spans[:position]
            if item["exact_text"].strip().casefold() == "submission period:"
        ]
        return (*selected, span["span_id"]), (match["opening"], match["closing"])
    return None


class ControlledCandidateClient:
    """In-memory Bedrock transport that can return only run-issued section proposals."""

    def __init__(self, official_url: str):
        self.official_url = official_url
        self.requests: list[dict] = []
        self.planner_actions: list[str] = []
        self.meta = SimpleNamespace(region_name="us-east-1")

    def converse(self, **request):
        self.requests.append(request)
        if "outputConfig" in request:
            return self._section_response(request)
        return self._planner_response(request)

    def _planner_response(self, request):
        observations = [
            json.loads(item["text"])
            for message in request.get("messages", ())
            for block in message.get("content", ())
            if isinstance(block, dict) and "toolResult" in block
            for item in block["toolResult"].get("content", ())
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if not observations:
            action, payload = "search_web", {"query": "official hackathon rules"}
        elif "results" in observations[-1]:
            action, payload = (
                "fetch_official_source",
                {"candidate_id": observations[-1]["results"][0]["candidate_id"]},
            )
        else:
            raise RuntimeError("CONTROLLED_PLANNER_OBSERVATION_UNSUPPORTED")
        self.planner_actions.append(action)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": f"controlled_{len(self.requests)}",
                                "name": action,
                                "input": payload,
                            }
                        }
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 10, "outputTokens": 10},
            "metrics": {"latencyMs": 1},
        }

    def _section_response(self, request):
        payload = json.loads(request["messages"][0]["content"][0]["text"])
        spans = payload["EVIDENCE_SPANS"]
        target = next(
            item for item in spans if item["section_id"] == payload["section_id"]
        )
        qualifier_ids = tuple(
            item["span_id"]
            for item in spans
            if re.search(
                r"\b(?:if|only|provided(?:\s+that)?|subject\s+to|conditional|"
                r"conditioned|pursuant\s+to|as\s+long\s+as|depending|contingent|"
                r"must\s+not|may\s+not|not|neither|without)\b",
                item["exact_text"],
                re.IGNORECASE,
            )
        )
        exception_ids = tuple(
            item["span_id"]
            for item in spans
            if re.search(
                r"\b(?:unless|except|excluding|exempt|exemption)\b",
                item["exact_text"],
                re.IGNORECASE,
            )
        )
        interpreted = {}
        if "DEADLINE" in payload["allowed_categories"]:
            reading = _submission_period_reading(
                [item for item in spans if item["section_id"] == payload["section_id"]]
            )
            if reading is not None:
                selected, endpoints = reading
                interpreted["DEADLINE"] = {
                    "category": "DEADLINE",
                    "proposed_value": list(endpoints),
                    "source_id": payload["source_id"],
                    "section_id": payload["section_id"],
                    "span_ids": list(selected),
                    "qualifier_span_ids": list(qualifier_ids),
                    "exception_span_ids": list(exception_ids),
                    "confidence_class": "HIGH",
                    "state": "CANDIDATE",
                }
        claims = [
            interpreted.get(category)
            or {
                "category": category,
                "proposed_value": None,
                "source_id": payload["source_id"],
                "section_id": payload["section_id"],
                "span_ids": [target["span_id"]],
                "qualifier_span_ids": list(qualifier_ids),
                "exception_span_ids": list(exception_ids),
                "confidence_class": "UNKNOWN",
                "state": "UNKNOWN",
            }
            for category in payload["allowed_categories"]
        ]
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": json.dumps({"claims": claims})}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 10},
            "metrics": {"latencyMs": 1},
        }


class _ControlledBotoSession:
    """Minimal session surface required by Strands; no credentials or SDK discovery."""

    region_name = "us-east-1"

    def __init__(self, client):
        self._client = client

    def client(self, **_kwargs):
        return self._client


def _safe_request_metadata(request: dict) -> MappingProxyType:
    from qualor.runtime.agent import model_request_metrics

    metrics = model_request_metrics(request)
    metadata = {
        "request_kind": metrics["request_kind"],
        "request_bytes": metrics["request_bytes"],
        "message_count": metrics["message_count"],
        "tool_result_bytes": metrics["tool_result_bytes"],
        "fetched_source_bytes": metrics["fetched_source_bytes"],
        "isolated_source_bytes": metrics["isolated_source_bytes"],
        "model_id": request.get("modelId"),
        "max_tokens": request.get("inferenceConfig", {}).get("maxTokens"),
        "temperature": request.get("inferenceConfig", {}).get("temperature"),
        "streaming": False,
        "budget_blocked": False,
    }
    if metrics["request_kind"] == "EXTRACTION":
        payload = json.loads(request["messages"][0]["content"][0]["text"])
        metadata.update(
            {
                "source_id": payload["source_id"],
                "section_id": payload["section_id"],
                "categories": tuple(payload["allowed_categories"]),
            }
        )
    return MappingProxyType(metadata)


def _rule_nodes(rule):
    """Walk one compiled expression tree."""

    yield rule
    for child in rule.children:
        yield from _rule_nodes(child)


def _executable_rule_count(results) -> int:
    """Count supported expressions the existing evaluator can actually resolve."""

    return sum(
        1
        for result in results
        for rule in result.rules
        for node in _rule_nodes(rule)
        if node.supported and node.subject_reference is not None and node.operands
    )


def _coverage_guarded_supported_claims(raw_results, effective_results) -> int:
    """Count supported observations retained beneath a non-supported coverage guard."""

    guards = tuple(
        rule
        for result in effective_results
        if "CATEGORY_COVERAGE_INCOMPLETE" in result.reason_codes
        for rule in result.rules
        if not rule.supported
    )
    guarded_children = {
        (guard.rule_type, child.id) for guard in guards for child in guard.children
    }
    return sum(
        1
        for result in raw_results
        if result.normalization_status == "SUPPORTED"
        and result.rules
        and all((result.category, rule.id) in guarded_children for rule in result.rules)
    )


def _unknown_profile_fact_count(profile) -> int:
    return sum(
        getattr(value, "provenance", None) != Provenance.UNKNOWN
        for _field, value in profile
        if hasattr(value, "provenance")
    )


def run_archived_compiler(directory: Path, *, sink=None) -> ArchivedCompilerReport:
    """Run the ordinary LIVE compiler shapes over the verified archive with no external I/O."""

    if os.environ.get("QUALOR_REQUIRE_ARCHIVE") != "1":
        _fail("ARCHIVE_REQUIRED")
    archive = ArchivedInput(directory=Path(directory), source=load_archived_rules(Path(directory)))
    raw = (archive.directory / ARCHIVE_RAW_ARTIFACT).read_bytes()

    from qualor.runtime.agent import BudgetedBedrockClient, run_agent
    from qualor.runtime.budget import BudgetLimitExceeded
    from qualor.runtime.extraction import MODEL_ID, BedrockClaimExtractor
    from qualor.runtime.live_cli import live_budget
    from qualor.runtime.loop import OpportunityRun
    from qualor.runtime.search import AgentCoreSearchProvider
    from qualor.runtime.sources import OfficialSourceFetcher

    class SearchTransport:
        def __init__(self):
            self.calls = []

        def rpc(self, method, params):
            self.calls.append((method, params))
            if method == "tools/list":
                return {
                    "tools": [
                        {
                            "name": "search",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "maxResults": {"type": "integer"},
                                    "filters": {
                                        "type": "object",
                                        "properties": {
                                            "domainFilter": {
                                                "type": "object",
                                                "properties": {"include": {"type": "array"}},
                                            }
                                        },
                                    },
                                },
                            },
                        }
                    ]
                }
            if method != "tools/call":
                raise RuntimeError("CONTROLLED_SEARCH_METHOD_UNSUPPORTED")
            return {
                "structuredContent": {
                    "results": [
                        {
                            "url": archive.source.final_url,
                            "title": "Archived official rules",
                            "text": "Offline archive discovery hint",
                        }
                    ]
                }
            }

    class ArchiveClock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = archive.evaluation_clock
            return value if tz is None else value.astimezone(tz)

    transport = SearchTransport()
    budget = live_budget()
    controlled = ControlledCandidateClient(archive.source.final_url)
    client = BudgetedBedrockClient(controlled, budget)
    request_sequence: list[MappingProxyType] = []
    original_converse = client.converse

    def observed_converse(**request):
        metadata = _safe_request_metadata(request)
        request_sequence.append(metadata)
        try:
            return original_converse(**request)
        except BudgetLimitExceeded:
            request_sequence[-1] = MappingProxyType({**metadata, "budget_blocked": True})
            raise

    client.converse = observed_converse
    model = BedrockModel(
        boto_session=_ControlledBotoSession(controlled),
        model_id=MODEL_ID,
        temperature=0,
        max_tokens=budget.policy.model_max_output_tokens,
        streaming=False,
    )
    model.client = client
    inputs = archived_studio_input()
    from qualor.runtime import sources as source_module

    original_datetime = source_module.datetime
    source_module.datetime = ArchiveClock
    try:
        run = OpportunityRun(
            inputs,
            mode="LIVE",
            budget=budget,
            search=AgentCoreSearchProvider(mode="LIVE", transport=transport, budget=budget),
            fetcher=OfficialSourceFetcher(
                mode="LIVE",
                allowed_hosts=inputs.allowed_hosts,
                budget=budget,
                resolver=lambda _host: ("93.184.216.34",),
                request=lambda _url, _address: (200, {"content-type": "text/html"}, raw),
            ),
            extractor=BedrockClaimExtractor(
                client, max_output_tokens=budget.policy.extraction_max_output_tokens
            ),
            sink=sink,
        )
        result, _metrics = run_agent(run, model=model)
    finally:
        source_module.datetime = original_datetime

    from qualor.domain.enums import Category
    from qualor.runtime.canonical_compilation import compile_section_authority

    index = run.section_acquisition.index
    ledger = run.section_acquisition.ledger
    # The compiler's retained observations, before the coverage guard is applied.
    raw_section_results = tuple(run.section_acquisition._observations)
    # The authority actually admitted for deterministic evaluation.
    section_results = tuple(run.section_results)
    effective_section_results = section_results
    coverage_states = MappingProxyType(
        {category.value: ledger.state(category).value for category in Category}
    )
    deadline_relevant = tuple(
        section
        for section in index.sections
        if not section.candidate_categories or Category.DEADLINE in section.candidate_categories
    )
    deadline_attempted = sum(
        (index.source_revision, section.section_id, Category.DEADLINE) in ledger.attempts
        for section in deadline_relevant
    )
    evidence = tuple(record for item in section_results for record in item.evidence)
    rules = tuple(rule for item in section_results for rule in item.rules)
    contexts = tuple(
        record.clause_context for record in evidence if record.clause_context is not None
    )
    qualifier_or_exception_drops = sum(
        excerpt not in {record.supporting_excerpt for record in evidence}
        for context in contexts
        for excerpt in (*context.qualifiers, *context.exceptions)
    )
    founder_facts = _unknown_profile_fact_count(result.bundle.decision_input.founder)
    project_facts = sum(
        _unknown_profile_fact_count(item.project)
        for item in result.bundle.decision_input.projects
    )
    attempts = tuple(
        sorted(
            (revision, section_id, category.value)
            for revision, section_id, category in ledger.attempts
        )
    )
    source_evidence_ids = {record.id for record in evidence}
    extraction_requests = [
        item for item in request_sequence if item["request_kind"] == "EXTRACTION"
    ]
    gate_values = MappingProxyType(
        {
            "DEFAULT_9KB_WINDOW_ONLY": bool(extraction_requests)
            and all(item["isolated_source_bytes"] == 9 * 1024 for item in extraction_requests),
            "REPEATED_IDENTICAL_WINDOW": len(
                {(item["section_id"], item["categories"]) for item in extraction_requests}
            )
            != len(extraction_requests),
            "duplicate_section_category_attempts": len(attempts) - len(set(attempts)),
            "extraction_after_exhaustion": sum(
                item["budget_blocked"] for item in extraction_requests
            ),
            "planner_rediscovery_calls": sum(
                action not in {"search_web", "fetch_official_source"}
                for action in controlled.planner_actions
            ),
            "sourceless_rules": sum(
                not rule.evidence_ids or not set(rule.evidence_ids) <= source_evidence_ids
                for rule in rules
            ),
            "decision_derived_from_canonical_authority": bool(section_results)
            and result.bundle.decision_input.evidence == tuple(
                result.bundle.evidence
            ),
            "unresolved_remains_unresolved": any(
                item.normalization_status in {"UNKNOWN", "AMBIGUOUS", "UNSUPPORTED"}
                for item in section_results
            ),
            "quote_fabrication": sum(
                record.supporting_excerpt not in archive.source.text for record in evidence
            ),
            "qualifier_or_exception_drops": qualifier_or_exception_drops,
            "owner_facts_inferred_from_rules": founder_facts,
            "project_facts_inferred_from_rules": project_facts,
            "dispatched_model_requests": len(controlled.requests),
            "model_cost_cap_usd": str(budget.policy.cost_cap_usd),
            "max_steps": run.max_steps,
            # Compiler-level authority: what the source actually yielded.
            "RAW_AUTHORITATIVE_CANONICAL_FACTS": compile_section_authority(
                raw_section_results
            ).supported_claim_count,
            "RAW_EXECUTABLE_RULES": _executable_rule_count(raw_section_results),
            # Eligibility-effective authority: what survives the coverage guard.
            "EFFECTIVE_AUTHORITATIVE_CANONICAL_FACTS": compile_section_authority(
                effective_section_results
            ).supported_claim_count,
            "COVERAGE_GUARDED_SUPPORTED_CLAIMS": _coverage_guarded_supported_claims(
                raw_section_results, effective_section_results
            ),
            "DEADLINE_RELEVANT_SECTIONS": len(deadline_relevant),
            "DEADLINE_ATTEMPTED_RELEVANT": deadline_attempted,
            "DEADLINE_RELEVANT_UNATTEMPTED_REMAINS": len(deadline_relevant) - deadline_attempted,
        }
    )
    # Task 11 accepts the canonical compiler, so its headline counts are the raw view.
    gate_values = MappingProxyType(
        {
            **gate_values,
            "AUTHORITATIVE_CANONICAL_FACTS": gate_values["RAW_AUTHORITATIVE_CANONICAL_FACTS"],
            "EXECUTABLE_RULES": gate_values["RAW_EXECUTABLE_RULES"],
        }
    )
    return ArchivedCompilerReport(
        source_hash=archive.source.content_hash,
        indexed_sections=len(index.sections),
        attempted_pairs=attempts,
        reached_categories=tuple(sorted({item.category.value for item in section_results})),
        section_results=section_results,
        raw_section_results=raw_section_results,
        effective_section_results=effective_section_results,
        coverage_states=coverage_states,
        result=result,
        receipts=tuple(result.model_receipts),
        request_sequence=tuple(request_sequence),
        gate_values=gate_values,
    )
