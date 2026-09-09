import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { apiRequest, ApiError } from '../../api/client';
import type { FounderProfile, ProjectProfile, PortfolioView, ProfileUpdateRequest, ProjectUpdateRequest, SessionView } from '../../generated/domain';

type Profile = FounderProfile | ProjectProfile;
type FieldKind = 'text' | 'list' | 'raw-list' | 'decimal' | 'integer' | 'boolean' | 'date' | 'select' | 'name';
interface FieldSpec { key: keyof FounderProfile | keyof ProjectProfile; label: string; kind: FieldKind; options?: readonly string[]; wide?: boolean; }
const founderFields: FieldSpec[] = [
  { key: 'country_of_residence', label: 'Country of residence', kind: 'text' },
  { key: 'citizenship', label: 'Citizenship', kind: 'text' },
  { key: 'legal_form', label: 'Legal form', kind: 'select', options: ['INDIVIDUAL', 'SOLE_TRADER', 'INCORPORATED_COMPANY', 'NONPROFIT'] },
  { key: 'incorporation_date', label: 'Incorporation date', kind: 'date' },
  { key: 'team_size', label: 'Team size', kind: 'integer' },
  { key: 'available_hours', label: 'Available hours', kind: 'decimal' },
  { key: 'open_source_willingness', label: 'Willing to open source', kind: 'boolean' },
  { key: 'strategic_goals', label: 'Strategic goals', kind: 'list', wide: true },
  { key: 'constraints', label: 'Constraints', kind: 'raw-list', wide: true },
];
const projectFields: FieldSpec[] = [
  { key: 'name', label: 'Project name', kind: 'name', wide: true },
  { key: 'problem', label: 'Problem', kind: 'text', wide: true },
  { key: 'audience', label: 'Audience', kind: 'text', wide: true },
  { key: 'stage', label: 'Stage', kind: 'select', options: ['IDEA', 'PROTOTYPE', 'MVP', 'PRODUCTION'] },
  { key: 'estimated_adaptation_hours', label: 'Adaptation hours', kind: 'decimal' },
  { key: 'available_features', label: 'Available features', kind: 'list', wide: true },
  { key: 'technology_stack', label: 'Technology stack', kind: 'list', wide: true },
  { key: 'code_provenance', label: 'Code origin', kind: 'select', options: ['ORIGINAL', 'REUSED', 'MIXED'] },
  { key: 'license_intent', label: 'Intended license', kind: 'text' },
  { key: 'is_new_project', label: 'New project', kind: 'boolean' },
  { key: 'has_sponsor_support', label: 'Sponsor support', kind: 'boolean' },
  { key: 'reuse_disclosed', label: 'Reuse disclosed', kind: 'boolean' },
  { key: 'reward_conditions_met', label: 'Reward conditions met', kind: 'boolean' },
  { key: 'prior_submissions', label: 'Prior submissions', kind: 'list', wide: true },
  { key: 'project_lineage', label: 'Project lineage', kind: 'list', wide: true },
  { key: 'reused_components', label: 'Reused components', kind: 'list', wide: true },
  { key: 'public_evidence_refs', label: 'Public evidence references', kind: 'raw-list', wide: true },
];
function fieldValue(record: Profile, field: FieldSpec): string {
  const entry: unknown = record[field.key as keyof Profile];
  const value = entry && typeof entry === 'object' && 'value' in entry ? entry.value : entry;
  if (value === undefined || value === null || value === 'UNKNOWN') return '';
  if (Array.isArray(value)) return value.join('\n');
  return String(value);
}
function parseField(value: string, field: FieldSpec): unknown {
  const text = value.trim();
  if (field.kind === 'name') {
    if (!text) throw new Error('Project name is required.');
    return text;
  }
  if (field.kind === 'raw-list') return text ? text.split('\n').map(item => item.trim()).filter(Boolean) : [];
  let parsed: unknown = text || null;
  if (text && field.kind === 'integer') {
    if (!/^[1-9]\d*$/.test(text) || !Number.isSafeInteger(Number(text))) throw new Error(`${field.label} must be a whole number of at least 1.`);
    parsed = Number(text);
  }
  if (text && field.kind === 'decimal' && !/^\d+(\.\d+)?$/.test(text)) throw new Error(`${field.label} must be a non-negative decimal number.`);
  if (text && field.kind === 'date') {
    const date = new Date(`${text}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== text) throw new Error(`${field.label} must be a valid calendar date.`);
  }
  if (text && field.kind === 'boolean') parsed = text === 'true';
  if (text && field.kind === 'list') parsed = text.split('\n').map(item => item.trim()).filter(Boolean);
  return { value: parsed, provenance: parsed === null ? 'UNKNOWN' : 'USER_ASSERTED', evidence_refs: [] };
}
function label(value: string) { return value.charAt(0) + value.slice(1).toLowerCase().replaceAll('_', ' '); }

interface Props {
  record: Profile;
  kind: 'founder' | 'project';
  isNew?: boolean;
  session: SessionView | null;
  onSaved: (portfolio: PortfolioView) => void;
}
export function ProfileForm({ record, kind, isNew = false, session, onSaved }: Props) {
  // Each form owns its loaded version and edits. A sibling save may return a new
  // portfolio snapshot but cannot silently replace this form's pending work.
  const [base, setBase] = useState(record);
  const [editing, setEditing] = useState(isNew && kind === 'project');
  const editButton = useRef<HTMLButtonElement>(null);
  const editRegion = useRef<HTMLFormElement>(null);
  const [expectedVersion, setExpectedVersion] = useState(isNew ? 0 : record.version);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [hasError, setHasError] = useState(false);
  const submitLock = useRef(false);
  const projectName = useRef<HTMLInputElement>(null);
  useEffect(() => { if (editing) { if (kind === 'project') projectName.current?.focus(); else editRegion.current?.focus({ preventScroll: true }); } }, [editing, kind]);
  const prefix = useId();
  const fields = kind === 'founder' ? founderFields : projectFields;
  const readOnly = !session || session.read_only || !session.action_token;
  const dirty = Object.keys(edits).length > 0;
  const money = kind === 'founder' ? (base as FounderProfile).max_cash_commitment?.value : null;
  const cashAmount = edits.cashAmount ?? money?.amount ?? '';
  const cashCurrency = edits.cashCurrency ?? money?.currency ?? '';
  function returnToDossier(discard: boolean) {
    if (discard) { setEdits({}); setFeedback(''); setHasError(false); }
    setEditing(false);
    requestAnimationFrame(() => editButton.current?.focus());
  }
  function change(key: string, value: string) { setEdits(previous => ({ ...previous, [key]: value })); setFeedback(''); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (readOnly || submitLock.current) return;
    setFeedback(''); setHasError(false);
    const patch: Record<string, unknown> = {};
    try {
      for (const field of fields) {
        const value = edits[field.key] ?? fieldValue(base, field);
        // Validate required names on creation as well as edited fields.
        if (field.kind === 'name' || (field.key in edits && value !== fieldValue(base, field))) patch[field.key] = parseField(value, field);
      }
      if (kind === 'founder' && ('cashAmount' in edits || 'cashCurrency' in edits) &&
          (cashAmount.trim() !== (money?.amount ?? '') || cashCurrency.trim() !== (money?.currency ?? ''))) {
        if (!cashAmount.trim() && !cashCurrency.trim()) patch.max_cash_commitment = { value: null, provenance: 'UNKNOWN', evidence_refs: [] };
        else {
          if (!/^\d+(\.\d+)?$/.test(cashAmount.trim()) || !/^[A-Z]{3}$/.test(cashCurrency.trim())) throw new Error('Cash commitment needs a non-negative amount and a three-letter currency code.');
          patch.max_cash_commitment = { value: { amount: cashAmount.trim(), currency: cashCurrency.trim() }, provenance: 'USER_ASSERTED', evidence_refs: [] };
        }
      }
    } catch (error) { setFeedback(error instanceof Error ? error.message : 'Check the entered values.'); setHasError(true); return; }
    submitLock.current = true; setPending(true);
    try {
      const updated = { ...base, ...patch };
      const body: ProfileUpdateRequest | ProjectUpdateRequest = kind === 'founder'
        ? { expected_version: expectedVersion, profile: updated as FounderProfile }
        : { expected_version: expectedVersion, project: updated as ProjectProfile };
      const portfolio = await apiRequest<PortfolioView>(kind === 'founder' ? '/profile' : `/projects/${encodeURIComponent(base.id)}`, { method: 'PUT', actionToken: session.action_token, body });
      const saved = kind === 'founder' ? portfolio.founder : portfolio.projects.find(project => project.id === base.id);
      if (!saved) throw new ApiError('INTERNAL_ERROR');
      setBase(saved); setExpectedVersion(saved.version); setEdits({});
      setFeedback(kind === 'founder' ? 'Founder profile saved.' : 'Project saved.');
      onSaved(portfolio);
    } catch (error) { setHasError(true); setFeedback(error instanceof ApiError ? error.message : 'The update could not be saved. Your edits are preserved.'); }
    finally { submitLock.current = false; setPending(false); }
  }
  if (!editing || readOnly) return <section className={`profile-dossier dossier-${kind}`} aria-label={kind === 'founder' ? 'Founder dossier' : `Project dossier ${(base as ProjectProfile).name}`}>
    <div className="dossier-heading"><div><span className="section-index">{kind === 'founder' ? 'Portfolio / founder' : 'Portfolio / project'}</span><h2>{kind === 'founder' ? 'Founder profile' : (base as ProjectProfile).name || 'New project'}</h2></div><div className="dossier-control"><span className="quiet">{expectedVersion ? `Version ${expectedVersion}` : 'Not saved yet'}</span>{!readOnly && <button ref={editButton} type="button" className="text-button" aria-label={kind === 'founder' ? 'Edit founder profile' : `Edit ${(base as ProjectProfile).name || 'New project'}`} onClick={() => setEditing(true)}>Edit ↗</button>}</div></div>
    {dirty && <p className="form-note" role="status">Unsaved changes retained</p>}
    <dl className="dossier-facts">{fields.filter(field => field.kind !== 'name').map(field => {
      const value = fieldValue(base, field);
      const fact: unknown = base[field.key as keyof Profile];
      const provenance = fact && typeof fact === 'object' && 'provenance' in fact ? String(fact.provenance) : null;
      const knownEmptyList = !!fact && typeof fact === 'object' && 'value' in fact && Array.isArray(fact.value) && fact.value.length === 0 && provenance !== null && provenance !== 'UNKNOWN';
      return <div key={field.key} className={`dossier-fact dossier-fact--${field.key}${field.wide ? ' dossier-fact--wide' : ''}`}><dt>{field.label}</dt><dd className={!value && !knownEmptyList ? 'unknown-fact' : ''}>{value ? field.kind === 'boolean' ? value === 'true' ? 'Yes' : 'No' : field.kind === 'select' ? label(value) : value : field.kind === 'raw-list' || knownEmptyList ? 'None recorded' : 'UNKNOWN'}</dd>{(value || knownEmptyList) && provenance && <small>{provenance}</small>}</div>;
    })}{kind === 'founder' && <div className="dossier-fact dossier-fact--cash"><dt>Maximum cash commitment</dt><dd className={!money ? 'unknown-fact' : ''}>{money ? `${money.amount} ${money.currency}` : 'UNKNOWN'}</dd>{money && <small>{(base as FounderProfile).max_cash_commitment?.provenance}</small>}</div>}
    {kind === 'project' && <div className="dossier-fact dossier-fact--wide"><dt>Material readiness</dt><dd>{(base as ProjectProfile).material_readiness?.map(item => `${label(item.kind)} · ${item.ready?.value === true ? 'Ready' : item.ready?.value === false ? 'Not ready' : 'UNKNOWN'}`).join('\n') || 'UNKNOWN'}</dd></div>}</dl>
    <p className="dossier-link">{kind === 'founder' ? 'ENTITY → ELIGIBILITY     /     CAPACITY → EFFORT FEASIBILITY' : 'PROJECT STAGE → READINESS'}</p>
    {feedback && <p className="form-feedback" role={hasError ? 'alert' : 'status'}>{feedback}</p>}
  </section>;
  return <form ref={editRegion} tabIndex={-1} className="profile-form" aria-label={kind === 'founder' ? 'Founder profile' : `Project ${(base as ProjectProfile).name || 'New project'}`} onSubmit={save} noValidate>
    <div className="form-heading"><h2>{kind === 'founder' ? 'Founder profile' : (base as ProjectProfile).name || 'New project'}</h2><span>{expectedVersion ? `Version ${expectedVersion}` : 'Not saved yet'}</span></div>
    <p className="form-note">{kind === 'founder' ? 'The facts that shape your eligibility and capacity.' : 'Describe the work you can bring to an opportunity.'} Blank facts remain UNKNOWN.</p>
    <div className="edit-mode-bar"><span className="section-index">Local edit</span><button type="button" className="text-button" disabled={pending} onClick={() => returnToDossier(false)}>Back to dossier</button><button type="button" className="text-button" disabled={pending} onClick={() => returnToDossier(true)}>Cancel changes</button></div>
    <fieldset className="form-fields" disabled={pending}>
      {(kind === 'founder' ? [fields.slice(0, 4), fields.slice(4)] : [fields]).map((group, groupIndex) => <fieldset className="field-group" key={groupIndex}>
        <legend>{kind === 'founder' ? groupIndex === 0 ? 'Identity' : 'Constraints & capacity' : 'Project facts'}</legend>
        <div className="field-group-grid">
      {group.map(field => <div className={`form-field${field.wide ? ' form-field--wide' : ''}`} key={field.key}>
        <div className="field-label"><label htmlFor={`${prefix}-${field.key}`}>{field.label}</label>{field.kind !== 'name' && field.kind !== 'raw-list' && !(edits[field.key] ?? fieldValue(base, field)) && <span id={`${prefix}-${field.key}-state`} className="field-state">UNKNOWN</span>}</div>
        {field.kind === 'select' || field.kind === 'boolean' ? <select id={`${prefix}-${field.key}`} aria-describedby={!(edits[field.key] ?? fieldValue(base, field)) ? `${prefix}-${field.key}-state` : undefined} value={edits[field.key] ?? fieldValue(base, field)} disabled={readOnly} onChange={event => change(field.key, event.target.value)}>
          <option value="">UNKNOWN</option>
          {field.kind === 'boolean' ? <><option value="true">Yes</option><option value="false">No</option></> : field.options?.map(option => <option value={option} key={option}>{label(option)}</option>)}
        </select> : field.kind === 'list' || field.kind === 'raw-list' ? <textarea id={`${prefix}-${field.key}`} aria-describedby={field.kind !== 'raw-list' && !(edits[field.key] ?? fieldValue(base, field)) ? `${prefix}-${field.key}-state` : undefined} value={edits[field.key] ?? fieldValue(base, field)} readOnly={readOnly} placeholder={field.kind === 'list' ? 'UNKNOWN · One item per line' : 'None recorded · One item per line'} onChange={event => change(field.key, event.target.value)} />
          : <input ref={field.kind === 'name' ? projectName : undefined} id={`${prefix}-${field.key}`} aria-describedby={field.kind !== 'name' && !(edits[field.key] ?? fieldValue(base, field)) ? `${prefix}-${field.key}-state` : undefined} value={edits[field.key] ?? fieldValue(base, field)} readOnly={readOnly} type="text" inputMode={field.kind === 'decimal' ? 'decimal' : field.kind === 'integer' ? 'numeric' : undefined} placeholder={field.kind === 'name' ? 'Name your project' : field.kind === 'date' ? 'UNKNOWN · YYYY-MM-DD' : 'UNKNOWN'} onChange={event => change(field.key, event.target.value)} />}
      </div>)}
      {kind === 'founder' && groupIndex === 1 && <>
        <div className="form-field"><label htmlFor={`${prefix}-cash`}>Maximum cash commitment</label><input id={`${prefix}-cash`} inputMode="decimal" value={cashAmount} placeholder="UNKNOWN" readOnly={readOnly} onChange={event => change('cashAmount', event.target.value)} /></div>
        <div className="form-field"><label htmlFor={`${prefix}-currency`}>Currency</label><input id={`${prefix}-currency`} value={cashCurrency} placeholder="UNKNOWN · e.g. EUR" readOnly={readOnly} maxLength={3} onChange={event => change('cashCurrency', event.target.value.toUpperCase())} /></div>
      </>}
        </div>
      </fieldset>)}
    </fieldset>
    {feedback && <p className="form-feedback" role={hasError ? 'alert' : 'status'}>{feedback}</p>}
    {!readOnly && <div className="form-footer"><button className="primary-action" type="submit" disabled={pending}>{pending ? 'Saving…' : kind === 'founder' ? 'Save founder profile' : 'Save project'}</button><span className="quiet">{dirty ? 'Unsaved changes' : 'Updates are saved as a new version.'}</span></div>}
  </form>;
}
