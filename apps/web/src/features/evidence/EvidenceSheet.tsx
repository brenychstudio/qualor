import { useEffect, useState } from 'react';
import { ApiError, apiRequest } from '../../api/client';
import type { EvidenceSheetView, Reward } from '../../generated/domain';
import { EvidenceClaim } from './EvidenceClaim';

const stateText = (value: string) => value.replaceAll('_', ' ');
const countText = (count: number, noun: string) => `${count} ${count === 1 ? noun : `${noun}s`}`;

function rewardText(reward: Reward) {
  const money = reward.amount ?? reward.amount_min ?? reward.amount_max;
  return money ? `${stateText(reward.kind)} · ${money.amount} ${money.currency}` : stateText(reward.kind);
}

function conflictText(status: EvidenceSheetView['constraints_conflicts']['status']) {
  if (status === 'BLOCKED_BY_EXPLICIT_RULE') return 'An explicit recorded rule blocks this opportunity.';
  if (status === 'REVIEW_REQUIRED') return 'Recorded rules require human review before this decision is acted on.';
  if (status === 'NO_CONFLICT_DETECTED_IN_CHECKED_RULES') return 'No conflict was detected in the checked rule categories. Unchecked categories remain unresolved.';
  return 'No conflict evaluation is recorded.';
}

// The warm proof layer inside the frozen evidence plane. It reads server-owned evidence only.
export function EvidenceSheet({ opportunityId }: { opportunityId: string }) {
  const [sheet, setSheet] = useState<EvidenceSheetView | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setSheet(null); setError(null);
    apiRequest<EvidenceSheetView>(`/opportunities/${opportunityId}/evidence`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setSheet(value); })
      .catch(readError => {
        if (controller.signal.aborted) return;
        setError(readError instanceof ApiError ? readError.message : 'The local controller could not read recorded evidence.');
      });
    return () => controller.abort();
  }, [opportunityId]);

  if (error) return <p className="proof-boundary" role="status">Recorded evidence is unavailable. {error}</p>;
  if (!sheet) return <p className="proof-boundary" role="status">Reading recorded evidence…</p>;

  const { claims, proofs, eligibility, project_fit: fit, constraints_conflicts: conflicts, reward_deadline: reward } = sheet;
  const sources = new Set(proofs.map(proof => proof.domain));
  return <div className="evidence-sheet">
    <p className="proof-introduction">
      {countText(claims.length, 'recorded claim')} · {countText(sources.size, 'cited source')}<br />
      Evidence freshness at this read: {sheet.freshness}. Opportunity version {sheet.opportunity_version}.
    </p>

    <section className="evidence-section" aria-label="Eligibility">
      <div className="proof-claim-heading"><h3 className="section-index">Eligibility</h3><strong>{eligibility.state ?? 'UNKNOWN'}</strong></div>
      <p className="proof-boundary">
        Deterministic gate · policy version {eligibility.policy_version ?? 'unrecorded'} ·{' '}
        {eligibility.evaluated_at ? <>evaluated <time dateTime={eligibility.evaluated_at}>{eligibility.evaluated_at}</time></> : 'no evaluation recorded'}
      </p>
      {claims.length === 0
        ? <p className="proof-boundary">No eligibility claims are recorded for this opportunity.</p>
        : claims.map(claim => <EvidenceClaim key={claim.rule_id} claim={claim} proofs={proofs} />)}
    </section>

    <section className="evidence-section" aria-label="Project Fit">
      <div className="proof-claim-heading"><h3 className="section-index">Project fit</h3><strong>{fit.match_status ?? 'INSUFFICIENT EVIDENCE'}</strong></div>
      <p className="proof-boundary">Project facts are context. They are not official eligibility authority.</p>
      <dl className="proof-metadata">
        <div><dt>Best project</dt><dd>{fit.project?.name ?? 'Unresolved'}</dd></div>
        <div><dt>Matched requirements</dt><dd>{countText(fit.matched_requirement_refs.length, 'reference')}</dd></div>
        <div><dt>Missing facts</dt><dd>{fit.missing_facts.length ? fit.missing_facts.map(stateText).join(' · ') : 'None recorded'}</dd></div>
        <div><dt>Blocking gaps</dt><dd>{fit.blocking_gaps.length ? fit.blocking_gaps.map(stateText).join(' · ') : 'None recorded'}</dd></div>
      </dl>
      {fit.factor_results.length > 0 && <div className="proof-claims">
        <h4>Recorded factors</h4>
        {fit.factor_results.map(factor => <div key={factor.factor}>
          <span>{stateText(factor.factor)}</span>
          <strong>{factor.rating == null ? 'UNKNOWN' : `${factor.rating} / 4`}</strong>
          <span>{countText(factor.reasons.length, 'recorded reason')}</span>
        </div>)}
      </div>}
    </section>

    <section className="evidence-section" aria-label="Constraints & Conflicts">
      <div className="proof-claim-heading"><h3 className="section-index">Constraints &amp; conflicts</h3><strong>{conflicts.status ? stateText(conflicts.status) : 'UNKNOWN'}</strong></div>
      <p className="proof-boundary">{conflictText(conflicts.status)}</p>
      <dl className="proof-metadata">
        <div><dt>Founder constraints</dt><dd>{conflicts.founder_constraints.length ? conflicts.founder_constraints.map(stateText).join(' · ') : 'None recorded'}</dd></div>
        <div><dt>Checked rule categories</dt><dd>{countText(conflicts.checked_rule_categories.length, 'category')}</dd></div>
        <div><dt>Unchecked rule categories</dt><dd>{countText(conflicts.missing_rule_categories.length, 'category')}</dd></div>
        <div><dt>Recorded reasons</dt><dd>{conflicts.reasons.length ? conflicts.reasons.map(stateText).join(' · ') : 'None recorded'}</dd></div>
      </dl>
    </section>

    <section className="evidence-section" aria-label="Reward & Deadline">
      <div className="proof-claim-heading"><h3 className="section-index">Reward &amp; deadline</h3><strong>{reward.deadline.values.length ? stateText(reward.deadline.timezone_status) : 'UNKNOWN'}</strong></div>
      <dl className="proof-metadata">
        <div><dt>Recorded deadline</dt><dd>{reward.deadline.values.length ? reward.deadline.values.join(' · ') : 'UNKNOWN'}</dd></div>
        <div><dt>Timezone status</dt><dd>{stateText(reward.deadline.timezone_status)}</dd></div>
        <div><dt>Recorded rewards</dt><dd>{reward.rewards.length ? reward.rewards.map(rewardText).join(' · ') : 'None recorded'}</dd></div>
        <div><dt>Evidence references</dt><dd>{countText(reward.evidence_refs.length, 'reference')}{reward.evidence_refs_scope ? ` · ${stateText(reward.evidence_refs_scope)}` : ''}</dd></div>
      </dl>
      <p className="proof-boundary">Reward and deadline facts appear exactly as recorded. An unknown deadline is never read as open.</p>
    </section>
  </div>;
}
