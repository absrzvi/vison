import { useEffect, useState } from 'react';
import { getApiHealth } from '../../api/health';
import './DegradedBanner.css';

const COPY =
  'AI alert quality is degraded. Nomad has been notified. Continue to verify alerts against CCTV as normal.';
const DISMISS_KEY = 'oebb-degraded-banner-dismissed';
const POLL_MS = 60_000;

// AC21: shown when GET /api/v1/health reports ai_quality_degraded.
// Dismissible per-session; reappears next session if the flag is still true.
export function DegradedBanner() {
  const [degraded, setDegraded] = useState(false);
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === '1',
  );

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      getApiHealth()
        .then(d => { if (!cancelled) setDegraded(Boolean(d.ai_quality_degraded)); })
        .catch(() => { if (!cancelled) setDegraded(false); });
    };
    check();
    const id = setInterval(check, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!degraded || dismissed) return null;

  return (
    <div className="degraded-banner" role="status">
      <span className="degraded-banner__copy">{COPY}</span>
      <button
        className="degraded-banner__dismiss"
        aria-label="Dismiss degraded quality banner"
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, '1');
          setDismissed(true);
        }}
      >
        &times;
      </button>
    </div>
  );
}
