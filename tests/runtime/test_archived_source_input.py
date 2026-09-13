import hashlib
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
from archived_compiler_support import (
    ARCHIVE_SHA256,
    ARCHIVE_TIMESTAMP,
    ArchivedInput,
    ArchiveInputError,
    archived_studio_input,
    deny_external_io,
    load_archived_rules,
)

ARCHIVE_ROOT = Path(
    r"C:\PROJECTS\qualor\.worktrees\qualor-killer-demo-real-source"
    r"\.qualor\local\killer-demo-real-source"
)


def _manifest(
    *, raw_artifact="official-rules.raw", timestamp=ARCHIVE_TIMESTAMP, digest=ARCHIVE_SHA256
):
    return {
        "SRC-OFFICIAL-RULES": {
            "SOURCE_ID": "SRC-OFFICIAL-RULES",
            "CANONICAL_SOURCE": "https://agentsforhumans.devpost.com/rules",
            "RETRIEVED_AT_UTC": timestamp,
            "CONTENT_SHA256": digest,
            "SOURCE_AUTHORITY": "OFFICIAL_RULES",
            "RAW_ARTIFACT": raw_artifact,
        }
    }


def _archive(tmp_path, *, raw=b"tiny archive", manifest=None):
    (tmp_path / "source-manifest.json").write_text(
        json.dumps(_manifest() if manifest is None else manifest), encoding="utf-8"
    )
    (tmp_path / "official-rules.raw").write_bytes(raw)
    return tmp_path


def _hash_bound_tiny_archive(monkeypatch, tmp_path, *, raw=b"tiny archive"):
    import archived_compiler_support

    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(archived_compiler_support, "ARCHIVE_SHA256", digest)
    return _archive(tmp_path, raw=raw, manifest=_manifest(digest=digest))


def _assert_code(exc, code):
    assert str(exc.value) == code


def test_missing_archive_directory_is_rejected(tmp_path):
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(tmp_path / "missing")
    _assert_code(exc, "ARCHIVE_DIRECTORY_INVALID")


def test_missing_rules_file_is_rejected(tmp_path):
    (tmp_path / "source-manifest.json").write_text(json.dumps(_manifest()), encoding="utf-8")

    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(tmp_path)
    _assert_code(exc, "ARCHIVE_RAW_ARTIFACT_MISSING")


def test_changed_raw_byte_is_rejected(tmp_path):
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, raw=b"changed"))
    _assert_code(exc, "ARCHIVE_RAW_HASH_MISMATCH")


def test_manifest_hash_mismatch_is_rejected(tmp_path):
    manifest = _manifest(digest="0" * 64)
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, manifest=manifest))
    _assert_code(exc, "ARCHIVE_MANIFEST_HASH_INVALID")


def test_wrong_raw_filename_is_rejected(tmp_path):
    manifest = _manifest(raw_artifact="not-rules.raw")
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, manifest=manifest))
    _assert_code(exc, "ARCHIVE_RAW_ARTIFACT_INVALID")


def test_wrong_timestamp_is_rejected(tmp_path):
    manifest = _manifest(timestamp="2026-09-12T11:25:53Z")
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, manifest=manifest))
    _assert_code(exc, "ARCHIVE_TIMESTAMP_INVALID")


def test_traversal_is_rejected_before_raw_read(tmp_path):
    manifest = _manifest(raw_artifact="../outside.raw")
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, manifest=manifest))
    _assert_code(exc, "ARCHIVE_RAW_ARTIFACT_INVALID")


def test_symlink_escape_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.raw"
    outside.write_bytes(b"outside")
    archive = _archive(tmp_path)
    (archive / "official-rules.raw").unlink()
    try:
        (archive / "official-rules.raw").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable on this Windows test host")

    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(archive)
    _assert_code(exc, "ARCHIVE_SYMLINK_ESCAPE")


def test_resolved_outside_path_is_rejected_without_symlink_privileges(tmp_path):
    import archived_compiler_support

    root = tmp_path / "archive"
    root.mkdir()
    outside = tmp_path / "outside.raw"
    outside.write_bytes(b"outside")

    with pytest.raises(ArchiveInputError) as exc:
        archived_compiler_support._contained(root.resolve(), outside, missing_code="UNUSED")
    _assert_code(exc, "ARCHIVE_SYMLINK_ESCAPE")


def test_changed_or_invalid_archive_never_reaches_parser(monkeypatch, tmp_path):
    import archived_compiler_support

    calls = []
    monkeypatch.setattr(
        archived_compiler_support,
        "canonical_source_text",
        lambda *_: calls.append(True) or ("unexpected", False),
    )
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, raw=b"changed"))
    _assert_code(exc, "ARCHIVE_RAW_HASH_MISMATCH")
    assert calls == []


def test_wrong_canonical_parse_is_rejected_without_authoritative_archive(monkeypatch, tmp_path):
    import archived_compiler_support

    archive = _hash_bound_tiny_archive(monkeypatch, tmp_path)
    monkeypatch.setattr(archived_compiler_support, "canonical_source_text", lambda *_: ("", False))
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(archive)
    _assert_code(exc, "ARCHIVE_SOURCE_PARSE_INVALID")


def test_malformed_manifest_url_is_normalized_before_raw_parsing(monkeypatch, tmp_path):
    import archived_compiler_support

    calls = []
    manifest = _manifest()
    manifest["SRC-OFFICIAL-RULES"]["CANONICAL_SOURCE"] = "https://["
    monkeypatch.setattr(
        archived_compiler_support,
        "canonical_source_text",
        lambda *_: calls.append(True) or ("unexpected", False),
    )
    with pytest.raises(ArchiveInputError) as exc:
        load_archived_rules(_archive(tmp_path, manifest=manifest))
    _assert_code(exc, "ARCHIVE_URL_INVALID")
    assert calls == []


