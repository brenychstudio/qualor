"""Offline regression for the diagnosed IPv6 TLS failure; no AWS requests."""

import importlib.util
from pathlib import Path

import httpx

SPEC = importlib.util.spec_from_file_location(
    "aws_mcp_proxy", Path(__file__).parents[1] / "scripts" / "aws_mcp_proxy.py"
)
proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proxy)


def test_ipv4_adapter_preserves_original_sigv4_client_and_tls_verification(monkeypatch):
    options = {}
    captured = {}
    transport = object()
    client = object()

    def transport_factory(**kwargs):
        options.update(kwargs)
        return transport

    def upstream_factory(**kwargs):
        captured.update(kwargs)
        return client

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport_factory)
    result = proxy.ipv4_client(
        upstream_factory,
        service="aws-mcp",
        region="us-east-1",
        profile="qualor-dev",
        metadata={"AWS_REGION": "us-east-1"},
        skip_auth=False,
    )
    assert result is client
    assert options["local_address"] == "0.0.0.0"
    assert options["verify"] is True
    assert captured["transport"] is transport
    assert captured["profile"] == "qualor-dev"
    assert captured["region"] == "us-east-1"
    assert captured["skip_auth"] is False
    assert captured["metadata"] == {"AWS_REGION": "us-east-1"}
