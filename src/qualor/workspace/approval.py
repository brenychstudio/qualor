"""Human application-service approval boundary; never register as an agent tool.

Control-plane actor, policies and runtime mode must come from trusted application
configuration, never model output. Confirmation receipts do not authorize drafting.
Only a new (replayed=False) consume within the caller transaction can do so.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import uuid4

from pydantic import TypeAdapter

from qualor.decisions.model import PolicyVersions
from qualor.domain.base import NonEmpty, UtcInstant
from qualor.domain.enums import Category
from qualor.eligibility.coverage import REQUIRED_CATEGORIES
from qualor.eligibility.evidence import HARD_SOURCES
from qualor.eligibility.freshness import evaluate_freshness
from qualor.persistence import Database
from qualor.runtime import RuntimeMode

from .models import (
    ApprovalAction,
    ApprovalBindings,
    ApprovalChange,
    ApprovalReason,
    ApprovalRecord,
    ApprovalState,
)
from .store import WorkspaceStore

_INSTANT = TypeAdapter(UtcInstant)
_TEXT = TypeAdapter(NonEmpty)


@dataclass(frozen=True)
class ApprovalValidation:
    actionable: bool
    reason: ApprovalReason
    record: ApprovalRecord | None


@dataclass(frozen=True)
class ConsumptionReceipt:
    record: ApprovalRecord
    replayed: bool


class ApprovalDenied(RuntimeError):
    def __init__(self, reason: ApprovalReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def approval_expiry(now: datetime, deadline: date | datetime | None) -> datetime:
    """Calendar-only dates retain 24h; actionability separately requires exact proof."""
    instant = _INSTANT.validate_python(now)
    expiry = instant + timedelta(hours=24)
    return (
        min(expiry, _INSTANT.validate_python(deadline))
        if isinstance(deadline, datetime)
        else expiry
    )


def _bindings(record: ApprovalRecord) -> ApprovalBindings:
    return ApprovalBindings.model_validate(
        {field: getattr(record, field) for field in ApprovalBindings.model_fields}
    )


def _binding_reason(actual: ApprovalBindings, expected: ApprovalBindings) -> ApprovalReason | None:
    if actual.actor_id != expected.actor_id:
        return ApprovalReason.ACTOR_MISMATCH
    if actual.action != expected.action:
        return ApprovalReason.ACTION_MISMATCH
    for field in ("opportunity_id", "founder_profile_id", "project_id", "decision_id"):
        if getattr(actual, field) != getattr(expected, field):
            return ApprovalReason.IDENTITY_MISMATCH
    if actual.policy_versions != expected.policy_versions:
        return ApprovalReason.POLICY_MISMATCH
    if actual != expected:
        return ApprovalReason.VERSION_MISMATCH
    return None


def _key(operation: str, key: str) -> str:
    # Global per-operation lookup prevents the same key being retargeted to another
    # approval. Its immutable receipt is the full actor/action/identity fingerprint.
    raw = _TEXT.validate_python(key)
    return hashlib.sha256(json.dumps([operation, raw]).encode()).hexdigest()


class ApprovalService:
    def __init__(
        self,
        database: Database,
        *,
        actor_id: str,
        policy_versions: PolicyVersions,
        mode: RuntimeMode,
    ) -> None:
        self.database = database
        self.actor_id = _TEXT.validate_python(actor_id)
        self.policy_versions = PolicyVersions.model_validate(policy_versions)
        self.mode = RuntimeMode(mode)

    def _expected(self, value: ApprovalBindings) -> ApprovalBindings:
        if getattr(value, "action", None) != ApprovalAction.GENERATE_DRAFT_PACK:
            raise ApprovalDenied(ApprovalReason.ACTION_MISMATCH)
        expected = ApprovalBindings.model_validate(value)
        if expected.actor_id != self.actor_id:
            raise ApprovalDenied(ApprovalReason.ACTOR_MISMATCH)
        return expected

    def _graph_reason(
        self, store: WorkspaceStore, binding: ApprovalBindings, now: datetime
    ) -> ApprovalReason | None:
        if binding.policy_versions != self.policy_versions:
            return ApprovalReason.POLICY_MISMATCH
        latest = store.opportunities.latest_with_digest(binding.opportunity_id)
        founder = store.profiles.latest_founder(binding.founder_profile_id)
        project = store.projects.latest_project(binding.project_id)
        decisions = store.decisions.list_versions(binding.decision_id)
        if latest is None or founder is None or project is None or not decisions:
            return ApprovalReason.GRAPH_MISMATCH
        opportunity, digest = latest
        decision = decisions[-1]
        if (opportunity.version, digest, founder.version, project.version, decision.version) != (
            binding.opportunity_version,
            binding.opportunity_hash,
            binding.founder_profile_version,
            binding.project_version,
            binding.decision_version,
        ):
            return ApprovalReason.VERSION_MISMATCH
        if (
            decision.opportunity_id,
            decision.opportunity_version,
            decision.project_id,
            decision.project_version,
            decision.profile_version,
            store.decisions.get_founder_profile_id(decision.id, decision.version),
        ) != (
            binding.opportunity_id,
            binding.opportunity_version,
            binding.project_id,
            binding.project_version,
            binding.founder_profile_version,
            binding.founder_profile_id,
        ):
            return ApprovalReason.GRAPH_MISMATCH
        # Distinct deterministic decision IDs may describe successive reevaluations.
        # A newer same-graph decision supersedes this one; equal timestamps are
        # ambiguous and fail closed rather than treating lexical ID order as authority.
        for candidate in store.decisions.list_for_opportunity(
            binding.opportunity_id, binding.opportunity_version
        ):
            if (
                candidate.id != decision.id
                and candidate.project_id == binding.project_id
                and store.decisions.get_founder_profile_id(candidate.id, candidate.version)
                == binding.founder_profile_id
                and candidate.created_at >= decision.created_at
            ):
                return ApprovalReason.GRAPH_MISMATCH
        if decision.policy_versions != self.policy_versions:
            return ApprovalReason.POLICY_MISMATCH
        if not opportunity.deadlines or any(type(d) is date for d in opportunity.deadlines):
            return ApprovalReason.DEADLINE_UNKNOWN
        deadline = min(opportunity.deadlines)
        if deadline <= now:
            return ApprovalReason.DEADLINE_PASSED
        gate = decision.eligibility_gate
        if gate.policy_version != self.policy_versions.eligibility:
            return ApprovalReason.POLICY_MISMATCH
        if (
            decision.recommendation not in {"APPLY", "PREPARE"}
            or gate.state != "PASS"
            or decision.conflict_status != "NO_CONFLICT_DETECTED_IN_CHECKED_RULES"
            or decision.freshness_status != "FRESH"
        ):
            return ApprovalReason.DECISION_NOT_ACTIONABLE
        if store.opportunities.list_refresh_failures(opportunity.id, opportunity.version):
            return ApprovalReason.EVIDENCE_NOT_ACTIONABLE
        # Current decisions bind evidence IDs only. No timestamp or latest-version
        # guess can prove which immutable version was evaluated. Resolve required
        # IDs globally; reevaluation must use unambiguous IDs until decision records
        # explicitly bind proof versions. This also blocks a new request laundering
        # an old decision after a proof replacement.
        required_refs = set(decision.conflict.evidence_ids)
        critical_rule_ids = {
            rule_id for entry in gate.critical_coverage for rule_id in entry.rule_ids
        }

        def collect_refs(evaluation) -> None:
            required_refs.update(evaluation.evidence_ids)
            for child in evaluation.children:
                collect_refs(child)

        for evaluation in gate.evaluations:
            if evaluation.rule_id in critical_rule_ids:
                collect_refs(evaluation)
        if any(len(store.evidence.list_versions(ref)) > 1 for ref in required_refs):
            return ApprovalReason.EVIDENCE_CHANGED
        evidence = {
            item.id: item
            for item in store.evidence.list_for_opportunity(opportunity.id, opportunity.version)
        }
        for ref in decision.conflict.evidence_ids:
            item = evidence.get(ref)
            if (
                item is None
                or item.extraction_state != "REVIEWED"
                or item.last_refresh_failed_at is not None
                or not (
                    item.source_type in HARD_SOURCES
                    or (
                        item.source_type == "SYNTHETIC_FIXTURE" and self.mode == RuntimeMode.FIXTURE
                    )
                )
                or evaluate_freshness(item.retrieved_at, now, deadline) != "FRESH"
            ):
                return ApprovalReason.EVIDENCE_NOT_ACTIONABLE
        evaluations = {item.rule_id: item for item in gate.evaluations}
        coverage = {item.category: item for item in gate.critical_coverage}
        if len(coverage) != len(gate.critical_coverage) or set(coverage) != set(
            REQUIRED_CATEGORIES
        ):
            return ApprovalReason.EVIDENCE_NOT_ACTIONABLE

        def verified(evaluation, category: Category) -> bool:
            if (
                evaluation.policy_version != self.policy_versions.eligibility
                or evaluation.status not in {"PASS", "NOT_APPLICABLE"}
            ):
                return False
            if any(
                code not in {"MATCH", "EXPLICIT_NOT_APPLICABLE"} for code in evaluation.reason_codes
            ):
                return False
            if not evaluation.evidence_ids:
                return False
            for ref in evaluation.evidence_ids:
                item = evidence.get(ref)
                if (
                    item is None
                    or item.normalized_field != category
                    or item.extraction_state != "REVIEWED"
                    or item.last_refresh_failed_at is not None
                    or not (
                        item.source_type in HARD_SOURCES
                        or (
                            item.source_type == "SYNTHETIC_FIXTURE"
                            and self.mode == RuntimeMode.FIXTURE
                        )
                    )
                    or evaluate_freshness(item.retrieved_at, now, deadline) != "FRESH"
                ):
                    return False
            return all(verified(child, category) for child in evaluation.children)

        for category, entry in coverage.items():
            if (
                entry.state not in {"EVALUATED", "NOT_APPLICABLE_WITH_REASON"}
                or not entry.rule_ids
                or (entry.state == "NOT_APPLICABLE_WITH_REASON" and not entry.reasons)
            ):
                return ApprovalReason.EVIDENCE_NOT_ACTIONABLE
            for rule_id in entry.rule_ids:
                evaluation = evaluations.get(rule_id)
                if evaluation is None or not verified(evaluation, category):
                    return ApprovalReason.EVIDENCE_NOT_ACTIONABLE
        return None

    @staticmethod
    def _append(
        store: WorkspaceStore, record: ApprovalRecord, now: datetime, **changes
    ) -> ApprovalRecord:
        updated = ApprovalRecord.model_validate(
            {**record.model_dump(), "version": record.version + 1, "updated_at": now, **changes}
        )
        store.approvals.put_approval(updated)
        return updated

    def _inspect(
        self,
        store: WorkspaceStore,
        approval_id: str,
        expected: ApprovalBindings,
        now: datetime,
        *,
        pending_allowed: bool = False,
    ) -> ApprovalValidation:
        record = store.approvals.latest(approval_id)
        if record is None:
            return ApprovalValidation(False, ApprovalReason.NOT_FOUND, None)
        reason = _binding_reason(_bindings(record), expected)
        if reason is None and record.mode != self.mode:
            reason = ApprovalReason.MODE_MISMATCH
        if reason is not None:
            return ApprovalValidation(False, reason, record)
        if now < record.updated_at:
            return ApprovalValidation(False, ApprovalReason.TIME_INVALID, record)
        if record.state == ApprovalState.REVOKED_APPROVAL:
            reason = (
                ApprovalReason.EXPIRED
                if record.revocation_reason == ApprovalReason.EXPIRED
                else ApprovalReason.REVOKED
            )
            return ApprovalValidation(False, reason, record)
        if now >= record.expires_at:
            record = self._append(
                store,
                record,
                now,
                state=ApprovalState.REVOKED_APPROVAL,
                revocation_reason=ApprovalReason.EXPIRED.value,
                idempotency_key=None,
            )
            return ApprovalValidation(False, ApprovalReason.EXPIRED, record)
        if record.consumed_at is not None:
            return ApprovalValidation(False, ApprovalReason.CONSUMED, record)
        reason = self._graph_reason(store, _bindings(record), now)
        if reason is not None:
            if reason in {
                ApprovalReason.VERSION_MISMATCH,
                ApprovalReason.POLICY_MISMATCH,
                ApprovalReason.GRAPH_MISMATCH,
                ApprovalReason.EVIDENCE_CHANGED,
            }:
                record = self._append(
                    store,
                    record,
                    now,
                    state=ApprovalState.REVOKED_APPROVAL,
                    revocation_reason=reason.value,
                    idempotency_key=None,
                )
            return ApprovalValidation(False, reason, record)
        if record.state == ApprovalState.PENDING_APPROVAL and pending_allowed:
            return ApprovalValidation(True, ApprovalReason.VALID, record)
        if record.state != ApprovalState.APPROVED_FOR_PREPARATION:
            return ApprovalValidation(False, ApprovalReason.PENDING, record)
        return ApprovalValidation(True, ApprovalReason.VALID, record)

    def request_approval(
        self,
        actor_id,
        opportunity_hash,
        opportunity_version,
        profile_version,
        project_version,
        policy_versions,
        action,
        deadline,
        now,
        *,
        opportunity_id,
        founder_profile_id,
        project_id,
        decision_id,
        decision_version,
    ) -> ApprovalRecord:
        if action != ApprovalAction.GENERATE_DRAFT_PACK:
            raise ApprovalDenied(ApprovalReason.ACTION_MISMATCH)
        binding = self._expected(
            ApprovalBindings(
                actor_id=actor_id,
                opportunity_hash=opportunity_hash,
                opportunity_version=opportunity_version,
                founder_profile_version=profile_version,
                project_version=project_version,
                policy_versions=policy_versions,
                action=action,
                opportunity_id=opportunity_id,
                founder_profile_id=founder_profile_id,
                project_id=project_id,
                decision_id=decision_id,
                decision_version=decision_version,
            )
        )
        instant = _INSTANT.validate_python(now)
        with self.database.transaction(immediate=True) as connection:
            store = WorkspaceStore(connection)
            reason = self._graph_reason(store, binding, instant)
            if reason:
                raise ApprovalDenied(reason)
            opportunity = store.opportunities.latest_with_digest(opportunity_id)[0]
            verified_deadline = min(opportunity.deadlines)
            if deadline is not None and deadline != verified_deadline:
                raise ApprovalDenied(ApprovalReason.DEADLINE_MISMATCH)
            record = ApprovalRecord(
                **binding.model_dump(),
                schema_version="1",
                id=str(uuid4()),
                version=1,
                created_at=instant,
                updated_at=instant,
                provenance="USER_ASSERTED",
                mode=self.mode,
                state=ApprovalState.PENDING_APPROVAL,
                expires_at=approval_expiry(instant, verified_deadline),
            )
            store.approvals.put_approval(record)
            return record

    def validate_approval(
        self, approval_id: str, expected_versions: ApprovalBindings, now: datetime
    ) -> ApprovalValidation:
        expected = self._expected(expected_versions)
        instant = _INSTANT.validate_python(now)
        with self.database.transaction(immediate=True) as connection:
            return self._inspect(WorkspaceStore(connection), approval_id, expected, instant)

    def _receipt(self, store, approval_id, key, expected):
        receipt = store.approvals.find_receipt(key)
        if receipt is not None and (
            receipt.id != approval_id or _bindings(receipt) != expected or receipt.mode != self.mode
        ):
            raise ApprovalDenied(ApprovalReason.IDEMPOTENCY_CONFLICT)
        return receipt

    def confirm_approval(
        self,
        approval_id: str,
        idempotency_key: str,
        now: datetime,
        *,
        expected_versions: ApprovalBindings,
    ) -> ApprovalRecord:
        """A retry returns the original historical receipt, never new authorization."""
        expected = self._expected(expected_versions)
        instant = _INSTANT.validate_python(now)
        key = _key("CONFIRM", idempotency_key)
        with self.database.transaction(immediate=True) as connection:
            store = WorkspaceStore(connection)
            receipt = self._receipt(store, approval_id, key, expected)
            if receipt is not None:
                return receipt
            result = self._inspect(store, approval_id, expected, instant, pending_allowed=True)
            if result.actionable:
                if result.record.state != ApprovalState.PENDING_APPROVAL:
                    result = ApprovalValidation(
                        False, ApprovalReason.IDEMPOTENCY_CONFLICT, result.record
                    )
                else:
                    return self._append(
                        store,
                        result.record,
                        instant,
                        state=ApprovalState.APPROVED_FOR_PREPARATION,
                        idempotency_key=key,
                    )
        # Raise after commit: detected invalid versions retain their durable revocation.
        raise ApprovalDenied(result.reason)

    def consume_in_transaction(
        self,
        store: WorkspaceStore,
        approval_id: str,
        idempotency_key: str,
        now: datetime,
        *,
        expected_versions: ApprovalBindings,
    ) -> ConsumptionReceipt:
        """Compose with Task5 writes in ONE caller-owned transaction.

        A replay retrieves history only; it MUST NOT start new work. An exception
        aborts the caller transaction including consumption (and any revocation).
        """
        store.require_transaction()
        expected = self._expected(expected_versions)
        instant = _INSTANT.validate_python(now)
        key = _key("CONSUME", idempotency_key)
        receipt = self._receipt(store, approval_id, key, expected)
        if receipt is not None:
            return ConsumptionReceipt(receipt, True)
        result = self._inspect(store, approval_id, expected, instant)
        if not result.actionable:
            raise ApprovalDenied(result.reason)
        return ConsumptionReceipt(
            self._append(store, result.record, instant, consumed_at=instant, idempotency_key=key),
            False,
        )

    def consume_approval(
        self,
        approval_id: str,
        idempotency_key: str,
        now: datetime,
        *,
        expected_versions: ApprovalBindings,
    ) -> ConsumptionReceipt:
        error = None
        with self.database.transaction(immediate=True) as connection:
            try:
                receipt = self.consume_in_transaction(
                    WorkspaceStore(connection),
                    approval_id,
                    idempotency_key,
                    now,
                    expected_versions=expected_versions,
                )
            except ApprovalDenied as exc:
                error = exc
        if error:
            raise error
        return receipt

    def revoke_invalid_approvals(
        self, change: ApprovalChange, now: datetime
    ) -> tuple[ApprovalRecord, ...]:
        scope = ApprovalChange.model_validate(change)
        instant = _INSTANT.validate_python(now)
        with self.database.transaction(immediate=True) as connection:
            store = WorkspaceStore(connection)
            revoked = []
            for record in store.approvals.list_current():
                if (
                    record.actor_id != self.actor_id
                    or record.state == ApprovalState.REVOKED_APPROVAL
                ):
                    continue
                matched = any(
                    getattr(scope, field) is not None
                    and getattr(scope, field) == getattr(record, field)
                    for field in (
                        "opportunity_id",
                        "founder_profile_id",
                        "project_id",
                        "decision_id",
                    )
                )
                matched |= scope.policy_versions is not None and (
                    record.policy_versions != scope.policy_versions
                )
                if matched:
                    revoked.append(
                        self._append(
                            store,
                            record,
                            instant,
                            state=ApprovalState.REVOKED_APPROVAL,
                            idempotency_key=None,
                            revocation_reason=ApprovalReason.CHANGE_REVOKED.value,
                        )
                    )
            return tuple(revoked)
