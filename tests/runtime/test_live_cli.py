from typer.testing import CliRunner

from qualor.cli import app


def test_live_opportunity_command_requires_explicit_activation():
    result = CliRunner().invoke(app, ["run-live-opportunity", "--profile", "missing.json"])
    assert result.exit_code != 0
    assert "LIVE_REQUIRES_EXPLICIT_MODE" in result.output


def test_replay_uses_recorded_observations_without_network():
    from test_claims import source

    from qualor.runtime.providers import FetchRequest, SearchRequest
    from qualor.runtime.replay import RecordedProviders

    providers = RecordedProviders(
        searches={
            "owned": [
                {"url": "https://example.org/rules", "title": "Owned", "snippet": "discovery"}
            ]
        },
        sources=[source()],
    )
    assert providers.search(SearchRequest("owned"))[0].url == "https://example.org/rules"
    assert providers.fetch(FetchRequest("https://example.org/rules")).id == "source_owned"
