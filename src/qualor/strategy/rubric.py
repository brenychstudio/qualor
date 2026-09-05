"""Explicit factor rubric: no absent fact is an average rating.

Product fit consumes the matching rating. Readiness is READY=4,
GAPS_EXECUTABLE=3, NOT_READY=0. Time and affordability are sufficient=4,
insufficient=0. Strategic value is floor(4 * covered distinct goals / goals).
Label comparison uses Unicode normalization, case folding and whitespace only.
"""

import unicodedata


def _goal_coverage(goals: tuple[str, ...] | None, benefits: tuple[str, ...] | None) -> int | None:
    if goals is None:
        return None
    if not goals:
        return 0
    if benefits is None:
        return None

    def normalize(value: str) -> str:
        return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

    expected = {normalize(g) for g in goals}
    supplied = {normalize(b) for b in benefits}
    return 4 * len(expected & supplied) // len(expected)
