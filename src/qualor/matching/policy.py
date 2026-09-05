"""Versioned deterministic project matching rubric."""

MATCH_POLICY_VERSION = 1
STRONG_THRESHOLD = 75
PARTIAL_THRESHOLD = 50
FACTOR_COUNT = 7


def comparable_score(ratings: tuple[int, ...]) -> int:
    return (sum(ratings) * 50 + FACTOR_COUNT) // (2 * FACTOR_COUNT)
