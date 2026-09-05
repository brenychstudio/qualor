"""Explicit submission conflicts with scoped, qualified outcomes."""

from enum import StrEnum
from typing import Literal

from pydantic import StrictBool

from qualor.domain.base import (
    CalendarDate,
    Contract,
    Fact,
    NonEmpty,
    Record,
    UtcInstant,
)
from qualor.domain.enums import CodeProvenance, Provenance


class ConflictCategory(StrEnum):
    NEW_PROJECT = "NEW_PROJECT"
    EXCLUSIVE_SUBMISSION = "EXCLUSIVE_SUBMISSION"
    LICENSE = "LICENSE"
    SPONSOR_SUPPORT = "SPONSOR_SUPPORT"
    SAME_PROJECT = "SAME_PROJECT"
    EXISTING_PROJECT = "EXISTING_PROJECT"
    DISCLOSURE = "DISCLOSURE"


class ConflictStatus(StrEnum):
    BLOCKED_BY_EXPLICIT_RULE = "BLOCKED_BY_EXPLICIT_RULE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_CONFLICT_DETECTED_IN_CHECKED_RULES = "NO_CONFLICT_DETECTED_IN_CHECKED_RULES"


class ConflictRule(Contract):
    id: NonEmpty
    category: ConflictCategory
    applies: Fact[StrictBool] = Fact()
    supported: StrictBool
    evidence_ids: tuple[NonEmpty, ...] = ()
    allowed_licenses: Fact[tuple[NonEmpty, ...]] = Fact()


class ActiveSubmission(Record):
    contest: NonEmpty
    project_id: NonEmpty
    project_lineage: Fact[tuple[NonEmpty, ...]] = Fact()
    code_origin: Fact[CodeProvenance] = Fact()
    sponsor_support: Fact[StrictBool] = Fact()
    submission_dates: tuple[CalendarDate | UtcInstant, ...] = ()
    license: Fact[NonEmpty] = Fact()
    reused_components: Fact[tuple[NonEmpty, ...]] = Fact()
    rules_evidence_refs: tuple[NonEmpty, ...] = ()
    facts_provenance: Provenance
    conflict_rules: tuple[ConflictRule, ...] = ()


class ConflictAssessment(Contract):
    status: ConflictStatus
    checked_rule_categories: tuple[tuple[NonEmpty, ConflictCategory], ...]
    missing_rule_categories: tuple[tuple[NonEmpty, ConflictCategory], ...]
    evidence_ids: tuple[NonEmpty, ...]
    reasons: tuple[NonEmpty, ...]
    evaluated_at: UtcInstant
    policy_version: Literal[1] = 1
