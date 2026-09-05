"""Versioned conservative preparation policy."""

EFFORT_POLICY_VERSION = 1
# No foreign-exchange inference. V1 supports these explicit cash denominations.
SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "GBP"})
