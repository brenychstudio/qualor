"""Bounded AgentCore discovery. Search snippets never become verified evidence."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from .budget import LiveBudgetGuard, LiveCallKind
from .mode import ProviderBoundaryError, RuntimeMode
from .providers import SearchCandidate, SearchRequest

WEB_SEARCH_TASK_COST_CAP_USD = Decimal("0.02")
WEB_SEARCH_RESERVED_COST_USD = Decimal("0.009")


class McpTransport(Protocol):
    def rpc(self, method: str, params: dict) -> dict: ...


def _schema_object(value: dict, *path: str) -> dict:
    for key in path:
        if not isinstance(value, dict):
            raise ValueError("Malformed tool input schema")
        value = value.get(key, {})
    if not isinstance(value, dict):
        raise ValueError("Malformed tool input schema")
    return value


class AgentCoreSearchProvider:
    """One shared run budget; failed calls remain reserved, with no automatic retries."""

    def __init__(
        self, *, mode: RuntimeMode, transport: McpTransport, budget: LiveBudgetGuard
    ) -> None:
        if RuntimeMode(mode) is not RuntimeMode.LIVE or transport is None:
            raise ProviderBoundaryError("LIVE search requires explicit AgentCore transport")
        self.transport = transport
        self.budget = budget
        self.tool_name: str | None = None
        self.input_schema: dict | None = None

    def discover(self) -> None:
        if self.tool_name is not None:
            return
        response = self.transport.rpc("tools/list", {})
        tools = response.get("tools")
        if not isinstance(tools, list) or response.get("nextCursor"):
            raise ValueError("Expected a bounded complete WebSearch tool catalog")
        candidates = []
        for tool in tools:
            if not isinstance(tool, dict):
                raise ValueError("Malformed tool catalog")
            schema = _schema_object(tool, "inputSchema")
            properties = _schema_object(schema, "properties")
            if (
                isinstance(tool.get("name"), str)
                and schema.get("type") == "object"
                and _schema_object(properties, "query").get("type") == "string"
                and _schema_object(properties, "maxResults").get("type") == "integer"
                and _schema_object(properties, "filters").get("type") == "object"
            ):
                include = _schema_object(
                    properties, "filters", "properties", "domainFilter", "properties", "include"
                )
                if include.get("type") == "array":
                    candidates.append(tool)
        if len(candidates) != 1:
            raise ValueError("WebSearch v1.2.0 filter schema unavailable or ambiguous")
        self.tool_name = candidates[0]["name"]
        self.input_schema = candidates[0]["inputSchema"]

    def search(self, request: SearchRequest) -> tuple[SearchCandidate, ...]:
        # Revalidate mutable nested filter data before any network operation.
        request.__post_init__()
        self.discover()
        arguments = {"query": request.query, "maxResults": request.max_results}
        if request.filters is not None:
            arguments["filters"] = request.filters
        self.budget.reserve(LiveCallKind.SEARCH, estimated_cost_usd=WEB_SEARCH_RESERVED_COST_USD)
        response = self.transport.rpc(
            "tools/call", {"name": self.tool_name, "arguments": arguments}
        )
        return parse_search_result(response, request)


def parse_search_result(response: dict, request: SearchRequest) -> tuple[SearchCandidate, ...]:
    if not isinstance(response, dict) or response.get("isError"):
        raise ValueError("WebSearch tool returned an error")
    body = response.get("structuredContent")
    if body is None:
        blocks = response.get("content", [])
        if not isinstance(blocks, list):
            raise ValueError("Malformed MCP content")
        decoded = []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                try:
                    value = json.loads(block.get("text", ""))
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict) and "results" in value:
                    decoded.append(value)
        if len(decoded) != 1:
            raise ValueError("Expected one structured WebSearch result")
        body = decoded[0]
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise ValueError("Malformed structured search results")
    if len(body["results"]) > request.max_results:
        raise ValueError("Search returned more than the requested result limit")
    query_id = body.get("id", request.run_id)
    if not isinstance(query_id, str):
        raise ValueError("Malformed query identifier")
    now = datetime.now(UTC)
    candidates = []
    for row in body["results"]:
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            raise ValueError("Malformed search snippet")
        for key in ("url", "title", "publishedDate"):
            if row.get(key) is not None and not isinstance(row[key], str):
                raise ValueError("Malformed search citation")
        candidates.append(
            SearchCandidate(
                url=row.get("url"),
                title=row.get("title"),
                snippet=row["text"],
                published_date=row.get("publishedDate"),
                retrieved_at=now,
                provider="AGENTCORE_WEB_SEARCH",
                query_id=query_id,
                run_id=request.run_id,
            )
        )
    return tuple(candidates)
