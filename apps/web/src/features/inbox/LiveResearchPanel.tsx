import { useState } from 'react';
import type { FormEvent } from 'react';
import { useLiveResearch } from './useLiveResearch';

const STATUS_COPY = {
  STARTING: 'Starting research',
  RESEARCHING: 'Researching official sources',
  EVALUATING: 'Evaluating evidence',
  COMPLETED: 'Research complete',
  FAILED: 'Research could not complete',
  BUDGET_STOPPED: 'Research stopped at the safety budget',
} as const;

export function LiveResearchPanel({
  onOpportunityCreated = () => undefined,
  pollIntervalMs,
  maxPollAttempts,
}: {
  onOpportunityCreated?: () => void;
  pollIntervalMs?: number;
  maxPollAttempts?: number;
}) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [validation, setValidation] = useState<string | null>(null);
  const research = useLiveResearch({ onOpportunityCreated, pollIntervalMs, maxPollAttempts });

  async function submit(event: FormEvent) {
    event.preventDefault();
    const officialUrl = url.trim();
    if (!officialUrl.toLowerCase().startsWith('https://')) {
      setValidation('Enter an official HTTPS URL.');
      return;
    }
    setValidation(null);
    if (await research.start(officialUrl)) setOpen(false);
  }

  const status = research.status?.status;
  const terminal = status === 'FAILED' || status === 'BUDGET_STOPPED';
  const activeStatus = status === 'STARTING' || status === 'RESEARCHING' || status === 'EVALUATING';
  return <section className="live-research" aria-label="Live opportunity research">
    <button className="research-trigger" disabled={research.active} onClick={() => {
      research.reset();
      setValidation(null);
      setOpen(true);
    }}>Research opportunity <span aria-hidden="true">+</span></button>

    {open && !status && <form className="research-form" onSubmit={submit}>
      <div className="research-heading"><h3>Research opportunity</h3><button type="button" className="text-button" disabled={research.submitting} onClick={() => setOpen(false)}>Cancel</button></div>
      <p>QUALOR will verify official evidence before evaluating the opportunity.</p>
      <label>Official opportunity URL<input autoFocus value={url} required inputMode="url" autoComplete="url" placeholder="https://example.org/opportunity/rules" onChange={event => {
        setUrl(event.target.value);
        setValidation(null);
      }} /></label>
      {validation && <p className="research-error" role="alert">{validation}</p>}
      {research.error && <p className="research-error" role="alert">{research.error.message}</p>}
      <button className="research-start" type="submit" disabled={!url.trim() || research.submitting}>{research.submitting ? 'Starting research' : 'Start research'} <span aria-hidden="true">→</span></button>
    </form>}

    {(status || research.connectionUnavailable) && <div className={`research-status${terminal ? ' research-status--terminal' : ''}`} role="status" aria-live="polite">
      <span className="section-index">LIVE research</span>
      <p className="research-status-title">{research.connectionUnavailable ? 'Research status is temporarily unavailable.' : STATUS_COPY[status!]}</p>
      {status === 'FAILED' && <p>The run ended without a complete persisted opportunity.</p>}
      {status === 'BUDGET_STOPPED' && <p>Research stopped at the configured safety budget.</p>}
      {activeStatus && !research.connectionUnavailable && <span className="research-activity" aria-hidden="true" />}
      {terminal && <button className="text-button" onClick={() => {
        research.reset();
        setOpen(true);
      }}>Retry</button>}
    </div>}
  </section>;
}
