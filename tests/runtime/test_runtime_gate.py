import pytest

from qualor.runtime import LiveProviders, ProviderBoundaryError, RuntimeBoundary, RuntimeMode


class ProviderStub:
    pass


def live_providers() -> LiveProviders:
    provider = ProviderStub()
    return LiveProviders(model=provider, search=provider, fetcher=provider)


@pytest.mark.parametrize("mode", [RuntimeMode.FIXTURE, RuntimeMode.REPLAY])
def test_C01_C02_offline_modes_reject_live_providers(mode):
    with pytest.raises(ProviderBoundaryError, match="cannot receive live providers"):
        RuntimeBoundary.open(mode, live_providers())


def test_C03_live_mode_requires_an_explicit_provider_bundle():
    with pytest.raises(ProviderBoundaryError, match="requires explicit live providers"):
        RuntimeBoundary.open(RuntimeMode.LIVE)

    boundary = RuntimeBoundary.open(RuntimeMode.LIVE, live_providers())
    assert boundary.mode is RuntimeMode.LIVE
    assert boundary.providers is not None


@pytest.mark.parametrize("mode", [RuntimeMode.FIXTURE, RuntimeMode.REPLAY])
def test_offline_mode_output_keeps_its_exact_label(mode):
    boundary = RuntimeBoundary.open(mode)
    assert boundary.mode.value == mode.value
    assert boundary.providers is None
