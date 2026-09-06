import json
from pathlib import Path

import pytest


def test_live_and_replay_decisions_keep_real_mode_and_reject_synthetic_evidence():
    from qualor.decisions.engine import decide
    from qualor.decisions.fixture import DecisionInput

    data = json.loads(
        Path("tests/fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json").read_text()
    )
    for mode in ("LIVE", "REPLAY"):
        data["mode"] = mode
        result = decide(DecisionInput.model_validate(data))
        assert result.mode == mode
        assert all(d.eligibility_gate.state != "PASS" for d in result.candidates)
        assert result.recommendation != "APPLY"


def test_fixture_entry_point_still_cannot_report_live():
    from qualor.decisions.fixture import DecisionFixture

    data = json.loads(
        Path("tests/fixtures/decisions/D01_ELIGIBLE_HIGH_SCORE_READY_APPLY.json").read_text()
    )
    data["mode"] = "LIVE"
    with pytest.raises(ValueError):
        DecisionFixture.model_validate(data)
