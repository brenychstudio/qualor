"""Public deterministic eligibility API."""

from .coverage import evaluate_coverage
from .engine import aggregate_eligibility, evaluate_rule, evaluate_rules
from .freshness import evaluate_freshness

__all__ = [
    "evaluate_rule",
    "evaluate_rules",
    "aggregate_eligibility",
    "evaluate_freshness",
    "evaluate_coverage",
]
