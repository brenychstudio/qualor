import type { EvidenceClaimView, EvidenceProofView } from '../../generated/domain';
import { TechnicalProvenance } from './TechnicalProvenance';

const ruleText = (value: string) => value.replace(/^r_/, '').replaceAll('_', ' ');
const stateText = (value: string) => value.replaceAll('_', ' ');

// QUALOR's reading of a recorded rule. It never appears inside the source quotation.
const interpretation: Record<EvidenceClaimView['state'], string> = {
  PASS: 'A recorded rule is positively supported by the cited evidence.',
  FAIL: 'A recorded rule is contradicted by the cited evidence.',
  UNKNOWN: 'No admissible evidence resolves this rule. The fact stays unresolved.',
  CONFLICT: 'Cited sources disagree and recorded precedence cannot resolve them. This claim needs human review; QUALOR does not choose between the sources.',
  STALE: 'The previous snapshot is retained for audit and requires renewed verification before it can be read as current.',
  NOT_APPLICABLE: 'This rule does not apply to the selected opportunity.',
};

function EvidenceCitation({ proof }: { proof: EvidenceProofView }) {
  return <figure className="evidence-citation">
    <blockquote className="proof-excerpt" cite={proof.original_url}>{proof.excerpt}</blockquote>
    <figcaption>
      <dl className="proof-metadata">
        <div><dt>Source</dt><dd>{proof.domain}</dd></div>
        <div><dt>Source type</dt><dd>{stateText(proof.source_type)}</dd></div>
        <div><dt>Evidence category</dt><dd>{stateText(proof.category)}</dd></div>
        <div><dt>Freshness at retrieval</dt><dd>{proof.freshness}</dd></div>
      </dl>
      <p className="proof-source-url">{proof.original_url}</p>
      <a className="proof-citation-link" href={proof.original_url} target="_blank" rel="noopener noreferrer external">
        View original <span aria-hidden="true">↗</span>
      </a>
      <TechnicalProvenance proof={proof} />
    </figcaption>
  </figure>;
}

export function EvidenceClaim({ claim, proofs }: { claim: EvidenceClaimView; proofs: EvidenceProofView[] }) {
  const cited = proofs.filter(proof => claim.evidence_refs.includes(proof.evidence_id));
  const label = ruleText(claim.rule_id);
  return <div className="evidence-claim" role="group" aria-label={`${label} claim, ${claim.state}`}>
    <div className="proof-claim-heading"><span className="section-index">{label}</span><strong>{claim.state}</strong></div>
    <p className="proof-boundary">{interpretation[claim.state]}</p>
    {claim.reason_codes.length > 0 && <p className="proof-boundary">Recorded reason codes: {claim.reason_codes.map(stateText).join(' · ')}</p>}
    {cited.length === 0
      ? <p className="proof-boundary">No source excerpt is recorded for this claim.</p>
      : cited.map(proof => <EvidenceCitation key={proof.evidence_id} proof={proof} />)}
    {claim.state === 'CONFLICT' && cited.length > 1 && <p className="proof-boundary">Both cited sources are shown unchanged so a human reviewer can resolve them.</p>}
  </div>;
}
