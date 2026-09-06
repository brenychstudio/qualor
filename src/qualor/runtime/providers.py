"""Provider interfaces expose observations, never eligibility or recommendations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from urllib.parse import urlsplit
from uuid import uuid4


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
    max_results: int = 5
    filters: dict | None = None
    run_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query) > 200:
            raise ValueError("Search query must contain 1–200 characters")
        if type(self.max_results) is not int or not 1 <= self.max_results <= 25:
            raise ValueError("maxResults must be an integer in 1–25")
        if self.filters is not None:
            if not isinstance(self.filters, dict) or self.filters.keys() - {
                "domainFilter",
                "publishedDateFilter",
            }:
                raise ValueError("Unsupported search filters")
            domains = self.filters.get("domainFilter", {})
            if not isinstance(domains, dict) or domains.keys() - {"include", "exclude"}:
                raise ValueError("Invalid domain filter")
            for values in domains.values():
                if not isinstance(values, list) or not 1 <= len(values) <= 100:
                    raise ValueError("Domain filters require 1–100 domains")
                if any(
                    not isinstance(v, str)
                    or not v
                    or "/" in v
                    or ":" in v
                    or any(c.isspace() for c in v)
                    for v in values
                ):
                    raise ValueError("Invalid domain name")
            dates = self.filters.get("publishedDateFilter", {})
            if not isinstance(dates, dict) or dates.keys() - {"from", "to"}:
                raise ValueError("Invalid publication filter")
            parsed = {}
            for key, value in dates.items():
                if not isinstance(value, str) or not value.endswith("Z"):
                    raise ValueError("Publication bounds must be ISO-8601 UTC")
                parsed[key] = datetime.fromisoformat(value)
            if "from" in parsed and "to" in parsed and parsed["from"] > parsed["to"]:
                raise ValueError("Publication range is reversed")


@dataclass(frozen=True)
class SearchCandidate:
    url: str | None
    title: str | None
    snippet: str
    published_date: str | None = None
    retrieved_at: datetime | None = None
    provider: str = "UNSPECIFIED"
    query_id: str | None = None
    run_id: str | None = None

    @property
    def source_domain(self) -> str | None:
        try:
            return urlsplit(self.url).hostname if self.url else None
        except ValueError:
            return None

    @property
    def citable_for_user_output(self) -> bool:
        try:
            parts = urlsplit(self.url or "")
            return bool(
                parts.scheme in {"http", "https"}
                and parts.hostname
                and not parts.username
                and not parts.password
            )
        except ValueError:
            return False

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
