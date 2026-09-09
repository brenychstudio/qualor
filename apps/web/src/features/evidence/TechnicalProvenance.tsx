import { useId, useState } from 'react';
import type { EvidenceProofView } from '../../generated/domain';

// Level-3 audit detail. Identifiers stay out of the DOM until the reader asks for them.
export function TechnicalProvenance({ proof }: { proof: EvidenceProofView }) {
  const [open, setOpen] = useState(false);
  const detailId = useId();
  return <div className="evidence-provenance">
    <button type="button" className="text-button" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen(!open)}>
      Technical provenance <span aria-hidden="true">{open ? '↙' : '→'}</span>
    </button>
    {open && <dl id={detailId} className="proof-metadata evidence-provenance-detail">
      <div><dt>Evidence ID</dt><dd>{proof.evidence_id}</dd></div>
      <div><dt>Evidence version</dt><dd>{proof.evidence_version}</dd></div>
      <div><dt>Source ID</dt><dd>{proof.technical_provenance?.source_id ?? proof.source_id ?? 'Not recorded'}</dd></div>
      <div><dt>Source version</dt><dd>{proof.source_version}</dd></div>
      <div><dt>Retrieval time</dt><dd><time dateTime={proof.retrieved_at}>{proof.retrieved_at}</time></dd></div>
      <div><dt>Policy version</dt><dd>{proof.technical_provenance?.policy_version ?? 'Not recorded'}</dd></div>
      <div><dt>Extraction state</dt><dd>{proof.technical_provenance?.extraction_state ?? 'Not recorded'}</dd></div>
      <div><dt>Retrieved location</dt><dd>{proof.url}</dd></div>
    </dl>}
  </div>;
}
