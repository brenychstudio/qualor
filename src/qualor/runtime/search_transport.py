"""Explicit live-only SigV4 MCP transport. No credentials or endpoints are persisted."""

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from botocore.session import Session

from .mode import ProviderBoundaryError, RuntimeMode

PROFILE = "qualor-dev"
REGION = "us-east-1"
STATELESS_VERSION = "2026-07-28"
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MAX_RESPONSE_BYTES = 2_000_000
CLIENT_INFO = {"name": "qualor-bounded-search", "version": "1"}


class GatewayMcpTransport:
    """Signed requests with bounded responses, no redirects and no automatic retries."""

    def __init__(
        self,
        *,
        mode: RuntimeMode,
        endpoint: str,
        supported_versions: tuple[str, ...],
        credentials: Callable[[], Credentials],
        client: httpx.Client | None = None,
    ) -> None:
        if RuntimeMode(mode) is not RuntimeMode.LIVE:
            raise ProviderBoundaryError("AWS transport requires explicit LIVE mode")
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or not re.fullmatch(
                r"[a-z0-9-]+\.gateway\.bedrock-agentcore\.us-east-1\.amazonaws\.com",
                url.hostname or "",
            )
            or url.path != "/mcp"
            or url.query
            or url.fragment
            or url.username
            or url.password
            or url.port not in (None, 443)
        ):
            raise ValueError("Expected canonical regional HTTPS Gateway endpoint")
        self.endpoint = endpoint
        self.credentials = credentials
        self.supported_versions = supported_versions
        self.stateless = STATELESS_VERSION in supported_versions
        choices = [v for v in LEGACY_VERSIONS if not supported_versions or v in supported_versions]
        if not self.stateless and not choices:
            raise ValueError("No implemented MCP protocol advertised")
        self.version = STATELESS_VERSION if self.stateless else choices[0]
        self.client = client or httpx.Client(
            verify=True, trust_env=False, timeout=60, follow_redirects=False
        )
        self.signing_name = Session().get_service_model("bedrock-agentcore").metadata["signingName"]
        self._initialized = self.stateless
        self._session: str | None = None
        self.http_calls = 0

    def close(self) -> None:
        self.client.close()

    def rpc(self, method: str, params: dict) -> dict:
        if method not in {"tools/list", "tools/call"}:
            raise ValueError("Only bounded tool discovery and calls are supported")
        if not self._initialized:
            initialized = self._send(
                "initialize",
                {"protocolVersion": self.version, "capabilities": {}, "clientInfo": CLIENT_INFO},
            )
            selected = initialized.get("protocolVersion")
            if selected not in LEGACY_VERSIONS or (
                self.supported_versions and selected not in self.supported_versions
            ):
                raise ValueError("Server negotiated an unsupported MCP protocol")
            self.version = selected
            self._send("notifications/initialized", {}, notification=True)
            self._initialized = True
        return self._send(method, params)

    def _send(self, method: str, params: dict, *, notification: bool = False) -> dict:
        params = dict(params)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.version,
        }
        if self.stateless:
            headers["Mcp-Method"] = method
            if method == "tools/call":
                headers["Mcp-Name"] = params["name"]
            params["_meta"] = {
                "io.modelcontextprotocol/protocolVersion": self.version,
                "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        request_id = uuid4().hex
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            payload["id"] = request_id
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        credentials = self.credentials().get_frozen_credentials()
        if not credentials.token:
            raise RuntimeError("Temporary credentials are required")
        signed = AWSRequest(method="POST", url=self.endpoint, data=raw, headers=headers)
        SigV4Auth(credentials, self.signing_name, REGION).add_auth(signed)
        self.http_calls += 1
        started = time.monotonic()
        try:
            with self.client.stream(
                "POST", self.endpoint, content=raw, headers=dict(signed.headers)
            ) as response:
                if response.status_code not in (200, 202, 204):
                    raise RuntimeError(f"MCP_HTTP_{response.status_code}")
                if method == "initialize":
                    self._session = response.headers.get("mcp-session-id")
                if notification:
                    return {}
                chunks = bytearray()
                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise ValueError("MCP response exceeded local size limit")
                    if time.monotonic() - started > 60:
                        raise RuntimeError("MCP_RESPONSE_DEADLINE_EXCEEDED")
                    if content_type == "text/event-stream":
                        normalized = bytes(chunks).replace(b"\r\n", b"\n")
                        boundary = normalized.rfind(b"\n\n")
                        if boundary >= 0:
                            result = _decode_response(
                                normalized[: boundary + 2],
                                content_type,
                                request_id,
                                allow_pending=True,
                            )
                            if result is not None:
                                return result
        except httpx.HTTPError as exc:
            raise RuntimeError(f"MCP_TRANSPORT_{type(exc).__name__}") from None
        return _decode_response(bytes(chunks), content_type, request_id)


def _decode_response(
    raw: bytes, content_type: str, request_id: str, *, allow_pending: bool = False
) -> dict | None:
    try:
        if content_type == "application/json":
            envelopes = [json.loads(raw)]
        elif content_type == "text/event-stream":
            envelopes, data = [], []
            for line in (raw.decode("utf-8") + "\n\n").splitlines():
                if line.startswith("data:"):
                    data.append(line[5:].removeprefix(" "))
                elif not line and data:
                    envelopes.append(json.loads("\n".join(data)))
                    data = []
        else:
            raise ValueError("Unsupported MCP response content type")
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("Malformed MCP JSON response") from None
    matching = [e for e in envelopes if isinstance(e, dict) and e.get("id") == request_id]
    if (
        not matching
        and allow_pending
        and all(
            isinstance(e, dict)
            and e.get("jsonrpc") == "2.0"
            and "id" not in e
            and isinstance(e.get("method"), str)
            for e in envelopes
        )
    ):
        return None
    if len(matching) != 1:
        raise ValueError("MCP response identifier mismatch")
    envelope = matching[0]
    if (
        envelope.get("jsonrpc") != "2.0"
        or "error" in envelope
        or not isinstance(envelope.get("result"), dict)
    ):
        raise ValueError("MCP error or malformed response envelope")
    return envelope["result"]


def _aws_json(arguments: list[str]) -> dict:
    executable = shutil.which("aws")
    if executable is None:
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Amazon/AWSCLIV2/aws.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Amazon/AWSCLIV2/aws.exe",
        ]
        executable = next((str(p) for p in candidates if p.is_file()), None)
    if executable is None:
        raise RuntimeError("AWS_CLI_UNAVAILABLE")
    try:
        result = subprocess.run(
            [executable, *arguments, "--profile", PROFILE, "--region", REGION, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={**os.environ, "AWS_MAX_ATTEMPTS": "1", "AWS_PAGER": ""},
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("AWS_CLI_UNAVAILABLE_OR_TIMEOUT") from None
    if result.returncode:
        # stderr may contain account identifiers, private ARNs or credential details.
        raise RuntimeError("AWS_PROFILE_READ_OR_AUTH_FAILED")
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except ValueError:
        raise RuntimeError("AWS_CLI_INVALID_RESPONSE") from None


def _temporary_credentials() -> Credentials:
    data = _aws_json(["configure", "export-credentials", "--format", "process"])
    try:
        expiry = datetime.fromisoformat(data["Expiration"].replace("Z", "+00:00"))
        if not data.get("SessionToken") or expiry <= datetime.now(UTC):
            raise ValueError
        return Credentials(data["AccessKeyId"], data["SecretAccessKey"], data["SessionToken"])
    except (KeyError, ValueError, TypeError):
        raise RuntimeError("Valid temporary AWS login credentials required") from None


@contextmanager
def open_gateway_transport(*, mode: RuntimeMode, gateway_id: str) -> Iterator[GatewayMcpTransport]:
    if RuntimeMode(mode) is not RuntimeMode.LIVE:
        raise ProviderBoundaryError("AWS transport requires explicit LIVE mode")
    if not re.fullmatch(r"qualor-opportunity-gateway-[a-z0-9]+", gateway_id):
        raise ValueError("Explicit QUALOR Gateway ID required")
    _temporary_credentials()
    identity = _aws_json(["sts", "get-caller-identity"])
    if not identity.get("Arn", "").endswith(":user/qualor-dev-user"):
        raise RuntimeError("Expected non-root QUALOR development IAM user")
    gateway = _aws_json(
        ["bedrock-agentcore-control", "get-gateway", "--gateway-identifier", gateway_id]
    )
    if (
        gateway.get("status") != "READY"
        or gateway.get("protocolType") != "MCP"
        or gateway.get("authorizerType") != "AWS_IAM"
        or gateway.get("name") != "qualor-opportunity-gateway"
    ):
        raise RuntimeError("Expected READY QUALOR MCP AWS_IAM Gateway")
    tags = _aws_json(
        [
            "bedrock-agentcore-control",
            "list-tags-for-resource",
            "--resource-arn",
            gateway["gatewayArn"],
        ]
    ).get("tags")
    if tags != {"Project": "QUALOR", "Environment": "hackathon", "Owner": "BrenychStudio"}:
        raise RuntimeError("Gateway ownership tags mismatch")
    versions = (
        (gateway.get("protocolConfiguration") or {}).get("mcp", {}).get("supportedVersions", [])
    )
    transport = GatewayMcpTransport(
        mode=mode,
        endpoint=gateway["gatewayUrl"],
        supported_versions=tuple(versions),
        credentials=_temporary_credentials,
    )
    try:
        yield transport
    finally:
        transport.close()
