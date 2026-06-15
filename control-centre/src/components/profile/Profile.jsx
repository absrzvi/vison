import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useFleetData } from '../../hooks/useFleetData';
import {
  ALERT_THRESHOLD_OPTIONS,
  STALENESS_THRESHOLD_OPTIONS,
  formatSec,
} from '../../constants/preferences';
import { SegmentedControl } from '../shell/SegmentedControl';
import './Profile.css';

// E11-S3 — the authenticated user's Profile screen. Identity header (username +
// role) over the two SERVER-BACKED preference controls (alert + staleness). The
// "unattended bag" control is deliberately NOT here: it persists only to
// localStorage today, and a setting that doesn't follow the user would contradict
// this screen's whole point (D5). Preference values flow through FleetContext
// (synchronous from localStorage, then GET-reconciled), so there is no spinner —
// the three required states are: populated (controls), error (save-failure toast),
// loading (effectively instant; the controls render immediately).
export function Profile() {
  const { username, role } = useAuth();
  const {
    alertThresholdSeconds,
    stalenessThresholdSeconds,
    updateAlertThreshold,
    updateStalenessThreshold,
  } = useFleetData();
  const [toast, setToast] = useState(null);
  const toastTimerRef = useRef(null);

  useEffect(() => () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); }, []);

  function showToast(msg) {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 4000);
  }

  async function handleAlertCommit(val) {
    const err = await updateAlertThreshold(val);
    if (err) showToast('Preference not saved — please retry');
  }

  async function handleStalenessCommit(val) {
    const err = await updateStalenessThreshold(val);
    if (err) showToast('Preference not saved — please retry');
  }

  return (
    <div className="profile-screen" data-testid="profile-screen">
      <header className="profile-header">
        <div className="profile-avatar" aria-hidden="true">
          {(username || '?').charAt(0).toUpperCase()}
        </div>
        <div className="profile-identity">
          <span className="profile-username" data-testid="profile-username">
            {username || '—'}
          </span>
          <span className="profile-role" data-testid="profile-role">{role || '—'}</span>
        </div>
      </header>

      <section className="profile-prefs" aria-label="Preferences">
        <h2 className="profile-prefs__title">Preferences</h2>
        <SegmentedControl
          label="Critical alert threshold"
          options={ALERT_THRESHOLD_OPTIONS}
          value={alertThresholdSeconds}
          onCommit={handleAlertCommit}
          formatLabel={formatSec}
        />
        <SegmentedControl
          label="Connection staleness warning"
          options={STALENESS_THRESHOLD_OPTIONS}
          value={stalenessThresholdSeconds}
          onCommit={handleStalenessCommit}
          formatLabel={formatSec}
        />
      </section>

      {toast && (
        <div className="profile-toast" role="alert">{toast}</div>
      )}
    </div>
  );
}
