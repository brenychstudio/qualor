"""Operator-scoped HTTPS fetching with DNS-pinned connections and retained source identity."""

import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit

from pydantic import Field

from qualor.domain.base import Contract, NonEmpty, UtcInstant
from qualor.domain.enums import SourceType

from .budget import LiveBudgetGuard, LiveCallKind
from .mode import ProviderBoundaryError, RuntimeMode
from .providers import FetchRequest

MAX_SOURCE_BYTES = 1_000_000
MAX_SOURCE_CHARACTERS = 60_000
SOURCE_DEADLINE_SECONDS = 30
AUTHORITY_PRIORITY = (
    SourceType.OFFICIAL_RULES,
    SourceType.OFFICIAL_APPLICATION,
    SourceType.OFFICIAL_FAQ,
    SourceType.OTHER_OFFICIAL,
    SourceType.THIRD_PARTY,
)


class SourceDocument(Contract):
    id: NonEmpty
    original_url: NonEmpty
    final_url: NonEmpty
    retrieved_at: UtcInstant
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority: SourceType
    content_type: NonEmpty = "text/plain"
    text: str = Field(min_length=1, max_length=MAX_SOURCE_CHARACTERS)
    truncated: bool = False


def resolve_host(host: str) -> list[str]:
    return list(
        dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
    )


def validate_destination(url: str, allowed_hosts: tuple[str, ...], resolver=resolve_host) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or not host
        or parts.username
        or parts.password
        or parts.port not in (None, 443)
        or parts.fragment
        or any(ord(c) < 33 for c in url)
        or not any(host == d or host.endswith("." + d) for d in allowed_hosts)
    ):
        raise ValueError("SOURCE_URL_NOT_AUTHORIZED")
    addresses = resolver(host)
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("SOURCE_ADDRESS_NOT_PUBLIC")
    # Only vetted numeric addresses reach connect; DNS cannot rebind during connection.
    return sorted(addresses, key=lambda a: (ipaddress.ip_address(a).version, a))[0]


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        super().__init__(host, timeout=20, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def request_public(url: str, address: str) -> tuple[int, dict, bytes]:
    parts = urlsplit(url)
    connection = _PinnedHTTPS(parts.hostname, address)
    deadline = None
    try:
        # Connect/TLS each retain their socket timeout. The request/header/body
        # deadline actively interrupts blocked reads, including trickle responses.
        connection.connect()
        deadline_socket = connection.sock
        expired = threading.Event()

        def interrupt():
            expired.set()
            try:
                deadline_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        deadline = threading.Timer(SOURCE_DEADLINE_SECONDS, interrupt)
        deadline.daemon = True
        started = time.monotonic()
        deadline.start()
        path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
        connection.request(
            "GET",
            path,
            headers={
                "User-Agent": "QUALOR/0.0.1 (bounded official-source research)",
                "Accept": "text/html, application/json, text/plain",
                "Accept-Encoding": "identity",
            },
        )
        response = connection.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        if headers.get("content-encoding", "identity") != "identity":
            raise ValueError("UNSUPPORTED_SOURCE_ENCODING")
        body = bytearray()
        while chunk := response.read(8192):
            body.extend(chunk)
            if (
                len(body) > MAX_SOURCE_BYTES
                or expired.is_set()
                or time.monotonic() - started > SOURCE_DEADLINE_SECONDS
            ):
                raise ValueError("SOURCE_SIZE_OR_TIME_LIMIT")
        if expired.is_set():
            raise ValueError("SOURCE_SIZE_OR_TIME_LIMIT")
        return response.status, headers, bytes(body)
    finally:
        if deadline is not None:
            deadline.cancel()
        connection.close()


class _ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(" ".join(data.split()))


def canonical_source_text(body: bytes, content_type: str) -> tuple[str, bool]:
    """Return the retained canonical text using the fetcher's existing parser rules."""

    text = body.decode("utf-8", errors="replace")
    if content_type == "text/html":
        parser = _ReadableHTML()
        parser.feed(text)
        text = "\n".join(parser.parts)
    elif content_type == "application/json":
        text = json.dumps(json.loads(text), ensure_ascii=False)
    return text[:MAX_SOURCE_CHARACTERS], len(text) > MAX_SOURCE_CHARACTERS


def source_authority(url: str, allowed_hosts: tuple[str, ...]) -> SourceType:
    host, path = urlsplit(url).hostname or "", urlsplit(url).path.lower().rstrip("/")
    if not any(host == d or host.endswith("." + d) for d in allowed_hosts):
        return SourceType.THIRD_PARTY
    if path.endswith("/rules") or path.endswith("/official-rules"):
        return SourceType.OFFICIAL_RULES
    if path.endswith(("/faq", "/faqs")):
        return SourceType.OFFICIAL_FAQ
    if path.endswith(("/application", "/apply")):
        return SourceType.OFFICIAL_APPLICATION
    return SourceType.OTHER_OFFICIAL


class OfficialSourceFetcher:
    def __init__(
        self,
        *,
        mode: RuntimeMode,
        allowed_hosts: tuple[str, ...],
        budget: LiveBudgetGuard,
        resolver=resolve_host,
        request=request_public,
    ):
        if RuntimeMode(mode) != RuntimeMode.LIVE:
            raise ProviderBoundaryError("Network fetcher requires LIVE mode")
        self.allowed_hosts, self.budget = allowed_hosts, budget
        self.resolver, self.request = resolver, request

    def fetch(self, request: FetchRequest) -> SourceDocument:
        original = request.url
        current = urldefrag(original).url
        address = validate_destination(current, self.allowed_hosts, self.resolver)
        receipt = self.budget.reserve(LiveCallKind.FETCH)
        for redirect in range(4):
            status, headers, body = self.request(current, address)
            if status in {301, 302, 303, 307, 308}:
                if redirect == 3 or not headers.get("location"):
                    raise ValueError("SOURCE_REDIRECT_LIMIT")
                current = urljoin(current, headers["location"])
                address = validate_destination(current, self.allowed_hosts, self.resolver)
                continue
            if status != 200:
                raise ValueError(f"SOURCE_HTTP_{status}")
            mime = headers.get("content-type", "").split(";")[0].lower().strip()
            if mime not in {"text/html", "application/json", "text/plain"}:
                raise ValueError("UNSUPPORTED_SOURCE_TYPE")
            if len(body) > MAX_SOURCE_BYTES:
                raise ValueError("SOURCE_SIZE_LIMIT")
            text, truncated = canonical_source_text(body, mime)
            digest = hashlib.sha256(body).hexdigest()
            source = SourceDocument(
                id="source_" + hashlib.sha256(current.encode()).hexdigest()[:20],
                original_url=original,
                final_url=current,
                retrieved_at=datetime.now(UTC),
                content_hash=digest,
                authority=source_authority(current, self.allowed_hosts),
                content_type=mime,
                text=text,
                truncated=truncated,
            )
            self.budget.commit(receipt)
            return source
        raise ValueError("SOURCE_REDIRECT_LIMIT")
