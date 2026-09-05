"""Run the pinned AWS proxy with a process-local IPv4 HTTPS transport.

QUALOR-00B1 traced empty ConnectError/-32603 failures to IPv6 TLS resets.
HTTPX uses direct IPv4 HTTPS; AWS owns signing and MCP filtering.
"""

from functools import partial
from importlib.metadata import version

import httpx


def ipv4_client(factory, **kwargs):
    transport = httpx.AsyncHTTPTransport(
        local_address="0.0.0.0",
        verify=True,
        limits=httpx.Limits(max_keepalive_connections=1, max_connections=5),
    )
    return factory(**kwargs, transport=transport)


def main():
    if version("mcp-proxy-for-aws") != "1.6.5":
        raise SystemExit("MCP_PROXY=BLOCKED_VERSION")
    # The pinned factory forwards HTTPX kwargs and retains the upstream SigV4 hooks.
    # No installed package or global networking configuration is modified.
    from mcp_proxy_for_aws import server, utils

    utils.create_sigv4_client = partial(ipv4_client, utils.create_sigv4_client)
    return server.main()


if __name__ == "__main__":
    raise SystemExit(main())
