# QUALOR-03B2 implementation plan

Source: `docs/00_CANONICAL_BRIEF_UA.md`; branch `qualor-03-live-agent`.

1. Verify identity, Gateway tags/state, installed target schema; create only the
   authorized `web-search@1.2.0` target with no permanent domain filters. Stop on failure.
2. Extend `runtime/providers.py` dataclass contracts with validated search limits,
   per-request filters, optional citation fields, retrieval time and run/query provenance.
3. Add `runtime/search.py`: `AgentCoreSearchProvider(mode, transport, budget)` implements
   the existing `SearchProvider.search(SearchRequest)` interface; discovers the tool
   from schema, reserves every attempted search, parses structured candidates only.
4. Add `runtime/search_transport.py`: `GatewayMcpTransport` signs bounded HTTPS requests
   with botocore SigV4 and temporary named-profile credentials. Handle JSON and SSE,
   version negotiation, legacy initialization and stateless per-request metadata.
   No endpoint, auth headers, account identifiers or credentials in source/output.
5. Add `search-live` in `cli.py`; require `--mode LIVE` and explicit local Gateway ID.
   Query validation precedes any AWS access. Surface citations with each candidate.
6. RED/GREEN in `tests/runtime/test_search.py` and `test_search_transport.py`: S01–S20,
   malformed responses, ID correlation, authentication and protocol metadata. Use
   synthetic HTTP responses; CI never calls AWS. Commands: `uv run pytest -q tests/runtime`
   then `uv run ruff check .`. No behavioral change without an observed failing test.
7. One live tools/list; primary search and only the specified zero-usable-results fallback.
   Reserve USD 0.009 per attempted query (search plus conservative Gateway allowance),
   at most two queries / USD 0.02. No paid inference or automatic retries.
8. Update `docs/status/QUALOR-03.md` with bounded sanitized evidence and limitations.
   Commit code/tests/docs, run verify.ps1, aws-preflight.ps1, schema/type generation,
   independent Ruff/pytest/frontend gates and secret scan; push only after green checks.

Deferred: Strands loop, official-source fetching, eligibility promotion, persistence,
other AWS resources, IAM modifications, target invocation beyond this bounded smoke,
final QUALOR-03 PR and QUALOR-03B3.
