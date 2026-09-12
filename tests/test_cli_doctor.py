import socket
from pathlib import Path

import boto3.session
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    """A provider/client or network connection during doctor must fail the test."""

    def deny_network(*args, **kwargs):
        raise AssertionError("Doctor must work offline")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(boto3.session.Session, "client", deny_network)
    monkeypatch.delenv("QUALOR_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("QUALOR_ENV", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)


def test_doctor_reports_verified_bootstrap_offline_from_any_directory(monkeypatch, tmp_path):
    from qualor.cli import app

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        "QUALOR",
        "PHASE=bootstrap",
        "PYTHON=PASS",
        "CANONICAL=PASS",
        "LIVE_MODE=DISABLED",
        "PAID_AWS_CALLS=DISABLED",
    ]


@pytest.mark.parametrize("content", [None, b"changed canonical bytes"])
def test_doctor_blocks_missing_or_changed_canonical(monkeypatch, content):
    from qualor.cli import app

    original_read = Path.read_bytes

    def read_candidate(path):
        if path.name == "00_CANONICAL_BRIEF_UA.md":
            if content is None:
                raise FileNotFoundError
            return content
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_candidate)
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "CANONICAL=BLOCKED" in result.output


def test_doctor_blocks_incompatible_python(monkeypatch):
    import qualor.cli as cli

    monkeypatch.setattr(cli.sys, "version_info", (3, 11, 0))
    result = CliRunner().invoke(cli.app, ["doctor"])
    assert result.exit_code == 1
    assert "PYTHON=BLOCKED" in result.output


def test_doctor_rejects_live_enablement(monkeypatch):
    from qualor.cli import app

    monkeypatch.setenv("QUALOR_LIVE_ENABLED", "true")
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "CONFIGURATION=BLOCKED" in result.output
    assert "LIVE_MODE=DISABLED" in result.output


def test_settings_default_to_safe_bootstrap_configuration():
    from qualor.settings import Settings

    settings = Settings(_env_file=None)
    assert settings.qualor_env == "development"
    assert settings.qualor_live_enabled is False
    assert settings.aws_region == "us-east-1"


def test_settings_read_nonsecret_environment(monkeypatch):
    from qualor.settings import Settings

    monkeypatch.setenv("QUALOR_ENV", "test")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    settings = Settings(_env_file=None)
    assert settings.qualor_env == "test"
    assert settings.aws_region == "eu-west-1"


def test_settings_refuse_live_mode(monkeypatch):
    from qualor.settings import Settings

    monkeypatch.setenv("QUALOR_LIVE_ENABLED", "true")
    with pytest.raises(ValidationError, match="Live mode is disabled during bootstrap"):
        Settings(_env_file=None)


WORKSPACE_FIXTURES = Path(__file__).parent / "fixtures/workspace"
W01 = WORKSPACE_FIXTURES / "W01_DECISION_TO_DRAFT_PACK.json"


def seed_command(tmp_path, monkeypatch, argument=None, **environment):
    """Invoke the development-only seed boundary against a temporary database."""
    from qualor.cli import app

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "workspace.db"))
    for name, value in environment.items():
        monkeypatch.setenv(name.upper(), value)
    return CliRunner().invoke(app, ["seed-workspace-fixture", str(argument or W01)])


