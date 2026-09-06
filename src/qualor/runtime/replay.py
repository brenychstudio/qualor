"""Offline observations only: no credential chain, network client or executable replay code."""

from .providers import SearchCandidate
from .sources import SourceDocument


class RecordedProviders:
    def __init__(self, *, searches: dict[str, list[dict]], sources: list[SourceDocument]):
        if len(searches) > 5 or len(sources) > 10:
            raise ValueError("Recorded observations exceed run limits")
        self.searches = {
            q: tuple(SearchCandidate(**c) for c in rows) for q, rows in searches.items()
        }
        self.sources = {s.original_url: SourceDocument.model_validate(s) for s in sources}

    def search(self, request):
        request.__post_init__()
        if request.query not in self.searches:
            raise ValueError("REPLAY_SEARCH_NOT_RECORDED")
        return self.searches[request.query][: request.max_results]

    def fetch(self, request):
        if request.url not in self.sources:
            raise ValueError("REPLAY_SOURCE_NOT_RECORDED")
        return self.sources[request.url]
