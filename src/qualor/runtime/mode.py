"""Fail-closed runtime mode boundary."""

from dataclasses import dataclass
from enum import StrEnum

from .providers import LiveProviders


class RuntimeMode(StrEnum):
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    REPLAY = "REPLAY"


class ProviderBoundaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeBoundary:
    mode: RuntimeMode
    providers: LiveProviders | None

    @classmethod
    def open(
        cls, mode: RuntimeMode, providers: LiveProviders | None = None
    ) -> "RuntimeBoundary":
        mode = RuntimeMode(mode)
        if mode in {RuntimeMode.FIXTURE, RuntimeMode.REPLAY} and providers is not None:
            raise ProviderBoundaryError(f"{mode.value} cannot receive live providers")
        if mode is RuntimeMode.LIVE and providers is None:
            raise ProviderBoundaryError("LIVE requires explicit live providers")
        return cls(mode=mode, providers=providers)
