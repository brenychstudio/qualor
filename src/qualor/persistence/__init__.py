"""Local SQLite persistence primitives."""

from .database import Database
from .migrations import UnsupportedSchemaError, migrate
from .repositories import (
    ApprovalRepository,
    CorruptRecordError,
    DecisionRepository,
    DraftPackRepository,
    EvidenceRepository,
    InvalidReferenceError,
    OpportunityRepository,
    ProfileRepository,
    ProjectRepository,
    RepositoryConflictError,
    RepositoryError,
    RunRepository,
    TransactionRequiredError,
)

__all__ = [
    "ApprovalRepository",
    "CorruptRecordError",
    "Database",
    "DecisionRepository",
    "DraftPackRepository",
    "EvidenceRepository",
    "InvalidReferenceError",
    "OpportunityRepository",
    "ProfileRepository",
    "ProjectRepository",
    "RepositoryConflictError",
    "RepositoryError",
    "RunRepository",
    "TransactionRequiredError",
    "UnsupportedSchemaError",
    "migrate",
]
