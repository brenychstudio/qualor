import { Link } from 'react-router-dom';
import type { ProductStateView } from '../../generated/domain';
import { AVAILABILITY_COPY, PRIMARY_ACTION_LABELS, PRODUCT_STATE_COPY } from './product-state';

/**
 * The one degraded or terminal condition currently governing the workspace.
 *
 * It renders nothing at all when the server reports no product state, so a healthy
 * workspace never accumulates permanent warning surfaces. Every availability shown here is
 * the server's answer: this component recombines no facts into a permission of its own.
 */
export function ProductStateSurface({ productState }: { productState: ProductStateView | null }) {
  if (!productState?.state) return null;
  const { state, primary_action: action, reason } = productState;
  const copy = PRODUCT_STATE_COPY[state];
  const packLink = productState.draft_pack_available && productState.pack_id
    ? productState.pack_id
    : null;
  // When opening the pack is the action, the link is the action; do not say it twice.
  const actionIsPackLink = action === 'OPEN_APPLICATION_PACK' && packLink !== null;
  return <section className={`product-state product-state--${state.toLowerCase()}`} role="status" aria-label={AVAILABILITY_COPY.heading}>
    <div className="product-state-heading">
      <span className="section-index">{AVAILABILITY_COPY.heading}</span>
      <strong className="product-state-code">{state}</strong>
    </div>
    <h2 className="product-state-title">{copy.title}</h2>
    <p className="product-state-detail">{copy.detail}</p>

    {reason && <p className="product-state-reason">
      <span className="visually-hidden">Recorded reason </span>{reason}
    </p>}

    <ul className="product-state-availability">
      <li>{productState.evidence_available ? AVAILABILITY_COPY.evidenceAvailable : AVAILABILITY_COPY.evidenceUnavailable}</li>
      {!productState.coverage_complete && <li>{AVAILABILITY_COPY.coverageIncomplete}</li>}
      {!productState.approval_available && <li>{AVAILABILITY_COPY.approvalUnavailable}</li>}
    </ul>

    {action && !actionIsPackLink && <p className="product-state-action">{PRIMARY_ACTION_LABELS[action]}</p>}

    {packLink && <Link className="inline-link" to={`/draft-packs/${packLink}`}>
      {AVAILABILITY_COPY.openPack} <span aria-hidden="true">↗</span>
    </Link>}
  </section>;
}
