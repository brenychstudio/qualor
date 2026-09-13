"""Explicit source dates with independently resolved, unambiguous timezones."""

import re
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from qualor.domain.enums import Operator, SubjectReference
from qualor.domain.values import InstantValue
from qualor.runtime.normalization import parse_absolute_deadline

from .base import Compiler, body, fullmatch

_MONTHS = (
    "January February March April May June July August September October November December".split()
)
_WEEKDAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()


def parse_dated_instant(text: str) -> datetime | None:
    if text.endswith("-00:00"):
        return None  # RFC3339 unknown local offset is not UTC authority.
    if instant := parse_absolute_deadline(text):
        return instant
    match = fullmatch(
        r"(?:(?P<weekday>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? )?"
        r"(?P<month>[A-Za-z]+) (?P<day>\d{1,2}),? (?P<year>\d{4})(?: at|,) "
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?"
        r"(?: (?P<ampm>AM|PM))? (?P<zone>.+)",
        text,
    )
    if not match:
        return None
    try:
        month = [name.casefold() for name in _MONTHS].index(match["month"].casefold()) + 1
        hour = int(match["hour"])
        if match["ampm"]:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if match["ampm"].upper() == "PM" else 0)
        local = datetime(
            int(match["year"]),
            month,
            int(match["day"]),
            hour,
            int(match["minute"]),
            int(match["second"] or 0),
        )
        if (
            match["weekday"]
            and _WEEKDAYS[local.weekday()].casefold() != match["weekday"].casefold()
        ):
            return None
        zone = match["zone"]
        if zone.upper() == "UTC":
            return local.replace(tzinfo=UTC)
        offset = fullmatch(r"(?:UTC)?([+-])(\d{2}):(\d{2})", zone)
        if offset:
            hours, minutes = int(offset[2]), int(offset[3])
            if hours > 23 or minutes > 59 or (offset[1] == "-" and hours == minutes == 0):
                return None
            delta = timedelta(hours=hours, minutes=minutes) * (1 if offset[1] == "+" else -1)
            return local.replace(tzinfo=timezone(delta)).astimezone(UTC)
        if zone.casefold() in {"pacific time", "us pacific time"}:
            zone = "America/Los_Angeles"
        elif not re.fullmatch(r"[A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?", zone):
            return None
        tz = ZoneInfo(zone)
        instants = set()
        for fold in (0, 1):
            aware = local.replace(tzinfo=tz, fold=fold)
            instant = aware.astimezone(UTC)
            if instant.astimezone(tz).replace(tzinfo=None) == local:
                instants.add(instant)
        return instants.pop() if len(instants) == 1 else None
    except (ValueError, ZoneInfoNotFoundError):
        return None


class DeadlineAdapter:
    def compile(self, candidate, *, evaluated_at):
        c = Compiler(candidate, evaluated_at)
        if early := c.early():
            return early
        text = body(candidate)
        interval = fullmatch(
            r"(?:Submissions are accepted|Submission period is) from (.+) to (.+)", text
        )
        closing = fullmatch(
            r"(?:The )?deadline(?::| is) (.+)|Submissions close (?:on |at )?(.+)", text
        )
        if interval:
            source_values = (interval[1], interval[2])
        elif closing:
            source_values = (next(value for value in closing.groups() if value),)
        else:
            return c.finish(c.unresolved("DEADLINE_SHAPE_UNSUPPORTED"))
        instants = tuple(parse_dated_instant(value) for value in source_values)
        if any(value is None for value in instants) or (
            len(instants) == 2 and instants[0] > instants[1]
        ):
            return c.finish(c.unresolved("DEADLINE_TIMEZONE_OR_DATE_AMBIGUOUS"), status="AMBIGUOUS")
        proposed = candidate.candidate.proposed_value
        proposed_values = proposed if isinstance(proposed, tuple) else (proposed,)
        if (
            len(proposed_values) != len(instants)
            or tuple(parse_dated_instant(v) for v in proposed_values) != instants
        ):
            return c.finish(c.unresolved("DEADLINE_PROPOSAL_SOURCE_MISMATCH"))
        operands = tuple(InstantValue(value=value) for value in instants)
        value = tuple(instant.isoformat() for instant in instants)
        if interval:
            rule = c.rule(Operator.DATE_BETWEEN, SubjectReference.EVALUATED_AT, operands)
        else:
            value = value[0]
            rule = c.unresolved("DEADLINE_OPENING_BOUND_ABSENT", operands=operands)
        result = c.finish(rule, value=value, status="SUPPORTED", interpreted=True)
        if result.normalization_status != "SUPPORTED":
            result = result.model_copy(update={"normalized_value": None})
        return result
