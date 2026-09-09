import { useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import type { InboxResponse } from '../../generated/domain';
import { OpportunityRow } from './OpportunityRow';
import { visibleInboxItems } from './inbox-state';
import type { InboxFilter, InboxSort } from './inbox-state';

export function OpportunityInbox({ inbox, error }: { inbox: InboxResponse | null; error: string | null }) {
  const { opportunityId } = useParams();
  const navigate = useNavigate(); const location = useLocation();
  const [sort, setSort] = useState<InboxSort>('PRIORITY');
  const [filter, setFilter] = useState<InboxFilter>('ALL');
  const [search, setSearch] = useState('');
  const [focusedId, setFocusedId] = useState<string>();
  const rowRefs = useRef(new Map<string, HTMLAnchorElement>());
  const items = visibleInboxItems(inbox?.items ?? [], sort, filter, search, Date.now());
  const selectedVisible = items.some(item => item.opportunity_id === opportunityId);
  const entryId = selectedVisible ? opportunityId : items.some(item => item.opportunity_id === focusedId) ? focusedId : items[0]?.opportunity_id;
  function move(event: KeyboardEvent<HTMLAnchorElement>, index: number) {
    const target = event.key === 'ArrowDown' ? Math.min(index + 1, items.length - 1)
      : event.key === 'ArrowUp' ? Math.max(index - 1, 0)
      : event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : null;
    if (target === null || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    const id = items[target].opportunity_id;
    navigate({ pathname: `/inbox/${encodeURIComponent(id)}`, search: location.search });
    rowRefs.current.get(id)?.focus();
  }
  return <>
    <div className="zone-heading"><h2>Opportunities</h2><span>{inbox ? inbox.page.total : '\u2014'}</span></div>
    {inbox && !error ? <>
      <div className="inbox-controls">
        <label>Search<input type="search" aria-label="Search opportunities" placeholder="Title or organizer" value={search} onChange={event => setSearch(event.target.value)} /></label>
        <div className="inbox-view-controls">
          <label>Sort<select aria-label="Sort opportunities" value={sort} onChange={event => setSort(event.target.value as InboxSort)}>
            <option value="PRIORITY">Priority</option><option value="DEADLINE">Deadline</option><option value="NEWEST">Newest</option><option value="DECISION">Decision</option>
          </select></label>
          <label>Filter<select aria-label="Filter opportunities" value={filter} onChange={event => setFilter(event.target.value as InboxFilter)}>
            <option value="ALL">All</option><option value="APPLY">Apply</option><option value="PREPARE">Prepare</option><option value="WATCH">Watch</option><option value="SKIP">Skip</option>
          </select></label>
        </div>
      </div>
      <p className="queue-caption">{items.length} shown / {inbox.items.length} loaded{inbox.page.has_more ? ' \u00b7 More saved' : ''}</p>
      {opportunityId && !selectedVisible && <p className="queue-caption">{inbox.items.some(item => item.opportunity_id === opportunityId) ? 'Selected opportunity is hidden by your search or filter.' : 'Selected opportunity is not on this page.'}</p>}
      {items.length ? <ul className="scenario-queue inbox-queue" aria-label="Saved opportunities">{items.map((item, index) => <OpportunityRow key={item.opportunity_id} item={item}
        selected={item.opportunity_id === opportunityId} tabIndex={item.opportunity_id === entryId ? 0 : -1}
        rowRef={node => { if (node) rowRefs.current.set(item.opportunity_id, node); else rowRefs.current.delete(item.opportunity_id); }}
        onFocus={() => setFocusedId(item.opportunity_id)} onKeyDown={event => move(event, index)} />)}</ul>
        : <div className="queue-empty" role="status"><p>{search.trim() || filter !== 'ALL' ? 'No matches on this page. Change your search or filter.' : inbox.page.total ? 'No opportunities on this page.' : 'No saved opportunities.'}</p></div>}
    </> : <div className="queue-empty"><p>{error ? 'Queue unavailable' : 'Opening workspace\u2026'}</p></div>}
    <p className="queue-footnote">Saved in this workspace</p>
  </>;
}
