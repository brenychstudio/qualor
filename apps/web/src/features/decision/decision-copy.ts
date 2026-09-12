import type { Recommendation } from '../../generated/domain';

export const RECOMMENDATION_LABELS: Record<Recommendation, string> = {
  APPLY: 'APPLY',
  PREPARE: 'PREPARE',
  WATCH: 'WATCH',
  SKIP: 'SKIP',
};

export const PRIMARY_CTA_LABELS: Record<Recommendation, string> = {
  APPLY: 'Approve application',
  PREPARE: 'Approve preparation',
  WATCH: 'Resolve unknowns',
  SKIP: 'Review rejection',
};

/** Shorter labels for the compact Decision Field lane.
 *
 * The lane's value slot is a few characters wide by design — it carries PASS, 8–14 h, 0 gaps —
 * and the owned fixture's recorded project name is long enough to become the loudest thing in
 * the causal field. This maps that whole recorded name to a label sized for that one slot.
 *
 * Whole-string matches, and only for values this product owns and ships for evaluation. There
 * is deliberately no length rule and no truncation: a real organiser's project name is never
 * rewritten here, it wraps inside the lane geometry that exists for exactly that reason. The
 * recorded name stays on the value's `title` and in the queue card whichever branch is taken,
 * so nothing displayed here is the only place the authoritative value can be read.
 *
 * A Map rather than an object literal: the key is a recorded project name, and a name like
 * "constructor" would find something on an object literal's prototype and be rendered instead
 * of the name itself.
 */
export const LANE_LABEL_ALIASES = new Map<string, string>([
  ['Synthetic Eligibility Demonstrator', 'Synthetic demo'],
]);

export const DECISION_COPY = {
  unresolvedRecommendation: 'UNKNOWN',
  unresolvedReason: 'No deterministic decision reason is available.',
  unresolvedProject: 'Unresolved',
  unavailableFact: 'UNKNOWN',
  unavailableStrategy: 'Not enough evidence',
  unavailableDeadline: 'Deadline unavailable',
  dateOnlyDeadline: 'Time unknown · date only',
} as const;
