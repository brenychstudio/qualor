import type { DraftPackSection as Section } from '../../generated/domain';

type Material = 'Draft prose' | 'Source evidence' | 'Deterministic record' | 'Recorded content';

/**
 * Material kind per canonical section key. The server owns section identity, order and
 * content; this only tells the reader which frame they are looking at, so generated
 * narrative can never be mistaken for verified source material.
 *
 * An unrecognised key falls back to the neutral label rather than claiming an authority
 * the workspace did not state, and its content is still rendered in full.
 */
const MATERIAL: Record<string, Material> = {
  SUBMISSION_SUMMARY: 'Deterministic record',
  PROJECT_FIT_NARRATIVE: 'Draft prose',
  ELIGIBILITY_CHECKLIST: 'Deterministic record',
  REQUIRED_DELIVERABLES: 'Deterministic record',
  EVIDENCE_REFERENCES: 'Source evidence',
  READINESS_GAPS: 'Deterministic record',
  SUGGESTED_APPLICATION_ANSWERS: 'Draft prose',
};

const MODIFIER: Record<Material, string> = {
  'Draft prose': 'draft',
  'Source evidence': 'source',
  'Deterministic record': 'record',
  'Recorded content': 'record',
};

const readable = (key: string) => key.replaceAll('_', ' ').toLowerCase();

export function DraftPackSection({ section }: { section: Section }) {
  const material = MATERIAL[section.key] ?? 'Recorded content';
  const content = section.content.trim();
  const refs = section.evidence_refs ?? [];
  return <section
    className={`pack-section pack-section--${MODIFIER[material]}`}
    data-section-key={section.key}
    aria-label={readable(section.key)}
  >
    <div className="pack-section-heading">
      <h2>{section.title}</h2>
      <span className="pack-material">{material}</span>
    </div>
    {content
      ? <p className="pack-section-content">{content}</p>
      : <p className="pack-section-content pack-section-empty">No content recorded for this section.</p>}
    {refs.length > 0 && <p className="pack-section-refs">Evidence: {refs.join(' · ')}</p>}
  </section>;
}
