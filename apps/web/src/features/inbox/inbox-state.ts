import type { DeadlineView, InboxItem, Recommendation } from '../../generated/domain';

export type InboxSort = 'PRIORITY' | 'DEADLINE' | 'NEWEST' | 'DECISION';
export type InboxFilter = 'ALL' | Recommendation;

// Recommendation enum order is only the DECISION view; priority remains server-owned.
const decisionOrder: Record<Recommendation, number> = { APPLY: 0, PREPARE: 1, WATCH: 2, SKIP: 3 };
function stableOrder(a: InboxItem, b: InboxItem) {
  return a.priority_rank - b.priority_rank || (a.opportunity_id < b.opportunity_id ? -1 : a.opportunity_id > b.opportunity_id ? 1 : 0);
}
type Instant = { wholeSecond: number; fraction: string };
function parseInstant(value: string): Instant | null {
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$/i.exec(value);
  if (!match) return null;
  const wholeSecond = Date.parse(`${match[1]}${match[3]}`);
  // Date handles the explicit offset; keep fractions separately so microseconds
  // survive its millisecond limit. Removing trailing zeroes makes equal fractions tie.
  return Number.isFinite(wholeSecond) ? { wholeSecond, fraction: (match[2] ?? '').replace(/0+$/, '') } : null;
}
function compareInstants(a: Instant, b: Instant): number {
  return a.wholeSecond - b.wholeSecond || (a.fraction < b.fraction ? -1 : a.fraction > b.fraction ? 1 : 0);
}
function earliestInstant(deadline: DeadlineView): Instant | null {
  if (deadline.timezone_status !== 'UTC' || !deadline.values.length) return null;
  let earliest: Instant | null = null;
  for (const value of deadline.values) {
    const instant = parseInstant(value);
    if (!instant) return null;
    if (!earliest || compareInstants(instant, earliest) < 0) earliest = instant;
  }
  return earliest;
}
function deadlineOrder(deadline: DeadlineView, now: Instant): [number, Instant | null] {
  const earliest = earliestInstant(deadline);
  // V1 deadline buckets: earliest reliable future, unknown, past (rank breaks ties).
  return earliest === null ? [1, null] : compareInstants(earliest, now) <= 0 ? [2, null] : [0, earliest];
}
export function visibleInboxItems(items: readonly InboxItem[], sort: InboxSort, filter: InboxFilter, search: string, now: number): InboxItem[] {
  const query = search.trim().toLowerCase();
  const currentInstant: Instant = { wholeSecond: Math.floor(now / 1000) * 1000, fraction: String(now % 1000).padStart(3, '0').replace(/0+$/, '') };
  return items.filter(item => (filter === 'ALL' || (item.presentation_state === 'EVALUATED' && item.recommendation === filter))
    && (!query || item.program_name.toLowerCase().includes(query) || item.organizer.toLowerCase().includes(query)))
    .sort((a, b) => {
      let order = 0;
      if (sort === 'DEADLINE') {
        const left = deadlineOrder(a.deadline, currentInstant); const right = deadlineOrder(b.deadline, currentInstant);
        order = left[0] - right[0] || (left[1] && right[1] ? compareInstants(left[1], right[1]) : 0);
      } else if (sort === 'NEWEST') {
        const left = parseInstant(a.discovered_at); const right = parseInstant(b.discovered_at);
        order = left && right ? compareInstants(right, left) : 0;
      }
      else if (sort === 'DECISION') order = (a.recommendation === null ? 4 : decisionOrder[a.recommendation]) - (b.recommendation === null ? 4 : decisionOrder[b.recommendation]);
      return order || stableOrder(a, b);
    });
}
export function deadlineLabel(deadline: DeadlineView): string {
  const instant = earliestInstant(deadline);
  if (instant !== null) return `${new Date(instant.wholeSecond).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
  if (deadline.timezone_status === 'CALENDAR_DATE_ONLY' && deadline.values.length) return `${[...deadline.values].sort()[0]} \u00b7 time unknown`;
  return 'Deadline unknown';
}
