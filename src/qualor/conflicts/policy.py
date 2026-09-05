"""Versioned explicit policy; no license compatibility or legal interpretation."""

from qualor.domain.enums import Category, SourceType

from .model import ConflictCategory

CONFLICT_POLICY_VERSION = 1
EVIDENCE_CATEGORY = {
    category: {
        ConflictCategory.LICENSE: Category.LICENSE,
        ConflictCategory.SPONSOR_SUPPORT: Category.FINANCIAL_SUPPORT,
    }.get(category, Category.PROJECT_POLICY)
    for category in ConflictCategory
}
ACCEPTABLE_SOURCES = frozenset(
    {
        SourceType.OFFICIAL_RULES,
        SourceType.OFFICIAL_FAQ,
        SourceType.OFFICIAL_APPLICATION,
        SourceType.SYNTHETIC_FIXTURE,
    }
)
