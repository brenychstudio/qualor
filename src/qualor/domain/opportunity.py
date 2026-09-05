"""Network-free identity and metadata normalization."""

import hashlib
import json
import unicodedata
from typing import Annotated, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AfterValidator, model_validator

from .base import CalendarDate, NonEmpty, Record, UtcInstant
from .enums import OpportunityStatus
from .money import Reward


def validate_source_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username:
        raise ValueError("Only credential-free HTTP(S) source URLs are supported")
    return value


def normalize_url(value: str) -> str:
    parts = urlsplit(validate_source_url(value))
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}
    ]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urlencode(query), ""))


SourceUrl = Annotated[NonEmpty, AfterValidator(normalize_url)]
OriginalSourceUrl = Annotated[NonEmpty, AfterValidator(validate_source_url)]


def opportunity_identity(organizer: str, program_name: str, edition: str) -> str:
    parts = [
        " ".join(unicodedata.normalize("NFKC", part).casefold().split())
        for part in (organizer, program_name, edition)
    ]
    return "opp_" + hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


class OpportunityRecord(Record):
    organizer: NonEmpty
    program_name: NonEmpty
    edition: NonEmpty
    canonical_rules_url: SourceUrl
    application_url: SourceUrl | None = None
    tracks: tuple[NonEmpty, ...] = ()
    deadlines: tuple[CalendarDate | UtcInstant, ...] = ()
    geographic_scope: NonEmpty | None = None
    rewards: tuple[Reward, ...] = ()
    deliverables: tuple[NonEmpty, ...] = ()
    source_versions: tuple[NonEmpty, ...] = ()
    status: OpportunityStatus = OpportunityStatus.UNKNOWN

    @model_validator(mode="after")
    def canonical_identity(self) -> Self:
        object.__setattr__(
            self, "id", opportunity_identity(self.organizer, self.program_name, self.edition)
        )
        return self