def test_optional_archive_fixture_skips_only_unavailable_archives(monkeypatch, request, tmp_path):
    monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(tmp_path / "missing"))
    monkeypatch.delenv("QUALOR_REQUIRE_ARCHIVE", raising=False)

    with pytest.raises(pytest.skip.Exception):
        request.getfixturevalue("archived_source")


def test_optional_archive_fixture_propagates_integrity_failure(monkeypatch, request, tmp_path):
    monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(_archive(tmp_path, raw=b"changed")))
    monkeypatch.delenv("QUALOR_REQUIRE_ARCHIVE", raising=False)

    with pytest.raises(ArchiveInputError) as exc:
        request.getfixturevalue("archived_source")
    _assert_code(exc, "ARCHIVE_RAW_HASH_MISMATCH")


@pytest.mark.parametrize("selected", (None, "missing"))
def test_required_archive_fixture_fails_instead_of_skipping(
    monkeypatch, request, tmp_path, selected
):
    if selected is None:
        monkeypatch.delenv("QUALOR_ARCHIVE_DIR", raising=False)
    else:
        monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(tmp_path / selected))
    monkeypatch.setenv("QUALOR_REQUIRE_ARCHIVE", "1")

    with pytest.raises(ArchiveInputError) as exc:
        request.getfixturevalue("archived_source")
    _assert_code(exc, "ARCHIVE_DIRECTORY_INVALID")


def test_archive_loading_has_no_download_fallback(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: calls.append(True))

    with pytest.raises(ArchiveInputError):
        load_archived_rules(tmp_path / "missing")
    assert calls == []


def test_external_io_is_denied_at_aws_and_socket_boundaries(monkeypatch):
    import boto3
    import botocore.session
    from boto3.session import Session as SessionAlias

    client_alias = boto3.client
    dns_alias = socket.getaddrinfo
    config_calls = []
    credential_calls = []
    monkeypatch.setattr(
        botocore.session.Session,
        "get_scoped_config",
        lambda *_args, **_kwargs: config_calls.append(True),
    )
    monkeypatch.setattr(
        botocore.session.Session,
        "get_credentials",
        lambda *_args, **_kwargs: credential_calls.append(True),
    )
    session = object.__new__(SessionAlias)
    existing_socket = socket.socket()

    deny_external_io(monkeypatch)

    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        boto3.Session()
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        SessionAlias()
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        boto3.client("s3")
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        client_alias("s3")
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        session.client("s3")
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        socket.create_connection(("example.org", 443))
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        dns_alias("example.org", 443)
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        existing_socket.connect(("127.0.0.1", 9))
    with pytest.raises(ArchiveInputError, match="ARCHIVE_EXTERNAL_IO_DENIED"):
        existing_socket.connect_ex(("127.0.0.1", 9))
    existing_socket.close()
    assert config_calls == []
    assert credential_calls == []


@pytest.mark.archived_source
def test_archived_source_retains_manifest_identity_and_hash(archived_source):
    assert archived_source.id == "SRC-OFFICIAL-RULES"
    assert archived_source.content_hash == ARCHIVE_SHA256
    assert archived_source.retrieved_at == datetime(2026, 9, 12, 11, 25, 52, tzinfo=UTC)
    assert archived_source.authority == "OFFICIAL_RULES"
    assert archived_source.original_url == "https://agentsforhumans.devpost.com/rules"
    assert archived_source.final_url == archived_source.original_url
    assert archived_source.text
    assert archived_source.truncated is False


@pytest.mark.archived_source
def test_archived_source_matches_production_parser_and_archive_clock(archived_source):
    from qualor.runtime.sources import canonical_source_text

    raw = (ARCHIVE_ROOT / "official-rules.raw").read_bytes()
    expected_text, expected_truncated = canonical_source_text(raw, "text/html")
    archive = ArchivedInput(directory=ARCHIVE_ROOT, source=archived_source)

    assert (archived_source.text, archived_source.truncated) == (expected_text, expected_truncated)
    assert archive.evaluation_clock == archived_source.retrieved_at
    assert "Monday, September 14, 2026 (5:00 pm Pacific Time)" in archived_source.text


@pytest.mark.archived_source
def test_archived_studio_input_uses_independent_unknown_facts_and_fixed_clock(
    monkeypatch, archived_source
):
    monkeypatch.setenv("QUALOR_ARCHIVE_DIR", str(ARCHIVE_ROOT))
    inputs = archived_studio_input()

    assert inputs.allowed_hosts == ("agentsforhumans.devpost.com",)
    for field in (
        "country_of_residence",
        "citizenship",
        "legal_form",
        "incorporation_date",
        "team_size",
        "available_hours",
        "max_cash_commitment",
        "open_source_willingness",
        "strategic_goals",
    ):
        assert getattr(inputs.founder, field).provenance == "UNKNOWN"
    assert len(inputs.projects) == 1
    project = inputs.projects[0].project
    assert project.name == "Controlled compiler project"
    for field in (
        "problem",
        "audience",
        "stage",
        "available_features",
        "technology_stack",
        "code_provenance",
        "is_new_project",
        "license_intent",
        "prior_submissions",
        "estimated_adaptation_hours",
        "has_sponsor_support",
        "reward_conditions_met",
        "project_lineage",
        "reused_components",
        "reuse_disclosed",
    ):
        assert getattr(project, field).provenance == "UNKNOWN"
    assert inputs.projects[0].effort.items == ()
    assert inputs.founder.created_at == archived_source.retrieved_at
    assert project.created_at == archived_source.retrieved_at
    assert "Monday, September 14, 2026 (5:00 pm Pacific Time)" in archived_source.text
