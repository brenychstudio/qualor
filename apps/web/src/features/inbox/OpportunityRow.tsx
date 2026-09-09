import type { KeyboardEventHandler, Ref } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { InboxItem } from '../../generated/domain';
import { deadlineLabel } from './inbox-state';

export function OpportunityRow({ item, selected, tabIndex, rowRef, onFocus, onKeyDown }: {
  item: InboxItem; selected: boolean; tabIndex: number; rowRef: Ref<HTMLAnchorElement>;
  onFocus: () => void; onKeyDown: KeyboardEventHandler<HTMLAnchorElement>;
}) {
  const location = useLocation();
  return <li><Link ref={rowRef} to={{ pathname: `/inbox/${encodeURIComponent(item.opportunity_id)}`, search: location.search }}
    className={`opportunity-row${selected ? ' opportunity-row--selected' : ''}`} aria-current={selected ? 'true' : undefined}
    tabIndex={tabIndex} onFocus={onFocus} onKeyDown={onKeyDown}>
    <span className="queue-item-index">{item.mode ?? 'Mode unknown'}</span>
    <strong>{item.program_name}</strong>
    <span className="queue-organizer">{item.organizer}</span>
    <span className="queue-decision-axis"><b>{item.recommendation ?? 'Decision unresolved'}</b></span>
    <span className="queue-pipeline">{item.presentation_state.replaceAll('_', ' ')}</span>
    <span className="queue-deadline">{deadlineLabel(item.deadline)}</span>
    <span className="queue-project">{item.best_project?.name ?? 'Project unresolved'}</span>
    {(item.freshness !== 'FRESH' || (item.run_state && item.run_state !== 'COMPLETED')) && <span className="queue-condition">
      {item.freshness !== 'FRESH' && <span>{item.freshness === 'UNKNOWN' ? 'Freshness unknown' : item.freshness}</span>}
      {item.run_state && item.run_state !== 'COMPLETED' && <span>{item.run_state.replaceAll('_', ' ')}</span>}
    </span>}
  </Link></li>;
}
