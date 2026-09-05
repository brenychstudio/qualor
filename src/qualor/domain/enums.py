"""Bounded domain vocabulary; unknown is never an affirmative fact."""

from enum import StrEnum


class Provenance(StrEnum):
    USER_ASSERTED = "USER_ASSERTED"
    DOCUMENTED = "DOCUMENTED"
    UNKNOWN = "UNKNOWN"


class LegalForm(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    SOLE_TRADER = "SOLE_TRADER"
    INCORPORATED_COMPANY = "INCORPORATED_COMPANY"
    NONPROFIT = "NONPROFIT"
    UNKNOWN = "UNKNOWN"


class ProjectStage(StrEnum):
    IDEA = "IDEA"
    PROTOTYPE = "PROTOTYPE"
    MVP = "MVP"
    PRODUCTION = "PRODUCTION"
    UNKNOWN = "UNKNOWN"


class CodeProvenance(StrEnum):
    ORIGINAL = "ORIGINAL"
    REUSED = "REUSED"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class RewardKind(StrEnum):
    CASH_PRIZE = "CASH_PRIZE"
    CLOUD_CREDIT = "CLOUD_CREDIT"
    GRANT = "GRANT"
    EQUITY_INVESTMENT = "EQUITY_INVESTMENT"
    IN_KIND = "IN_KIND"


class OpportunityStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    OFFICIAL_RULES = "OFFICIAL_RULES"
    OFFICIAL_FAQ = "OFFICIAL_FAQ"
    OFFICIAL_APPLICATION = "OFFICIAL_APPLICATION"
    OFFICIAL_ANNOUNCEMENT = "OFFICIAL_ANNOUNCEMENT"
    OTHER_OFFICIAL = "OTHER_OFFICIAL"
    THIRD_PARTY = "THIRD_PARTY"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    SEARCH_SNIPPET = "SEARCH_SNIPPET"


class ExtractionState(StrEnum):
    REVIEWED = "REVIEWED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"


class Category(StrEnum):
    DEADLINE = "DEADLINE"
    ENTRANT_TYPE = "ENTRANT_TYPE"
    GEOGRAPHY = "GEOGRAPHY"
    LEGAL_ENTITY = "LEGAL_ENTITY"
    PROJECT_POLICY = "PROJECT_POLICY"
    LICENSE = "LICENSE"
    REQUIRED_TECHNOLOGY = "REQUIRED_TECHNOLOGY"
    FINANCIAL_SUPPORT = "FINANCIAL_SUPPORT"
    REWARD_CONDITIONS = "REWARD_CONDITIONS"


class Operator(StrEnum):
    EQ = "EQ"
    IN = "IN"
    GTE = "GTE"
    LTE = "LTE"
    BETWEEN = "BETWEEN"
    DATE_BETWEEN = "DATE_BETWEEN"
    BOOL_IS = "BOOL_IS"
    AND = "AND"
    OR = "OR"


class Criticality(StrEnum):
    CRITICAL = "CRITICAL"
    NON_CRITICAL = "NON_CRITICAL"


class RuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GateState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CoverageState(StrEnum):
    EVALUATED = "EVALUATED"
    NOT_APPLICABLE_WITH_REASON = "NOT_APPLICABLE_WITH_REASON"
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"


class FreshnessStatus(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ReasonCode(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING_FACT = "MISSING_FACT"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_OPERANDS = "INVALID_OPERANDS"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    UNVERIFIED_EVIDENCE = "UNVERIFIED_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    CONFLICT = "CONFLICT"
    PROVENANCE_REQUIRED = "PROVENANCE_REQUIRED"
    EXPLICIT_NOT_APPLICABLE = "EXPLICIT_NOT_APPLICABLE"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    EMPTY_RULE_SET = "EMPTY_RULE_SET"
    CRITICAL_UNKNOWN = "CRITICAL_UNKNOWN"


class SubjectReference(StrEnum):
    RESIDENCE = "founder.country_of_residence"
    CITIZENSHIP = "founder.citizenship"
    LEGAL_FORM = "founder.legal_form"
    INCORPORATION_DATE = "founder.incorporation_date"
    TEAM_SIZE = "founder.team_size"
    OPEN_SOURCE = "founder.open_source_willingness"
    NEW_PROJECT = "project.is_new_project"
    LICENSE = "project.license_intent"
    REQUIRED_TECHNOLOGY = "project.technology_stack"
    FINANCIAL_SUPPORT = "project.has_sponsor_support"
    REWARD_CONDITIONS = "project.reward_conditions_met"
    EVALUATED_AT = "context.evaluated_at"
