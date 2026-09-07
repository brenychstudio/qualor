"""Typed repositories scoped to a caller-owned SQLite transaction."""

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from qualor.decisions import DecisionRecord
from qualor.domain import EvidenceRecord, FounderProfile, OpportunityRecord, ProjectProfile
from qualor.runtime import RuntimeMode
from qualor.workspace.models import (
    ApprovalRecord,
    DraftJobRecord,
    DraftPack,
    RunEvent,
    RunEventPayload,
    RunRecord,
)


class RepositoryError(RuntimeError):
    """A bounded persistence failure safe to expose across service boundaries."""


class RepositoryConflictError(RepositoryError):
    """An immutable identity or uniqueness constraint already exists."""


class InvalidReferenceError(RepositoryError):
    """A required related record is missing."""


class TransactionRequiredError(RepositoryError):
    """A write was attempted outside a caller-owned transaction."""


class CorruptRecordError(RepositoryError):
    """Stored JSON or projected columns no longer match the typed record."""


def _json(model: BaseModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _load[ModelT: BaseModel](model: type[ModelT], value: str) -> ModelT:
    names = {
        OpportunityRecord: "opportunity version",
        RunRecord: "run",
        FounderProfile: "founder profile",
        ProjectProfile: "project profile",
        EvidenceRecord: "evidence",
        DecisionRecord: "decision",
        ApprovalRecord: "approval",
        DraftJobRecord: "draft job",
        DraftPack: "draft pack",
    }
    try:
        return model.model_validate_json(value)
    except (ValidationError, ValueError) as exc:
        raise CorruptRecordError(f"corrupt {names[model]} record") from exc


def _instant(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _require_projection(row: sqlite3.Row, model: BaseModel, **expected: Any) -> None:
    expected = {"id": model.id, "version": model.version, **expected}
    mismatches = {key: (row[key], value) for key, value in expected.items() if row[key] != value}
    if mismatches:
        name = (
            "opportunity version" if isinstance(model, OpportunityRecord) else type(model).__name__
        )
        words = re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()
        raise CorruptRecordError(f"corrupt {words} projected columns")


class _Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _require_transaction(self) -> None:
        if not self.connection.in_transaction:
            raise TransactionRequiredError("write requires an active caller-owned transaction")

    def _insert(self, statement: str, parameters: tuple[Any, ...], *, entity: str) -> None:
        self._require_transaction()
        try:
            self.connection.execute(statement, parameters)
        except sqlite3.IntegrityError as exc:
            if "FOREIGN KEY" in str(exc):
                raise InvalidReferenceError(f"invalid {entity} reference") from exc
            raise RepositoryConflictError(f"Conflicting immutable {entity} record") from exc


class ProfileRepository(_Repository):
    def put_founder(self, record: FounderProfile) -> None:
        self._require_transaction()
        record = FounderProfile.model_validate(record)
        self._insert(
            "INSERT INTO founder_profiles"
            "(id, version, record_json, created_at) VALUES (?, ?, ?, ?)",
            (record.id, record.version, _json(record), _instant(record.created_at)),
            entity="founder profile",
        )

    def get_founder(self, record_id: str, version: int) -> FounderProfile | None:
        row = self.connection.execute(
            "SELECT id, version, record_json, created_at FROM founder_profiles "
            "WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        if row is None:
            return None
        record = _load(FounderProfile, row["record_json"])
        _require_projection(row, record)
        return record


class ProjectRepository(_Repository):
    def put_project(self, record: ProjectProfile) -> None:
        self._require_transaction()
        record = ProjectProfile.model_validate(record)
        self._insert(
            "INSERT INTO project_profiles"
            "(id, version, record_json, created_at) VALUES (?, ?, ?, ?)",
            (record.id, record.version, _json(record), _instant(record.created_at)),
            entity="project profile",
        )

    def get_project(self, record_id: str, version: int) -> ProjectProfile | None:
        row = self.connection.execute(
            "SELECT id, version, record_json, created_at FROM project_profiles "
            "WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        if row is None:
            return None
        record = _load(ProjectProfile, row["record_json"])
        _require_projection(row, record)
        return record


class OpportunityRepository(_Repository):
    def put_opportunity_version(self, record: OpportunityRecord, *, content_hash: str) -> None:
        self._require_transaction()
        record = OpportunityRecord.model_validate(record)
        if re.fullmatch(r"[a-f0-9]{64}", content_hash) is None:
            raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
        self._insert(
            "INSERT INTO opportunity_versions(id, version, record_json, content_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (record.id, record.version, _json(record), content_hash, _instant(record.created_at)),
            entity="opportunity version",
        )

    def get_opportunity_version(self, record_id: str, version: int) -> OpportunityRecord | None:
        row = self.connection.execute(
            "SELECT id, version, record_json, content_hash, created_at FROM opportunity_versions "
            "WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        if row is None:
            return None
        record = _load(OpportunityRecord, row["record_json"])
        _require_projection(row, record)
        return record

    def list_versions(self, record_id: str) -> tuple[OpportunityRecord, ...]:
        rows = self.connection.execute(
            "SELECT id, version, record_json, content_hash, created_at FROM opportunity_versions "
            "WHERE id=? ORDER BY version",
            (record_id,),
        ).fetchall()
        records = []
        for row in rows:
            record = _load(OpportunityRecord, row["record_json"])
            _require_projection(row, record)
            records.append(record)
        return tuple(records)


class EvidenceRepository(_Repository):
    def put_evidence(
        self, record: EvidenceRecord, opportunity_id: str, opportunity_version: int
    ) -> None:
        self._require_transaction()
        record = EvidenceRecord.model_validate(record)
        self._insert(
            "INSERT INTO evidence(id, version, opportunity_id, opportunity_version, record_json, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.version,
                opportunity_id,
                opportunity_version,
                _json(record),
                _instant(record.created_at),
            ),
            entity="evidence opportunity",
        )

    def _from_row(self, row: sqlite3.Row) -> EvidenceRecord:
        record = _load(EvidenceRecord, row["record_json"])
        _require_projection(row, record)
        return record

    def get_evidence(self, record_id: str, version: int) -> EvidenceRecord | None:
        row = self.connection.execute(
            "SELECT id, version, opportunity_id, opportunity_version, record_json, created_at "
            "FROM evidence WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        return None if row is None else self._from_row(row)

    def list_for_opportunity(
        self, opportunity_id: str, opportunity_version: int
    ) -> tuple[EvidenceRecord, ...]:
        rows = self.connection.execute(
            "SELECT id, version, opportunity_id, opportunity_version, record_json, created_at "
            "FROM evidence WHERE opportunity_id=? AND opportunity_version=? ORDER BY id, version",
            (opportunity_id, opportunity_version),
        ).fetchall()
        return tuple(self._from_row(row) for row in rows)


class DecisionRepository(_Repository):
    def put_decision(self, record: DecisionRecord, *, founder_profile_id: str) -> None:
        self._require_transaction()
        record = DecisionRecord.model_validate(record)
        self._insert(
            "INSERT INTO decisions(id, version, opportunity_id, opportunity_version, "
            "founder_profile_id, founder_profile_version, project_id, project_version, "
            "record_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.version,
                record.opportunity_id,
                record.opportunity_version,
                founder_profile_id,
                record.profile_version,
                record.project_id,
                record.project_version,
                _json(record),
                _instant(record.created_at),
            ),
            entity="decision",
        )

    def _from_row(self, row: sqlite3.Row) -> DecisionRecord:
        record = _load(DecisionRecord, row["record_json"])
        _require_projection(
            row,
            record,
            opportunity_id=record.opportunity_id,
            opportunity_version=record.opportunity_version,
            founder_profile_version=record.profile_version,
            project_id=record.project_id,
            project_version=record.project_version,
        )
        return record

    def get_decision(self, record_id: str, version: int) -> DecisionRecord | None:
        row = self.connection.execute(
            "SELECT id, version, opportunity_id, opportunity_version, founder_profile_id, "
            "founder_profile_version, project_id, project_version, record_json, created_at "
            "FROM decisions WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        return None if row is None else self._from_row(row)

    def list_for_opportunity(
        self, opportunity_id: str, opportunity_version: int
    ) -> tuple[DecisionRecord, ...]:
        rows = self.connection.execute(
            "SELECT id, version, opportunity_id, opportunity_version, founder_profile_id, "
            "founder_profile_version, project_id, project_version, record_json, created_at "
            "FROM decisions WHERE opportunity_id=? AND opportunity_version=? ORDER BY id, version",
            (opportunity_id, opportunity_version),
        ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def list_versions(self, record_id: str) -> tuple[DecisionRecord, ...]:
        rows = self.connection.execute(
            "SELECT id, version, opportunity_id, opportunity_version, founder_profile_id, "
            "founder_profile_version, project_id, project_version, record_json, created_at "
            "FROM decisions WHERE id=? ORDER BY version",
            (record_id,),
        ).fetchall()
        return tuple(self._from_row(row) for row in rows)


class RunRepository(_Repository):
    def create_run(self, record: RunRecord) -> None:
        self._require_transaction()
        record = RunRecord.model_validate(record)
        self._validate_link(record, "opportunity")
        self._validate_link(record, "decision")
        if record.opportunity_id is not None:
            opportunity = self.connection.execute(
                "SELECT 1 FROM opportunity_versions WHERE id=? AND version=?",
                (record.opportunity_id, record.opportunity_version),
            ).fetchone()
            if opportunity is None:
                raise InvalidReferenceError("Invalid run opportunity reference")
        if record.decision_id is not None:
            decision = self.connection.execute(
                "SELECT opportunity_id, opportunity_version FROM decisions "
                "WHERE id=? AND version=?",
                (record.decision_id, record.decision_version),
            ).fetchone()
            if decision is None:
                raise InvalidReferenceError("Invalid run decision reference")
            if record.opportunity_id is not None and (
                decision["opportunity_id"],
                decision["opportunity_version"],
            ) != (record.opportunity_id, record.opportunity_version):
                raise InvalidReferenceError("Run decision and opportunity links diverge")
        self._insert(
            "INSERT INTO runs(id, version, record_json, mode, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.version,
                _json(record),
                record.mode.value,
                record.state.value,
                _instant(record.created_at),
                _instant(record.updated_at),
            ),
            entity="run",
        )

    @staticmethod
    def _validate_link(record: RunRecord, name: str) -> None:
        if (getattr(record, f"{name}_id") is None) != (getattr(record, f"{name}_version") is None):
            raise ValueError(f"{name} link requires both id and version")

    def _from_row(self, row: sqlite3.Row) -> RunRecord:
        record = _load(RunRecord, row["record_json"])
        _require_projection(row, record, mode=record.mode.value, state=record.state.value)
        return record

    def get_run(self, record_id: str, version: int) -> RunRecord | None:
        row = self.connection.execute(
            "SELECT id, version, record_json, mode, state, created_at, updated_at FROM runs "
            "WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        return None if row is None else self._from_row(row)

    def list_for_opportunity(
        self, opportunity_id: str, opportunity_version: int
    ) -> tuple[RunRecord, ...]:
        rows = self.connection.execute(
            "SELECT id, version, record_json, mode, state, created_at, updated_at "
            "FROM runs ORDER BY created_at, id"
        ).fetchall()
        records = tuple(self._from_row(row) for row in rows)
        return tuple(
            record
            for record in records
            if (record.opportunity_id, record.opportunity_version)
            == (opportunity_id, opportunity_version)
        )

    def append_run_event(
        self,
        run_id: str,
        *,
        event_type: str,
        payload: RunEventPayload | dict[str, Any],
        mode: RuntimeMode | str,
        occurred_at: datetime | str,
        sequence: int | None = None,
    ) -> RunEvent:
        self._require_transaction()
        persisted_run = self.connection.execute(
            "SELECT mode FROM runs WHERE id=?", (run_id,)
        ).fetchone()
        if persisted_run is None:
            raise InvalidReferenceError("Invalid run event run reference")
        requested_mode = RuntimeMode(mode)
        if persisted_run["mode"] != requested_mode.value:
            raise InvalidReferenceError("Run event mode does not match persisted run mode")
        next_sequence = self.connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM run_events WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        if sequence is not None and sequence != next_sequence:
            raise RepositoryConflictError("run event sequence must equal the next sequence")
        sequence = next_sequence
        event = RunEvent.model_validate(
            {
                "run_id": run_id,
                "sequence": sequence,
                "event_type": event_type,
                "payload": payload,
                "mode": requested_mode,
                "occurred_at": occurred_at,
            }
        )
        self._insert(
            "INSERT INTO run_events(run_id, sequence, event_type, payload_json, mode, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.run_id,
                event.sequence,
                event.event_type,
                _json(event.payload),
                event.mode.value,
                _instant(event.occurred_at),
            ),
            entity="run event",
        )
        return event

    def list_run_events(self, run_id: str) -> tuple[RunEvent, ...]:
        rows = self.connection.execute(
            "SELECT run_id, sequence, event_type, payload_json, mode, occurred_at FROM run_events "
            "WHERE run_id=? ORDER BY sequence",
            (run_id,),
        ).fetchall()
        return tuple(
            RunEvent.model_validate(
                {
                    "run_id": row["run_id"],
                    "sequence": row["sequence"],
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload_json"]),
                    "mode": row["mode"],
                    "occurred_at": row["occurred_at"],
                }
            )
            for row in rows
        )


class ApprovalRepository(_Repository):
    def put_approval(self, record: ApprovalRecord) -> None:
        self._require_transaction()
        record = ApprovalRecord.model_validate(record)
        self._insert(
            "INSERT INTO approvals(id, version, opportunity_id, opportunity_version, "
            "founder_profile_id, founder_profile_version, project_id, project_version, "
            "decision_id, "
            "decision_version, record_json, state, idempotency_key, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.version,
                record.opportunity_id,
                record.opportunity_version,
                record.founder_profile_id,
                record.founder_profile_version,
                record.project_id,
                record.project_version,
                record.decision_id,
                record.decision_version,
                _json(record),
                record.state.value,
                record.idempotency_key,
                _instant(record.created_at),
            ),
            entity="approval",
        )

    def revoke_approval(self, record: ApprovalRecord) -> None:
        record = ApprovalRecord.model_validate(record)
        if record.state.value != "REVOKED_APPROVAL":
            raise ValueError("revoke_approval requires a caller-decided REVOKED_APPROVAL record")
        self.put_approval(record)

    def get_approval(self, record_id: str, version: int) -> ApprovalRecord | None:
        row = self.connection.execute(
            "SELECT id, version, opportunity_id, opportunity_version, founder_profile_id, "
            "founder_profile_version, project_id, project_version, decision_id, decision_version, "
            "record_json, state, idempotency_key, created_at FROM approvals "
            "WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        if row is None:
            return None
        record = _load(ApprovalRecord, row["record_json"])
        _require_projection(
            row,
            record,
            opportunity_id=record.opportunity_id,
            opportunity_version=record.opportunity_version,
            founder_profile_id=record.founder_profile_id,
            founder_profile_version=record.founder_profile_version,
            project_id=record.project_id,
            project_version=record.project_version,
            decision_id=record.decision_id,
            decision_version=record.decision_version,
            state=record.state.value,
            idempotency_key=record.idempotency_key,
        )
        return record


class DraftPackRepository(_Repository):
    def put_draft_job(self, record: DraftJobRecord) -> None:
        self._require_transaction()
        record = DraftJobRecord.model_validate(record)
        self._insert(
            "INSERT INTO draft_jobs(id, version, approval_id, approval_version, record_json, "
            "state, "
            "idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.version,
                record.approval_id,
                record.approval_version,
                _json(record),
                record.state.value,
                record.idempotency_key,
                _instant(record.created_at),
            ),
            entity="draft job",
        )

    def get_draft_job(self, record_id: str, version: int) -> DraftJobRecord | None:
        row = self.connection.execute(
            "SELECT id, version, approval_id, approval_version, record_json, state, "
            "idempotency_key, "
            "created_at FROM draft_jobs WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        if row is None:
            return None
        record = _load(DraftJobRecord, row["record_json"])
        _require_projection(
            row,
            record,
            approval_id=record.approval_id,
            approval_version=record.approval_version,
            state=record.state.value,
            idempotency_key=record.idempotency_key,
        )
        return record

    def put_draft_pack(self, record: DraftPack) -> None:
        self._require_transaction()
        record = DraftPack.model_validate(record)
        self._validate_pack_graph(record)
        self._insert(
            "INSERT INTO draft_packs(id, version, draft_job_id, draft_job_version, approval_id, "
            "approval_version, record_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.version,
                record.draft_job_id,
                record.draft_job_version,
                record.approval_id,
                record.approval_version,
                _json(record),
                _instant(record.created_at),
            ),
            entity="draft pack",
        )

    def _validate_pack_graph(self, record: DraftPack) -> None:
        job = self.get_draft_job(record.draft_job_id, record.draft_job_version)
        if job is None:
            raise InvalidReferenceError("invalid draft pack job reference")
        if (job.approval_id, job.approval_version) != (
            record.approval_id,
            record.approval_version,
        ):
            raise InvalidReferenceError("draft pack job approval reference diverges")
        approval = ApprovalRepository(self.connection).get_approval(
            record.approval_id, record.approval_version
        )
        if approval is None:
            raise InvalidReferenceError("invalid draft pack approval reference")
        pack_snapshot = (
            record.opportunity_id,
            record.opportunity_hash,
            record.opportunity_version,
            record.founder_profile_id,
            record.founder_profile_version,
            record.project_id,
            record.project_version,
            record.decision_id,
            record.decision_version,
            record.policy_versions,
        )
        approval_snapshot = (
            approval.opportunity_id,
            approval.opportunity_hash,
            approval.opportunity_version,
            approval.founder_profile_id,
            approval.founder_profile_version,
            approval.project_id,
            approval.project_version,
            approval.decision_id,
            approval.decision_version,
            approval.policy_versions,
        )
        if pack_snapshot != approval_snapshot:
            raise InvalidReferenceError("draft pack approval snapshot reference diverges")

    def get_draft_pack(self, record_id: str, version: int) -> DraftPack | None:
        row = self.connection.execute(
            "SELECT id, version, draft_job_id, draft_job_version, approval_id, approval_version, "
            "record_json, created_at FROM draft_packs WHERE id=? AND version=?",
            (record_id, version),
        ).fetchone()
        if row is None:
            return None
        record = _load(DraftPack, row["record_json"])
        _require_projection(
            row,
            record,
            draft_job_id=record.draft_job_id,
            draft_job_version=record.draft_job_version,
            approval_id=record.approval_id,
            approval_version=record.approval_version,
        )
        self._validate_pack_graph(record)
        return record