def test_seed_accepts_an_owned_fixture_and_reports_only_bounded_facts(tmp_path, monkeypatch):
    result = seed_command(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "MODE=FIXTURE" in result.output
    # The opportunity identity is derived by the contract, never taken from the file.
    assert "OPPORTUNITY=opp_" in result.output
    assert "RECOMMENDATION=APPLY" in result.output
    assert (tmp_path / "workspace.db").exists()
    # The command reports what it recorded, never credentials, paths or raw source text.
    for forbidden in ("token", "secret", "password", "arn:", "http://", "https://"):
        assert forbidden not in result.output.lower()


def test_seed_derives_authority_from_the_engines_rather_than_the_file(tmp_path, monkeypatch):
    """The fixture supplies inputs. The deterministic engines supply the decision."""
    import json

    from qualor.persistence import Database
    from qualor.workspace import WorkspaceStore

    payload = json.loads(W01.read_text(encoding="utf-8"))
    assert "recommendation" not in payload
    assert "eligibility" not in payload

    result = seed_command(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    opportunity = next(
        line.split("=", 1)[1]
        for line in result.output.splitlines()
        if line.startswith("OPPORTUNITY=")
    )
    with Database(tmp_path / "workspace.db").transaction() as connection:
        workspace = WorkspaceStore(connection).load_opportunity_workspace(opportunity, 1)
    assert workspace.decisions and workspace.decisions[0].recommendation.value == "APPLY"


def test_seed_rejects_a_fixture_that_claims_a_non_fixture_mode(tmp_path, monkeypatch):
    import json

    payload = json.loads(W01.read_text(encoding="utf-8"))
    payload["mode"] = "LIVE"
    claimed = tmp_path / "claims-live.json"
    claimed.write_text(json.dumps(payload), encoding="utf-8")
    result = seed_command(tmp_path, monkeypatch, claimed)
    assert result.exit_code == 2
    assert "FIXTURE" in result.output


def test_seed_refuses_outside_a_development_environment(tmp_path, monkeypatch):
    result = seed_command(tmp_path, monkeypatch, qualor_env="production")
    assert result.exit_code == 2
    assert "DEVELOPMENT" in result.output
    assert not (tmp_path / "workspace.db").exists()


@pytest.mark.parametrize("argument", ["missing.json", "https://example.com/fixture.json"])
def test_seed_refuses_an_unreadable_or_remote_input(tmp_path, monkeypatch, argument):
    result = seed_command(tmp_path, monkeypatch, argument)
    assert result.exit_code == 2
    assert "INVALID_FIXTURE" in result.output


def test_seed_never_opens_a_network_or_aws_client(tmp_path, monkeypatch):
    """The autouse offline guard fails this test if any provider boundary is touched."""
    assert seed_command(tmp_path, monkeypatch).exit_code == 0


W02 = WORKSPACE_FIXTURES / "W02_PARTIAL_STALE_WATCH.json"
REBASE_CLOCKS = (
    "2026-09-10T12:00:00Z",
    "2026-09-14T12:00:00Z",
    "2026-09-16T12:00:00Z",
    "2027-03-01T12:00:00Z",
)


def instant(value):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def temporal_facts(payload):
    """Every temporal fact the moving scenario owns, addressed by a stable path.

    Paths are read from the typed contract rather than guessed from string shape, so a
    text operand that merely looks like a date is never treated as time.
    """
    facts = {"evaluated_at": payload["evaluated_at"]}
    for field in ("created_at", "updated_at", "verified_at"):
        if payload["founder"].get(field):
            facts[f"founder.{field}"] = payload["founder"][field]
    for index, entry in enumerate(payload.get("projects", [])):
        for field in ("created_at", "updated_at", "facts_verified_at"):
            if entry["project"].get(field):
                facts[f"projects[{index}].project.{field}"] = entry["project"][field]
    opportunity = payload["opportunity"]
    for field in ("created_at", "updated_at"):
        if opportunity.get(field):
            facts[f"opportunity.{field}"] = opportunity[field]
    for index, value in enumerate(opportunity.get("deadlines") or []):
        facts[f"opportunity.deadlines[{index}]"] = value
    for index, record in enumerate(payload.get("evidence", [])):
        for field in ("created_at", "updated_at", "retrieved_at"):
            if record.get(field):
                facts[f"evidence[{index}].{field}"] = record[field]
    for index, rule in enumerate(payload.get("eligibility_rules", [])):
        for field in ("created_at", "updated_at"):
            if rule.get(field):
                facts[f"eligibility_rules[{index}].{field}"] = rule[field]
        for position, operand in enumerate(rule.get("operands", [])):
            if operand.get("kind") in {"instant", "date"}:
                facts[f"eligibility_rules[{index}].operands[{position}].value"] = operand["value"]
    return facts


def verdict(payload):
    from qualor.decisions import DecisionFixture, decide_fixture

    result = decide_fixture(DecisionFixture.model_validate(payload))
    selected = result.selected_decision
    return (
        result.recommendation.value,
        selected.eligibility_gate.state.value if selected else "UNRESOLVED",
    )


@pytest.mark.parametrize("clock", REBASE_CLOCKS)
def test_w01_keeps_its_authored_verdict_at_every_rebased_clock(clock):
    """A scenario fixture must decide the same way whenever it is seeded."""
    import json

    from qualor.cli import _rebased_observations

    authored = json.loads(W01.read_text(encoding="utf-8"))
    assert verdict(authored) == ("APPLY", "PASS")
    assert verdict(_rebased_observations(authored, instant(clock))) == ("APPLY", "PASS")


@pytest.mark.parametrize("clock", REBASE_CLOCKS)
def test_w02_keeps_its_authored_unresolved_verdict_at_every_rebased_clock(clock):
    import json

    from qualor.cli import _rebased_observations

    authored = json.loads(W02.read_text(encoding="utf-8"))
    assert verdict(authored) == ("WATCH", "REVIEW_REQUIRED")
    assert verdict(_rebased_observations(authored, instant(clock))) == ("WATCH", "REVIEW_REQUIRED")


@pytest.mark.parametrize("name", ["W01_DECISION_TO_DRAFT_PACK", "W02_PARTIAL_STALE_WATCH"])
@pytest.mark.parametrize("clock", REBASE_CLOCKS)
def test_every_temporal_fact_moves_by_one_shared_delta(name, clock):
    """One delta, applied to the whole scenario, so authored relationships survive."""
    import json

    from qualor.cli import _rebased_observations

    authored = json.loads((WORKSPACE_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    rebased = _rebased_observations(authored, instant(clock))

    before, after = temporal_facts(authored), temporal_facts(rebased)
    assert set(before) == set(after)
    assert before, "the fixture must carry temporal facts to rebase"

    deltas = {path: instant(after[path]) - instant(before[path]) for path in before}
    assert len(set(deltas.values())) == 1, {
        path: str(delta) for path, delta in deltas.items() if delta != deltas["evaluated_at"]
    }
    assert instant(after["evaluated_at"]) == instant(clock)


@pytest.mark.parametrize("clock", REBASE_CLOCKS)
def test_authored_temporal_relationships_survive_the_rebase(clock):
    """The named relationships the engines actually reason about stay exactly as authored."""
    import json

    from qualor.cli import _rebased_observations

    authored = json.loads(W01.read_text(encoding="utf-8"))
    rebased = _rebased_observations(authored, instant(clock))

    def spans(payload):
        anchor = instant(payload["evaluated_at"])
        facts = temporal_facts(payload)
        return {path: instant(value) - anchor for path, value in facts.items()}

    assert spans(authored) == spans(rebased)

    # The eligibility window still contains the moment the scenario is evaluated.
    window = [
        operand["value"]
        for rule in rebased["eligibility_rules"]
        if rule.get("id") == "r_DEADLINE"
        for operand in rule.get("operands", [])
        if operand.get("kind") == "instant"
    ]
    assert len(window) == 2
    assert instant(window[0]) <= instant(rebased["evaluated_at"]) <= instant(window[1])


@pytest.mark.parametrize("clock", REBASE_CLOCKS)
def test_rebasing_never_moves_a_stable_opportunity_identity(clock):
    """Identity is organizer/program/edition. No clock may change which opportunity this is."""
    import json

    from qualor.cli import _rebased_observations
    from qualor.decisions import DecisionFixture
    from qualor.domain.opportunity import opportunity_identity

    authored = json.loads(W01.read_text(encoding="utf-8"))
    rebased = _rebased_observations(authored, instant(clock))
    for field in ("organizer", "program_name", "edition"):
        assert rebased["opportunity"][field] == authored["opportunity"][field]

    # Identity is derived by the contract from organizer/programme/edition alone, so no
    # retrieval-only timestamp and no rebase clock can change which opportunity this is.
    before = DecisionFixture.model_validate(authored).opportunity
    after = DecisionFixture.model_validate(rebased).opportunity
    assert after.id == before.id
    assert after.id == opportunity_identity(after.organizer, after.program_name, after.edition)


@pytest.mark.parametrize("name", ["W01_DECISION_TO_DRAFT_PACK", "W02_PARTIAL_STALE_WATCH"])
def test_neither_fixture_injects_an_authoritative_verdict(name):
    """Fixtures supply inputs. Every verdict stays the deterministic engines' to produce."""
    import json

    payload = json.loads((WORKSPACE_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    for forbidden in ("recommendation", "eligibility", "approval", "draft_pack", "pack_id"):
        assert forbidden not in payload
    assert payload["mode"] == "FIXTURE"


def test_rebase_reaches_temporal_facts_the_current_fixtures_do_not_yet_carry():
    """Nested rule windows and dated scenario facts move with everything else.

    The owned fixtures use flat rules today. A nested DATE_BETWEEN left behind would
    reproduce exactly the defect this rebase exists to prevent, so the traversal is proven
    against a constructed payload rather than only against what W01 happens to contain.
    """
    from qualor.cli import _rebased_observations

    authored = {
        "evaluated_at": "2026-09-05T12:00:00Z",
        "founder": {
            "created_at": "2026-09-05T12:00:00Z",
            "incorporation_date": {"value": "2020-01-31", "provenance": "USER_ASSERTED"},
            "legal_form": {"value": "not-a-date", "provenance": "USER_ASSERTED"},
        },
        "opportunity": {
            "deadlines": ["2026-09-15T12:00:00Z"],
            "rewards": [{"expiry": "2026-10-01", "kind": "CASH_PRIZE"}],
            "program_name": "AWS Agents for Humans",
        },
        "active_submissions": [{"submission_dates": ["2026-08-20"]}],
        "eligibility_rules": [
            {
                "id": "r_outer",
                "created_at": "2026-09-01T00:00:00Z",
                "children": [
                    {
                        "id": "r_nested",
                        "operands": [
                            {"kind": "instant", "value": "2026-09-01T00:00:00Z"},
                            {"kind": "date", "value": "2026-09-15"},
                            {"kind": "text", "value": "2026-09-15"},
                        ],
                    }
                ],
            }
        ],
    }
    rebased = _rebased_observations(authored, instant("2027-03-01T12:00:00Z"))
    delta = instant(rebased["evaluated_at"]) - instant(authored["evaluated_at"])

    authored_nested = authored["eligibility_rules"][0]["children"][0]["operands"]
    nested = rebased["eligibility_rules"][0]["children"][0]["operands"]
    assert instant(nested[0]["value"]) - instant(authored_nested[0]["value"]) == delta
    assert nested[1]["value"] == "2027-03-11", "a date operand stays a calendar date"
    assert nested[2]["value"] == "2026-09-15", "a text operand is never treated as time"

    assert rebased["founder"]["legal_form"]["value"] == "not-a-date"
    assert rebased["founder"]["incorporation_date"]["value"] == "2020-07-26"
    assert rebased["opportunity"]["rewards"][0]["expiry"] == "2027-03-27"
    assert rebased["opportunity"]["rewards"][0]["kind"] == "CASH_PRIZE"
    assert rebased["active_submissions"][0]["submission_dates"] == ["2027-02-13"]
    assert rebased["opportunity"]["program_name"] == "AWS Agents for Humans"


# --- Real-source REPLAY ingestion -----------------------------------------------------
#
# A captured real official source is not an owned scenario. Its instants are the source's
# own and must survive ingestion untouched, because the product quotes the excerpt that
# states them: a moved deadline would disagree with its own citation. FIXTURE keeps the
# moving-scenario rebase; REPLAY must not inherit it, and LIVE stays refused here.


def replay_payload():
    """W01's shape, declared REPLAY. The contract under test is the mode and the clock."""
    import json

    payload = json.loads(W01.read_text(encoding="utf-8"))
    payload["mode"] = "REPLAY"
    return payload


def seed_payload(tmp_path, monkeypatch, payload, name="capture.json"):
    import json

    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return seed_command(tmp_path, monkeypatch, path)


def persisted(tmp_path, opportunity_id):
    from qualor.persistence import Database
    from qualor.workspace import WorkspaceStore

    with Database(tmp_path / "workspace.db").transaction() as connection:
        store = WorkspaceStore(connection)
        workspace = store.load_opportunity_workspace(opportunity_id, 1)
        run = store.runs.current(f"seed-{opportunity_id}")
        events = store.runs.list_run_events(f"seed-{opportunity_id}")
    return workspace, run, events


def seeded_opportunity(result):
    return next(
        line.split("=", 1)[1]
        for line in result.output.splitlines()
        if line.startswith("OPPORTUNITY=")
    )


def test_seed_accepts_a_replay_capture_and_reports_its_own_mode(tmp_path, monkeypatch):
    result = seed_payload(tmp_path, monkeypatch, replay_payload())
    assert result.exit_code == 0, result.output
    assert "MODE=REPLAY" in result.output
    assert "MODE=FIXTURE" not in result.output


def test_seed_persists_replay_as_replay_rather_than_as_a_fixture(tmp_path, monkeypatch):
    """The recorded mode is the mode that ran. Nothing downstream may soften it."""
    result = seed_payload(tmp_path, monkeypatch, replay_payload())
    assert result.exit_code == 0, result.output
    _, run, events = persisted(tmp_path, seeded_opportunity(result))
    assert run is not None and run.mode.value == "REPLAY"
    assert [event.mode.value for event in events] == ["REPLAY"] * len(events)
    assert events, "the seeded run must record its observations"


def test_a_replay_capture_is_never_rebased_onto_the_current_clock(tmp_path, monkeypatch):
    """Every temporal fact the capture owns is the source's, not the seeding clock's."""
    payload = replay_payload()
    result = seed_payload(tmp_path, monkeypatch, payload)
    assert result.exit_code == 0, result.output

    authored = temporal_facts(payload)
    assert authored, "the capture must carry temporal facts"
    observed = next(
        line.split("=", 1)[1]
        for line in result.output.splitlines()
        if line.startswith("OBSERVED_AT=")
    )
    assert instant(observed) == instant(authored["evaluated_at"])


def test_a_replay_capture_keeps_its_official_deadline_and_source_truth(tmp_path, monkeypatch):
    """Deadline, excerpt, URLs, hash and retrieval instant all survive the round trip."""
    payload = replay_payload()
    result = seed_payload(tmp_path, monkeypatch, payload)
    assert result.exit_code == 0, result.output
    workspace, _, _ = persisted(tmp_path, seeded_opportunity(result))

    assert [d.isoformat().replace("+00:00", "Z") for d in workspace.opportunity.deadlines] == list(
        payload["opportunity"]["deadlines"]
    )

    authored = {record["id"]: record for record in payload["evidence"]}
    assert workspace.evidence, "the capture must persist its evidence"
    for record in workspace.evidence:
        source = authored[record.id]
        assert record.supporting_excerpt == source["supporting_excerpt"]
        assert record.original_url == source["original_url"]
        assert record.final_url == source["final_url"]
        assert record.content_hash == source["content_hash"]
        assert record.retrieved_at.isoformat().replace("+00:00", "Z") == source["retrieved_at"]


def test_a_replay_capture_survives_a_restart_unchanged(tmp_path, monkeypatch):
    """Reopening the database is the only way to prove this was persisted, not cached."""
    payload = replay_payload()
    result = seed_payload(tmp_path, monkeypatch, payload)
    assert result.exit_code == 0, result.output
    opportunity = seeded_opportunity(result)

    first, first_run, _ = persisted(tmp_path, opportunity)
    second, second_run, _ = persisted(tmp_path, opportunity)
    assert first_run.mode.value == second_run.mode.value == "REPLAY"
    assert [r.supporting_excerpt for r in first.evidence] == [
        r.supporting_excerpt for r in second.evidence
    ]
    assert second.opportunity.deadlines == first.opportunity.deadlines


def test_seeding_a_fixture_still_moves_it_onto_the_current_clock(tmp_path, monkeypatch):
    """The moving-scenario rebase is unchanged for owned fixtures; only REPLAY opts out."""
    import json
    from datetime import UTC, datetime

    payload = json.loads(W01.read_text(encoding="utf-8"))
    result = seed_payload(tmp_path, monkeypatch, payload, name="owned.json")
    assert result.exit_code == 0, result.output
    assert "MODE=FIXTURE" in result.output
    observed = next(
        line.split("=", 1)[1]
        for line in result.output.splitlines()
        if line.startswith("OBSERVED_AT=")
    )
    assert instant(observed) != instant(payload["evaluated_at"])
    assert abs((datetime.now(UTC) - instant(observed)).total_seconds()) < 300


def test_seed_still_refuses_a_capture_that_claims_live(tmp_path, monkeypatch):
    """Widening the envelope to REPLAY must not open it to LIVE."""
    payload = replay_payload()
    payload["mode"] = "LIVE"
    result = seed_payload(tmp_path, monkeypatch, payload, name="claims-live.json")
    assert result.exit_code == 2
    assert not (tmp_path / "workspace.db").exists()
