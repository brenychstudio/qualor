"""Versioned timestamp-only freshness; failed refreshes never renew snapshots."""

from datetime import date, datetime, timedelta

from qualor.domain.enums import FreshnessStatus

FRESHNESS_POLICY_VERSION = 1
DEFAULT_TTL = timedelta(hours=24)
NEAR_DEADLINE_TTL = timedelta(hours=6)
NEAR_DEADLINE_WINDOW = timedelta(hours=72)


def evaluate_freshness(
    retrieved_at: datetime, evaluated_at: datetime, deadline: date | datetime | None = None
) -> FreshnessStatus:
    for instant in (retrieved_at, evaluated_at):
        if not isinstance(instant, datetime) or instant.utcoffset() is None:
            raise ValueError("Freshness requires timezone-aware instants")
    ttl = DEFAULT_TTL
    if isinstance(deadline, datetime):
        if deadline.utcoffset() is None:
            raise ValueError("An exact deadline requires a timezone")
        if deadline - evaluated_at < NEAR_DEADLINE_WINDOW:
            ttl = NEAR_DEADLINE_TTL
    elif deadline is not None:
        ttl = NEAR_DEADLINE_TTL
    age = evaluated_at - retrieved_at
    if age < timedelta(0):
        return FreshnessStatus.UNKNOWN
    return FreshnessStatus.FRESH if age < ttl else FreshnessStatus.STALE
