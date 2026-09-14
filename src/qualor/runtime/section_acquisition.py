"""Run-owned, bounded acquisition from one admitted official source."""

import hashlib
import json
from typing import TYPE_CHECKING

from qualor.domain.enums import ExtractionState, Operator

from .acquisition_coverage import AcquisitionOutcome, AcquisitionState, CoverageLedger
from .acquisition_plan import build_acquisition_plan
from .adapters import adapt_candidate
from .adapters.base import AdapterResult
from .budget import BudgetLimitExceeded
from .canonical_compilation import compile_section_authority, require_consistent_sources
from .normalization import ClaimNormalizationError, NormalizedSupportResult
from .section_scheduler import NoExtractionJob, SectionScheduler
from .sections import index_source

if TYPE_CHECKING:
    from .loop import OpportunityRun


def _semantic_record(value):
    if isinstance(value, dict):
        return {
            key: _semantic_record(item)
            for key, item in value.items()
            if key not in {"created_at", "updated_at"}
        }
    if isinstance(value, list):
        return [_semantic_record(item) for item in value]
    return value


def _authority_key(result: AdapterResult) -> str:
    # Confidence never reaches AdapterResult. Observation timestamps and diagnostic
    # repetition cannot replace the original records used by a cached DecisionInput.
    payload = result.model_dump(mode="json", exclude={"reason_codes", "conditional"})
    return json.dumps(_semantic_record(payload), sort_keys=True, separators=(",", ":"))


def authority_fingerprint(results: tuple[AdapterResult, ...]) -> str:
    """Fingerprint rules and evidence, including unresolved DecisionInput authority."""
    keys = sorted({_authority_key(result) for result in results})
    return hashlib.sha256(json.dumps(keys).encode()).hexdigest()


def retained_section_observation_count(results: tuple[AdapterResult, ...]) -> int:
    """Count unique retained non-rejected section observations for legacy telemetry."""

    return len(
        {
            _authority_key(result)
            for result in results
            if result.normalization_status in {"SUPPORTED", "AMBIGUOUS", "UNKNOWN"}
        }
    )


