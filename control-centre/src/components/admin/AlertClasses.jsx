// E11-S4 — admin Alert Classes screen. Lists the kill-switch state of each alert
// class and toggles disable/enable. Admin-only: the route guard blocks operators,
// and the server enforces require_role("admin") on every call.
//
// Handles the three required states: loading, error, populated (control-centre
// CLAUDE.md). Mutations refetch the list so the UI reflects server truth.
import { useState, useEffect, useCallback } from 'react';
import { listAlertClasses, disableAlertClass, enableAlertClass } from '../../api/alertClasses';
import './AlertClasses.css';

// A class with no row yet is implicitly enabled (the kill-switch only stores
// disabled/re-enabled state). Treat anything other than "disabled" as enabled.
function isDisabled(row) {
  return row.state === 'disabled';
}

export function AlertClasses() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await listAlertClasses();
      setRows(body.alert_classes ?? []);
    } catch (err) {
      setError(err.message || 'Could not load alert classes');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch-on-mount; load() is a stable useCallback. The synchronous setLoading
  // inside load is the intended initial-load transition, not a render cascade.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  const runAction = useCallback(async (fn) => {
    setActionError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setActionError(err.message || 'Action failed');
    }
  }, [load]);

  const toggle = (row) =>
    runAction(() =>
      isDisabled(row) ? enableAlertClass(row.alert_code) : disableAlertClass(row.alert_code)
    );

  if (loading) {
    return (
      <div className="alert-classes" data-testid="alert-classes-loading">
        <p className="alert-classes-muted">Loading alert classes…</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="alert-classes" data-testid="alert-classes-error">
        <p className="alert-classes-error" role="alert">{error}</p>
        <button className="alert-classes-btn" onClick={load}>Retry</button>
      </div>
    );
  }

  return (
    <div className="alert-classes" data-testid="alert-classes-screen">
      <div className="alert-classes__header">
        <h2 className="alert-classes__title">Alert Classes</h2>
      </div>
      {actionError && <p className="alert-classes-error" role="alert">{actionError}</p>}
      <table className="alert-classes-table">
        <thead>
          <tr><th>Alert class</th><th>State</th><th>Last changed by</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const disabled = isDisabled(row);
            const lastBy = disabled ? row.disabled_by : row.enabled_by;
            const lastAt = disabled ? row.disabled_at : row.enabled_at;
            return (
              <tr key={row.alert_code}>
                <td className="alert-classes-mono">{row.alert_code}</td>
                <td>
                  <span
                    className={`alert-classes-pill ${disabled ? 'alert-classes-pill--disabled' : 'alert-classes-pill--enabled'}`}
                  >
                    {disabled ? 'disabled' : 'enabled'}
                  </span>
                </td>
                <td className="alert-classes-muted">
                  {lastBy || '—'}{lastAt ? ` (${lastAt})` : ''}
                </td>
                <td>
                  <button
                    className="alert-classes-btn"
                    onClick={() => toggle(row)}
                    data-testid={`alert-classes-toggle-${row.alert_code}`}
                  >
                    {disabled ? 'Enable' : 'Disable'}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p className="alert-classes-muted">
          No alert classes have been toggled yet — all classes are active.
        </p>
      )}
    </div>
  );
}
