"""Hash-bound archived source input for offline canonical-compiler tests only."""

import hashlib
import json
import socket
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

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