class SectionAcquisition:
    def __init__(self, run: "OpportunityRun"):
        self.run = run
        self.index = None
        self.plan = None
        self.ledger = None
        self.scheduler = None
        self._observations = ()

    @staticmethod
    def _retain_conflicts(results):
        conflicts = set()
        for category in {result.category for result in results}:
            assertions = tuple(
                (result.category, result.normalized_value)
                for result in results
                if result.category == category and result.normalization_status == "SUPPORTED"
            )
            try:
                require_consistent_sources(assertions)
            except ValueError as exc:
                if str(exc) != "CANONICAL_SOURCE_CONFLICT":
                    raise
                conflicts.add(category)
        return tuple(
            result.model_copy(
                update={
                    "normalization_status": "AMBIGUOUS",
                    "rules": tuple(
                        rule.model_copy(update={"contradiction": True}) for rule in result.rules
                    ),
                    "reason_codes": ("CANONICAL_SOURCE_CONFLICT",),
                }
            )
            if result.category in conflicts
            else result
            for result in results
        )

    def _effective_authority(self, observations):
        results = self._retain_conflicts(self._without_redundant_unknown(observations))
        results = self._reconcile_evidence(results)
        if self.ledger is None:
            return results
        effective = []
        for result in results:
            if (
                self.ledger.state(result.category) == AcquisitionState.SUPPORTED
                or result.normalization_status != "SUPPORTED"
            ):
                effective.append(result)
                continue
            # Preserve each supported expression under a non-executable completeness
            # guard. A later governing clause can invalidate an apparent hard failure.
            rules = tuple(
                rule.model_copy(
                    update={
                        "id": rule.id + "_coverage",
                        "operator": Operator.AND,
                        "subject_reference": None,
                        "operands": (),
                        "children": (rule,),
                        "supported": False,
                        "source_text_summary": "CATEGORY_COVERAGE_INCOMPLETE",
                    }
                )
                for rule in result.rules
            )
            effective.append(
                result.model_copy(
                    update={
                        "rules": rules,
                        "normalization_status": "UNKNOWN",
                        "reason_codes": ("CATEGORY_COVERAGE_INCOMPLETE",),
                    }
                )
            )
        return tuple(effective)

    @staticmethod
    def _reconcile_evidence(results):
        """Share a clause's reviewed snapshot without promoting rejected interpretations.

        Adapters can disagree on interpretation while referencing the same exact
        clause. REVIEWED records that one interpretation was grounded; each rule's
        supported flag still controls its own authority. Any other same-ID content
        disagreement remains invalid, including provenance or governing context.
        """
        records = {}
        for result in results:
            for record in result.evidence:
                previous = records.get(record.id)
                if previous is None or previous == record:
                    records.setdefault(record.id, record)
                    continue
                excluded = {"extraction_state"}
                if previous.model_dump(exclude=excluded) != record.model_dump(exclude=excluded) or {
                    previous.extraction_state,
                    record.extraction_state,
                } != {ExtractionState.UNVERIFIED, ExtractionState.REVIEWED}:
                    raise ValueError("CANONICAL_AUTHORITY_ID_CONFLICT")
                if record.extraction_state == ExtractionState.REVIEWED:
                    records[record.id] = record
        return tuple(
            result.model_copy(
                update={"evidence": tuple(records[record.id] for record in result.evidence)}
            )
            for result in results
        )

    @staticmethod
    def _without_redundant_unknown(results):
        def clause_key(result):
            evidence = tuple(
                _semantic_record(record.model_dump(mode="json", exclude={"extraction_state"}))
                for record in result.evidence
            )
            return json.dumps((result.category, evidence), sort_keys=True)

        supported = {
            clause_key(result) for result in results if result.normalization_status == "SUPPORTED"
        }
        return tuple(
            result
            for result in results
            if not (
                result.normalization_status == "UNKNOWN"
                and "MODEL_RETAINED_UNKNOWN" in result.reason_codes
                and clause_key(result) in supported
            )
        )

    def _admit(self, results: tuple[AdapterResult, ...]) -> bool:
        run = self.run
        unique = {
            _authority_key(result): result for result in (self._observations or run.section_results)
        }
        for result in results:
            unique.setdefault(_authority_key(result), result)
        observations = tuple(unique.values())
        admitted = self._effective_authority(observations)
        if authority_fingerprint(admitted) == authority_fingerprint(run.section_results):
            return False
        # Check the complete collection before changing the revision's authority.
        compile_section_authority(admitted)
        previous = run.section_results
        run.section_results = admitted
        run._authority_revision += 1
        try:
            run.evaluate_current_state()
        except Exception:
            run.section_results = previous
            run._authority_revision -= 1
            raise
        self._observations = observations
        if any("CANONICAL_SOURCE_CONFLICT" in result.reason_codes for result in admitted):
            reason = "CANONICAL_SOURCE_CONFLICT"
            run.semantic_rejection(
                ClaimNormalizationError(
                    reason,
                    NormalizedSupportResult(
                        status="AMBIGUOUS", canonical_value=None, reason_code=reason
                    ),
                )
            )
            run.event("CLAIM_NORMALIZATION_RESULT", reason, normalization_status="AMBIGUOUS")
        return True

    def drain(self, source_id: str) -> dict:
        run = self.run
        if run.termination_reason:
            return self._result(False)
        try:
            if run.mode != "LIVE":
                raise ValueError("SECTION_ACQUISITION_REQUIRES_LIVE")
            source = run.sources.get(source_id)
            if source is None:
                raise ValueError("SOURCE_REFERENCE_NOT_FOUND")
            if self.index is None:
                self.index = index_source(source, run.extractor.span_registry)
                self.plan = build_acquisition_plan(self.index)
                self.ledger = CoverageLedger(self.index, self.plan)
                self.scheduler = SectionScheduler(
                    self.index, self.plan, self.ledger, run.budget
                )
            elif source_id != self.index.source_id:
                raise ValueError("EXTRACTION_SOURCE_REFERENCE_MISMATCH")
        except Exception as exc:
            return run.failure(exc, component="extract_official_claims", event="EXTRACTION_RESULT")

        while not run.termination_reason:
            job = self.scheduler.next_job(
                authority_revision=run._authority_revision,
                steps_remaining=run.max_steps - run.steps,
                terminated=bool(run.termination_reason),
            )
            if isinstance(job, NoExtractionJob):
                run.stop(
                    {"STEP_BOUND": "MAX_STEPS", "BUDGET_BLOCKED": "BUDGET_EXHAUSTED"}.get(
                        job.reason_code, "NO_PROGRESS"
                    )
                )
                return self._result(job.pivot_eligible)
            if not run.enter(
                "section:"
                + job.source_revision
                + ":"
                + job.section_id
                + ":"
                + ",".join(job.categories)
            ):
                return self._result(False)
            self.scheduler.begin(job)
            dispatched_before = run.budget.snapshot().inference_calls
            receipt_context = run.extractor.client.extraction_receipt(
                source_id=job.source_id,
                section_id=job.section_id,
                categories=job.categories,
            )
            coverage_completed = False
            try:
                with receipt_context:
                    candidates = run.extractor.extract_section(source, self.index, job)
                    results = tuple(
                        adapt_candidate(candidate, evaluated_at=source.retrieved_at)
                        for candidate in candidates
                    )

                    interpreted = (
                        self._retain_conflicts((*self._observations, *results))[-len(results) :]
                        if results
                        else ()
                    )
                    retained = self._without_redundant_unknown(interpreted)
                    retained_ids = {id(result) for result in retained}
                    retained_candidates = tuple(
                        candidate
                        for candidate, interpretation in zip(candidates, interpreted, strict=True)
                        if id(interpretation) in retained_ids
                    )
                    if len(retained) != len(interpreted):
                        reason = "MODEL_RETAINED_UNKNOWN"
                        run.semantic_rejection(
                            ClaimNormalizationError(
                                reason,
                                NormalizedSupportResult(
                                    status="UNKNOWN", canonical_value=None, reason_code=reason
                                ),
                            )
                        )
                    interpreted = retained
                    outcomes = {}
                    for category in job.categories:
                        matching = tuple(
                            result for result in interpreted if result.category == category
                        )
                        statuses = {result.normalization_status for result in matching}
                        status = next(
                            (
                                value
                                for value in ("AMBIGUOUS", "UNKNOWN", "UNSUPPORTED")
                                if value in statuses
                            ),
                            "SUPPORTED" if matching else "UNKNOWN",
                        )
                        outcomes[category] = AcquisitionOutcome(
                            normalization_status=status,
                            supported_rule_ids=tuple(
                                dict.fromkeys(
                                    rule.id
                                    for result in matching
                                    if result.normalization_status == "SUPPORTED"
                                    for rule in result.rules
                                )
                            ),
                            conditional=any(result.conditional for result in matching),
                            context_complete=bool(matching)
                            and all(
                                candidate.semantic_context_complete
                                for candidate in retained_candidates
                                if candidate.candidate.category == category
                            ),
                            reason_code="SECTION_CANDIDATES_ADMITTED"
                            if matching
                            else "NO_SECTION_CANDIDATES",
                        )
                        if status != "SUPPORTED":
                            reason = next(
                                (
                                    result.reason_codes[0]
                                    for result in matching
                                    if result.normalization_status == status
                                ),
                                "NO_SECTION_CANDIDATES",
                            )
                            run.semantic_rejection(
                                ClaimNormalizationError(
                                    reason,
                                    NormalizedSupportResult(
                                        status=status, canonical_value=None, reason_code=reason
                                    ),
                                )
                            )
                    self.ledger.complete_item(
                        job.plan_item_id,
                        job.categories,
                        outcomes,
                        job.authority_revision,
                    )
                    coverage_completed = True
                    changed = self._admit(results)
                    receipt_context.complete(
                        outcomes=results, authority_revision=run._authority_revision
                    )
            except Exception as exc:
                if (
                    isinstance(exc, BudgetLimitExceeded)
                    and run.budget.snapshot().inference_calls == dispatched_before
                ):
                    self.ledger.budget_blocked_item(job.plan_item_id, job.categories)
                elif not coverage_completed:
                    self.ledger.operational_failure_item(
                        job.plan_item_id,
                        job.categories,
                        "SECTION_OPERATION_FAILED",
                    )
                run.failure(exc, component="extract_official_claims", event="EXTRACTION_RESULT")
                continue
            run.event("STRUCTURED_EXTRACTION", "MODEL_POWERED_TOOL", (source_id,), len(candidates))
            if not changed:
                run.no_progress += 1
                if run.no_progress >= 3:
                    run.stop("NO_PROGRESS")
        return self._result(False)

    def _result(self, pivot_eligible: bool) -> dict:
        return {
            "status": "STOPPED" if self.run.termination_reason else "ACQUIRED",
            "termination_reason": self.run.termination_reason,
            "authority_revision": self.run._authority_revision,
            "pivot_eligible": pivot_eligible,
        }
