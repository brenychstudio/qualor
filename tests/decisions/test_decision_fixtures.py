import copy
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1] / "fixtures" / "decisions"
EXPECTED = [
    "APPLY",
    "PREPARE",
    "SKIP",
    "WATCH",
    "SKIP",
    "WATCH",
    "WATCH",
    "SKIP",
    "APPLY",
    "WATCH",
    "SKIP",
    "WATCH",
]


def payload(n=1):
    return json.loads(next(ROOT.glob(f"D{n:02d}_*.json")).read_text(encoding="utf-8"))


def decide(data):
    from qualor.decisions import DecisionFixture, decide_fixture

    return decide_fixture(DecisionFixture.model_validate(data))


@pytest.mark.parametrize("n,expected", list(enumerate(EXPECTED, 1)))
def test_owned_pipeline(n, expected):
    result = decide(payload(n))
    assert result.mode == "FIXTURE"
    assert result.recommendation == expected
    assert result.candidates and result.reasons
    for candidate in result.candidates:
        assert candidate.strategy_breakdown == candidate.strategy.breakdown
        assert candidate.strategy_score == candidate.strategy.score
        assert candidate.conflict_status == candidate.conflict.status
        assert all(v == 1 for v in candidate.policy_versions.model_dump().values())
    if n == 2:
        assert 60 <= result.selected_decision.strategy_score < 75
    if n == 3:
        assert result.selected_decision.eligibility_gate.state == "FAIL"
    if n == 9:
        assert result.best_project_id == "project_synthetic"
        assert len(result.candidates) == 2
    if n == 10:
        assert result.best_project_id is None and result.selected_decision is None
        assert all(d.recommendation == "APPLY" for d in result.candidates)
        assert result.candidate_semantics == "CONDITIONAL_PER_PROJECT"
    if n == 11:
        a = result.selected_decision.affordability
        assert (
            a.state == "INSUFFICIENT" and a.cash_budget.amount == 0 and a.cash_required.amount == 25
        )
    if n == 12:
        assert result.selected_decision.conflict_status == "REVIEW_REQUIRED"


def test_b40_roundtrip_and_deterministic_record():
    from qualor.decisions import DecisionRecord, DecisionResult

    result = decide(payload())
    assert decide(payload()) == result
    assert DecisionResult.model_validate_json(result.model_dump_json()) == result
    record = result.selected_decision
    assert DecisionRecord.model_validate_json(record.model_dump_json()) == record
    assert (
        record.profile_version == 1
        and record.opportunity_version == 1
        and record.project_version == 1
    )
    assert record.created_at == record.updated_at


@pytest.mark.parametrize(
    "field", ["eligibility_gate", "score", "conflict", "recommendation", "strategy"]
)
def test_forged_outputs_rejected(field):
    data = payload()
    data[field] = "APPLY"
    with pytest.raises(ValueError):
        decide(data)


@pytest.mark.parametrize("count", [0, 6])
def test_project_bounds(count):
    data = payload()
    data["projects"] = [copy.deepcopy(data["projects"][0]) for _ in range(count)]
    for n, p in enumerate(data["projects"]):
        p["project"]["id"] = f"p{n}"
    with pytest.raises(ValueError):
        decide(data)


def test_duplicate_project_ids():
    data = payload()
    data["projects"] *= 2
    with pytest.raises(ValueError):
        decide(data)


@pytest.mark.parametrize(
    "change", [{"status": "UNKNOWN"}, {"deadlines": []}, {"deadlines": ["2026-09-06"]}]
)
def test_unknown_opportunity_not_actionable(change):
    data = payload()
    data["opportunity"].update(change)
    if change.get("deadlines") == []:
        data["eligibility_rules"] = [
            r for r in data["eligibility_rules"] if r["rule_type"] != "DEADLINE"
        ]
    assert decide(data).recommendation == "WATCH"


@pytest.mark.parametrize("change", [{"status": "CLOSED"}, {"deadlines": ["2026-09-05T12:00:00Z"]}])
def test_expired_closed_priority(change):
    data = payload()
    data["opportunity"].update(change)
    data["founder"]["strategic_goals"] = {}
    assert decide(data).recommendation == "SKIP"


def test_unknown_status_preserves_fail():
    data = payload(3)
    data["opportunity"]["status"] = "UNKNOWN"
    assert decide(data).recommendation == "SKIP"


def test_each_project_has_own_gate_and_unknown_match_unresolved():
    data = payload(9)
    data["projects"][1]["project"]["license_intent"] = {}
    result = decide(data)
    assert result.candidates[0].eligibility_gate.state == "PASS"
    assert result.candidates[1].eligibility_gate.state == "REVIEW_REQUIRED"
    assert result.best_project_id is None and result.recommendation == "WATCH"


def test_earlier_rule_deadline_limits_capacity_without_mutation():
    data = payload()
    original = copy.deepcopy(data)
    rule = next(r for r in data["eligibility_rules"] if r["rule_type"] == "DEADLINE")
    rule["operands"][1] = {"kind": "instant", "value": "2026-09-05T13:00:00Z"}
    result = decide(data)
    assert result.selected_decision.capacity.remaining_wall_hours == 1
    assert result.recommendation == "WATCH"
    assert data["opportunity"] == original["opportunity"]


def test_unsupported_past_rule_is_not_authoritative_expiry():
    data = payload()
    rule = next(r for r in data["eligibility_rules"] if r["rule_type"] == "DEADLINE")
    rule["operands"][1] = {"kind": "instant", "value": "2026-09-05T11:00:00Z"}
    rule["supported"] = False
    assert decide(data).recommendation == "WATCH"


def test_instance_copy_revalidated():
    from qualor.decisions import DecisionFixture, decide_fixture

    fixture = DecisionFixture.model_validate(payload())
    with pytest.raises(ValueError):
        decide_fixture(fixture.model_copy(update={"mode": "LIVE"}))
    with pytest.raises(ValueError):
        decide_fixture(fixture.model_copy(update={"projects": fixture.projects * 2}))


def test_owned_snapshots_hash_exact_utf8():
    assert len(list(ROOT.glob("D*.json"))) == 12
    for path in ROOT.glob("D*.json"):
        for evidence in json.loads(path.read_text())["evidence"]:
            assert (
                hashlib.sha256(evidence["supporting_excerpt"].encode("utf-8")).hexdigest()
                == evidence["content_hash"]
            )


def test_public_explanation_is_concise_and_not_only_codes():
    result = decide(payload())
    assert (
        result.selected_decision.explanation
        == "Checked eligibility, capacity, costs and ready materials "
        "support preparing an application package."
    )
    assert result.explanation == result.selected_decision.explanation
    assert len(decide(payload(10)).explanation) < 300
