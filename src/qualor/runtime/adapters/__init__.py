"""Category-only semantic adapter dispatch."""

from .base import AdapterResult, SemanticAdapter
from .deadline import DeadlineAdapter
from .entrant_type import EntrantTypeAdapter
from .financial_support import FinancialSupportAdapter
from .geography import GeographyRuleAdapter
from .legal_entity import LegalEntityAdapter
from .license import LicenseAdapter
from .project_policy import ProjectPolicyAdapter
from .reward_conditions import RewardConditionAdapter
from .technology import TechnologyRequirementAdapter


def adapt_candidate(candidate, *, evaluated_at) -> AdapterResult:
    adapters = {
        "DEADLINE": DeadlineAdapter,
        "ENTRANT_TYPE": EntrantTypeAdapter,
        "GEOGRAPHY": GeographyRuleAdapter,
        "LEGAL_ENTITY": LegalEntityAdapter,
        "PROJECT_POLICY": ProjectPolicyAdapter,
        "LICENSE": LicenseAdapter,
        "REQUIRED_TECHNOLOGY": TechnologyRequirementAdapter,
        "FINANCIAL_SUPPORT": FinancialSupportAdapter,
        "REWARD_CONDITIONS": RewardConditionAdapter,
    }
    return adapters[candidate.candidate.category]().compile(candidate, evaluated_at=evaluated_at)


__all__ = ["AdapterResult", "SemanticAdapter", "adapt_candidate"]
