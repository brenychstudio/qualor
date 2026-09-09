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

export const DECISION_COPY = {
  unresolvedRecommendation: 'UNKNOWN',
  unresolvedReason: 'No deterministic decision reason is available.',
  unresolvedProject: 'Unresolved',
  unavailableFact: 'UNKNOWN',
  unavailableStrategy: 'Not enough evidence',
  unavailableDeadline: 'Deadline unavailable',
  dateOnlyDeadline: 'Time unknown · date only',
} as const;
