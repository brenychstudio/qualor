"""Explicit owner-supplied facts; no private repository discovery or inferred traction."""

from typing import Self

from pydantic import StrictBool, model_validator

from .base import CalendarDate, Fact, NonEmpty, PositiveInt, Record, UtcInstant
from .enums import CodeProvenance, LegalForm, ProjectStage
from .money import Money, NonNegativeDecimal
from .planning import MaterialReadiness


class FounderProfile(Record):
    country_of_residence: Fact[NonEmpty] = Fact()
    citizenship: Fact[NonEmpty] = Fact()
    legal_form: Fact[LegalForm] = Fact()
    incorporation_date: Fact[CalendarDate] = Fact()
    team_size: Fact[PositiveInt] = Fact()
    available_hours: Fact[NonNegativeDecimal] = Fact()
    max_cash_commitment: Fact[Money] = Fact()
    open_source_willingness: Fact[StrictBool] = Fact()
    strategic_goals: Fact[tuple[NonEmpty, ...]] = Fact()
    constraints: tuple[NonEmpty, ...] = ()
    verified_at: UtcInstant | None = None


class ProjectProfile(Record):
    name: NonEmpty
    problem: Fact[NonEmpty] = Fact()
    audience: Fact[NonEmpty] = Fact()
    stage: Fact[ProjectStage] = Fact()
    available_features: Fact[tuple[NonEmpty, ...]] = Fact()
    technology_stack: Fact[tuple[NonEmpty, ...]] = Fact()
    code_provenance: Fact[CodeProvenance] = Fact()
    is_new_project: Fact[StrictBool] = Fact()
    license_intent: Fact[NonEmpty] = Fact()
    prior_submissions: Fact[tuple[NonEmpty, ...]] = Fact()
    public_evidence_refs: tuple[NonEmpty, ...] = ()
    estimated_adaptation_hours: Fact[NonNegativeDecimal] = Fact()
    has_sponsor_support: Fact[StrictBool] = Fact()
    reward_conditions_met: Fact[StrictBool] = Fact()
    facts_verified_at: UtcInstant | None = None

    material_readiness: tuple[MaterialReadiness, ...] = ()
    project_lineage: Fact[tuple[NonEmpty, ...]] = Fact()
    reused_components: Fact[tuple[NonEmpty, ...]] = Fact()
    reuse_disclosed: Fact[StrictBool] = Fact()

    @model_validator(mode="after")
    def unique_materials(self) -> Self:
        if len({m.kind for m in self.material_readiness}) != len(self.material_readiness):
            raise ValueError("Duplicate material readiness facts")
        return self
