"""Narrow URL identity and safe diagnostic rendering for discovery capabilities."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from .providers import SearchCandidate

CandidateProvenance = Literal[
    "SEARCH_CANDIDATE_EXACT",
    "SEARCH_CANDIDATE_CANONICAL_EQUIVALENT",
]


@dataclass(frozen=True)
class RegisteredCandidate:
    candidate_id: str
    observation: SearchCandidate
    fetch_url: str
    provenance: CandidateProvenance


def canonical_url_identity(url: str) -> str:
    """Return only equivalences safe for search-candidate registry identity."""

    parts = urlsplit(url)
    scheme = parts.scheme.casefold()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("CANDIDATE_URL_INVALID")
    if parts.username or parts.password:
        raise ValueError("CANDIDATE_URL_INVALID")
    try:
        host = parts.hostname.encode("idna").decode("ascii").casefold()
        port = parts.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("CANDIDATE_URL_INVALID") from exc
    if ":" in host:
        host = f"[{host}]"
    if port is not None and not (
        (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    ):
        host = f"{host}:{port}"
    return urlunsplit((scheme, host, parts.path or "/", parts.query, ""))


def sanitized_public_url(value: str) -> str | None:
    """Retain a public URL identity without query/fragment data for diagnostics."""

    try:
        parts = urlsplit(value)
        if parts.scheme.casefold() not in {"http", "https"} or not parts.hostname:
            return None
        host = parts.hostname.encode("idna").decode("ascii").casefold()
        if ":" in host:
            host = f"[{host}]"
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        return urlunsplit((parts.scheme.casefold(), host, parts.path or "/", "", ""))[:500]
    except (UnicodeError, ValueError):
        return None
