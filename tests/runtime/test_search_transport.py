import json

import httpx
import pytest
from botocore.credentials import Credentials

ENDPOINT = "https://owned-gateway-abcdefghij.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"


def transport(handler, versions=("2026-07-28",), mode="LIVE"):
    from qualor.runtime.search_transport import GatewayMcpTransport

    return GatewayMcpTransport(
        mode=mode,
        endpoint=ENDPOINT,
        supported_versions=versions,
        credentials=lambda: Credentials("testing", "testing", "temporary"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_stateless_metadata_matches_signed_headers_without_initialize():
    def respond(request):
        payload = json.loads(request.content)
        assert payload["method"] == "tools/list"
        assert request.headers["mcp-protocol-version"] == "2026-07-28"
        assert request.headers["mcp-method"] == "tools/list"
        assert payload["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
        assert "bedrock-agentcore/aws4_request" in request.headers["authorization"]
        assert request.headers["x-amz-security-token"] == "temporary"
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": []}}
        )

    t = transport(respond)
    assert t.rpc("tools/list", {}) == {"tools": []}
    assert t.stateless is True


def test_legacy_initialize_negotiates_and_preserves_session():
    methods = []

    def respond(request):
        p = json.loads(request.content)
        methods.append(p["method"])
        if p["method"] == "initialize":
            assert p["params"]["protocolVersion"] == "2025-11-25"
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "owned-session"},
                json={
                    "jsonrpc": "2.0",
                    "id": p["id"],
                    "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}},
                },
            )
        assert request.headers["mcp-session-id"] == "owned-session"
        assert request.headers["mcp-protocol-version"] == "2025-06-18"
        if p["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": p["id"], "result": {"tools": []}})

    t = transport(respond, versions=())
    assert t.rpc("tools/list", {}) == {"tools": []}
    assert methods == ["initialize", "notifications/initialized", "tools/list"]
    assert t.version == "2025-06-18"
    assert t.stateless is False


def test_sse_parses_multiline_data_and_ignores_keepalive():
    def respond(request):
        p = json.loads(request.content)
        raw = (
            ': ping\r\n\r\nevent: message\r\ndata: {"jsonrpc":"2.0",\r\n'
            f'data: "id":"{p["id"]}","result":{{"tools":[]}}}}\r\n\r\n'
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=raw)

    assert transport(respond).rpc("tools/list", {}) == {"tools": []}


def test_sse_returns_at_complete_response_without_waiting_for_disconnect():
    class OpenStream(httpx.SyncByteStream):
        def __init__(self, request_id):
            self.request_id = request_id

        def __iter__(self):
            yield (
                "data: "
                + json.dumps({"jsonrpc": "2.0", "id": self.request_id, "result": {"tools": []}})
                + "\n\n"
            ).encode()
            pytest.fail("Client waited past the complete SSE response")

    def respond(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=OpenStream(json.loads(request.content)["id"]),
        )

    assert transport(respond).rpc("tools/list", {}) == {"tools": []}


@pytest.mark.parametrize("mode", ["FIXTURE", "REPLAY"])
def test_factory_rejects_offline_before_credential_chain(monkeypatch, mode):
    import qualor.runtime.search_transport as module

    monkeypatch.setattr(module, "_temporary_credentials", lambda: pytest.fail("AWS access"))
    with pytest.raises(RuntimeError):
        with module.open_gateway_transport(
            mode=mode, gateway_id="qualor-opportunity-gateway-owned"
        ):
            pytest.fail("Offline provider constructed")


def test_factory_rejects_root_before_gateway_access(monkeypatch):
    import qualor.runtime.search_transport as module

    monkeypatch.setattr(
        module, "_temporary_credentials", lambda: Credentials("test", "test", "test")
    )
    calls = []

    def aws(args):
        calls.append(args)
        return {"Arn": "synthetic:root"}

    monkeypatch.setattr(module, "_aws_json", aws)
    with pytest.raises(RuntimeError, match="non-root"):
        with module.open_gateway_transport(
            mode="LIVE", gateway_id="qualor-opportunity-gateway-owned"
        ):
            pytest.fail("Root accepted")
    assert calls == [["sts", "get-caller-identity"]]


@pytest.mark.parametrize(
    "body",
    [
        {"jsonrpc": "2.0", "id": "wrong", "result": {}},
        {"jsonrpc": "2.0", "id": "wrong", "error": {"message": "private"}},
        {"result": {}},
        [],
    ],
)
def test_bad_envelope_rejected(body):
    with pytest.raises(ValueError):
        transport(lambda r: httpx.Response(200, json=body)).rpc("tools/list", {})


def test_http_error_does_not_leak_server_auth_material_or_retry():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(403, text="sensitive body")

    with pytest.raises(RuntimeError, match="HTTP_403") as caught:
        transport(respond).rpc("tools/list", {})
    assert "sensitive" not in str(caught.value)
    assert len(calls) == 1


def test_response_size_cap():
    with pytest.raises(ValueError):
        transport(
            lambda r: httpx.Response(
                200, text="x" * 2_000_001, headers={"content-type": "application/json"}
            )
        ).rpc("tools/list", {})


@pytest.mark.parametrize("mode", ["FIXTURE", "REPLAY"])
def test_offline_transport_cannot_be_constructed(mode):
    with pytest.raises(RuntimeError):
        transport(lambda r: pytest.fail("offline network"), mode=mode)


def test_permanent_credentials_cannot_sign():
    t = transport(lambda r: pytest.fail("network with permanent credentials"))
    t.credentials = lambda: Credentials("testing", "testing")
    with pytest.raises(RuntimeError):
        t.rpc("tools/list", {})


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.org/mcp",
        "https://example.org/mcp",
        ENDPOINT + "?redirect=elsewhere",
        ENDPOINT.replace("/mcp", "/other"),
    ],
)
def test_reject_noncanonical_signing_destination(endpoint):
    from qualor.runtime.search_transport import GatewayMcpTransport

    with pytest.raises(ValueError):
        GatewayMcpTransport(
            mode="LIVE",
            endpoint=endpoint,
            supported_versions=(),
            credentials=lambda: Credentials("testing", "testing", "temporary"),
        )
