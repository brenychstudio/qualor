import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, fetchDraftPack } from '../../api/client';
import type { DraftPackView } from '../../generated/domain';
import { DraftPackSection } from './DraftPackSection';

/** A persisted reference is linked only when it already is an absolute http(s) URL. */
function citationUrl(reference: string): string | null {
  try {
    const parsed = new URL(reference);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? reference : null;
  } catch {
    return null;
  }
}

/** A recorded enum read as language. Lossless and presentational only: the exact recorded
 *  value is still printed verbatim in Traceability, and nothing here reinterprets it. */
function readable(value: string | null | undefined): string {
  if (!value) return 'Unrecorded';
  const words = value.toLowerCase().replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * The approved Application Pack, read-only by construction.
 *
 * Everything here is the persisted DraftPackView: section identity, order, titles, content,
 * attribution, references and missing fields. The document adds no answer, resolves no gap
 * and offers no way to change or send what the workspace recorded.
 */
export function ApplicationPack() {
  const { packId } = useParams();
  const [pack, setPack] = useState<DraftPackView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setPack(null); setError(null);
    if (!packId) { setError('No application pack was requested.'); return; }
    fetchDraftPack(packId, controller.signal)
      .then(value => {
        if (controller.signal.aborted) return;
        // An unrecognised payload is an unavailable pack, never a partially invented document.
        if (!value || !Array.isArray(value.sections) || !value.approved_snapshot) {
          throw new ApiError('INTERNAL_ERROR');
        }
        setPack(value);
      })
      .catch(readError => {
        if (controller.signal.aborted) return;
        setError(readError instanceof ApiError ? readError.message : 'The local controller could not read this application pack.');
      });
    return () => controller.abort();
  }, [packId]);

  if (error) return <section className="structural-state">
    <span className="eyebrow">Application pack</span>
    <h1>Application pack unavailable</h1>
    <p role="status">This application pack is unavailable. {error}</p>
    <Link className="inline-link" to="/inbox">Return to inbox ↗</Link>
  </section>;

  if (!pack) return <section className="structural-state" aria-live="polite">
    <span className="eyebrow">Application pack</span>
    <h1>Opening application pack</h1>
    <p>Reading the approved draft pack…</p>
  </section>;

  const bound = pack.approved_snapshot;
  const policies = Object.entries(bound.policy_versions);
  return <article className="application-pack" aria-label="Application pack">
    <header className="pack-masthead">
      <span className="pack-eyebrow">Approved application pack</span>
      <h1>Application pack</h1>
      <p className="pack-standfirst">
        Finished local document, prepared for human review. No external submission has occurred
        and nothing here is sent anywhere.
      </p>
      {/* The recorded preparation facts, read as language. Enough for a person to know what
          they are holding; the records behind it are gathered in Traceability below. */}
      <div role="group" aria-label="How this pack was prepared">
        <ul className="pack-preparation">
          <li>{readable(pack.content_kind)}</li>
          <li>{readable(pack.creator_kind)} preparation</li>
          <li>{readable(pack.mode)} research mode</li>
        </ul>
      </div>
    </header>

    {/* What QUALOR prepared comes before how it can be traced. */}
    <div className="pack-sections">
      {pack.sections.map(section => <DraftPackSection key={section.key} section={section} />)}
    </div>

    <div className="pack-block" role="group" aria-label="Missing information">
      <h2 className="pack-block-title">Missing information</h2>
      {pack.missing_fields.length === 0
        ? <p className="pack-block-note">No missing field is recorded for this pack.</p>
        : <>
          <p className="pack-block-note">{pack.missing_fields.length} recorded gaps remain unresolved. They are not answered here.</p>
          <ul className="pack-missing">{pack.missing_fields.map(field => <li key={field}>{field}</li>)}</ul>
        </>}
    </div>

    <div className="pack-block" role="group" aria-label="Source and evidence references">
      <h2 className="pack-block-title">Source and evidence references</h2>
      <p className="pack-block-note">Exactly the references the workspace recorded for this pack.</p>
      <ul className="pack-references">
        {pack.source_refs.map(reference => {
          const url = citationUrl(reference);
          return <li key={reference}>
            {url
              ? <a className="pack-citation" href={url} target="_blank" rel="noopener noreferrer external">{reference}</a>
              : <span>{reference}</span>}
          </li>;
        })}
      </ul>
      <ul className="pack-references">
        {pack.evidence_versions.map(entry => <li key={entry.evidence_id}>
          <span>{entry.evidence_id}</span><small>Version {entry.version}</small>
        </li>)}
      </ul>
    </div>

    {/* `group`, not the `region` a named section would otherwise be: the seven prepared
        sections are the regions of this document, and an eighth would make the count of what
        QUALOR prepared disagree with the pack the server recorded. */}
    <section className="pack-trace" role="group" aria-label="Traceability">
      <h2 className="pack-block-title">Traceability</h2>
      <p className="pack-block-note">Every record this pack was prepared from, exactly as the workspace recorded it.</p>

      <dl className="pack-attribution" aria-label="Pack attribution">
        <div><dt>Pack</dt><dd>{pack.id}<small>Version {pack.version}</small></dd></div>
        <div><dt>Approval</dt><dd>{pack.approval_id}<small>Version {pack.approval_version}</small></dd></div>
        <div><dt>Drafting job</dt><dd>{pack.draft_job_id}<small>Version {pack.draft_job_version}</small></dd></div>
        <div><dt>Actor</dt><dd>{pack.actor_id}</dd></div>
        <div><dt>Prepared by</dt><dd>{pack.creator_kind ?? 'Unrecorded'}</dd></div>
        <div><dt>Content kind</dt><dd>{pack.content_kind ?? 'Unrecorded'}</dd></div>
        <div><dt>Research mode</dt><dd>{pack.mode}</dd></div>
        <div><dt>Generated</dt><dd><time dateTime={pack.generated_at}>{pack.generated_at}</time></dd></div>
      </dl>

      <div className="pack-block" role="group" aria-label="Bound versions">
        <h3 className="pack-block-subtitle">Bound versions</h3>
        <p className="pack-block-note">The approval was recorded against exactly these versions.</p>
        <ul className="pack-versions">
          <li>Opportunity version {bound.opportunity_version}</li>
          <li>Profile version {bound.founder_profile_version}</li>
          <li>Project version {bound.project_version}</li>
          <li>Decision version {bound.decision_version}</li>
          {policies.map(([name, version]) => <li key={name}>Policy · {name} {String(version)}</li>)}
        </ul>
      </div>
    </section>

    <p className="pack-colophon">
      Draft prose is not verified evidence. Review every answer before using it. No external
      submission is available from this document.
    </p>
  </article>;
}
