"""Provider interfaces expose observations, never eligibility or recommendations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    max_output_tokens: int
    temperature: int = 0


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class SearchRequest:
    query: str


@dataclass(frozen=True)
class SearchCandidate:
    url: str
    title: str
    snippet: str

    @property
    def can_create_candidate(self) -> bool:
        return True

    @property
    def can_prove_hard_eligibility(self) -> bool:
        return False


@dataclass(frozen=True)
class FetchRequest:
    url: str


@dataclass(frozen=True)
class FetchedSource:
    url: str
    content: str
    retrieved_at: datetime


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...


class SearchProvider(Protocol):
    def search(self, request: SearchRequest) -> tuple[SearchCandidate, ...]: ...


class SourceFetcher(Protocol):
    def fetch(self, request: FetchRequest) -> FetchedSource: ...


@dataclass(frozen=True)
class LiveProviders:
    model: ModelProvider
    search: SearchProvider
    fetcher: SourceFetcher
