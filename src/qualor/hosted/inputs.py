"""Operator-owned demo facts and untrusted URL admission."""

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from qualor.domain.base import Fact
from qualor.domain.opportunity import normalize_url
from qualor.runtime.run_models import StudioInput
from qualor.runtime.sources import resolve_host, validate_destination

DEFAULT_GOAL = "Research this opportunity for QUALOR using official evidence."


def admit_url(value: str, *, resolver=resolve_host) -> tuple[str, str]:
    # Reject ambiguous URL encodings before parsing/canonicalization can erase them.
    if any(ord(char) <= 32 or ord(char) == 127 for char in value) or "\\" in value:
        raise ValueError("INVALID_OPPORTUNITY_URL")
    parts = urlsplit(value)
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
    ):
        raise ValueError("INVALID_OPPORTUNITY_URL")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        host = host.encode("idna").decode("ascii").lower()
        if (
            host.endswith(".")
            or "." not in host
            or host.endswith((".localhost", ".local"))
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                for part in host.split(".")
            )
        ):
            raise ValueError("INVALID_OPPORTUNITY_URL") from None
    else:
        if not address.is_global:
            raise ValueError("INVALID_OPPORTUNITY_URL")
        # IP literals are not candidate official hostnames for this demo.
        raise ValueError("OFFICIAL_HOSTNAME_REQUIRED")
    canonical = normalize_url(urlunsplit(("https", host, parts.path or "/", parts.query, "")))
    validate_destination(canonical, (host,), resolver=resolver)
    return canonical, host


def load_demo_profile(path) -> StudioInput:
    """Use existing StudioInput file format; private founder facts never enter this demo."""
    with path.open("rb") as stream:
        data = stream.read(100_001)
    if len(data) > 100_000:
        raise ValueError("HOSTED_DEMO_PROFILE_INVALID")
    raw = StudioInput.model_validate_json(data)
    if len(raw.projects) != 1 or raw.projects[0].project.name != "QUALOR":
        raise ValueError("HOSTED_DEMO_REQUIRES_ONE_QUALOR_PROJECT")
    founder = raw.founder.model_copy(
        update={
            "id": "hosted-demo-founder",
            "country_of_residence": Fact(),
            "citizenship": Fact(),
            "incorporation_date": Fact(),
            "available_hours": Fact(),
            "max_cash_commitment": Fact(),
            "strategic_goals": Fact(),
            "constraints": (),
        }
    )
    project = raw.projects[0].project.model_copy(update={"id": "hosted-demo-qualor"})
    return StudioInput(
        schema_version="1",
        sanitized=True,
        goal=DEFAULT_GOAL,
        allowed_hosts=("example.invalid",),
        founder=founder,
        projects=(raw.projects[0].model_copy(update={"project": project}),),
    )
