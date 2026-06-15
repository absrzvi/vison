// E11-S5 — admin Configuration screen. Lists the per-class confidence thresholds
// and the degraded-banner floor; an admin edits a value (inline 0.0–1.0 input) and
// saves it (PATCH → refetch). Admin-only: the route guard blocks operators and the
// server enforces require_role("admin") on the PATCH.
//
// Handles the three required states: loading, error, populated (control-centre
// CLAUDE.md). Saves refetch so the UI reflects server truth.
import { useState, useEffect, useCallback } from 'react';
import { listThresholds, patchThresholds } from '../../api/config';
import './Configuration.css';

// Build a flat, ordered row list from the {per_class, degraded_banner_floor} shape.
function toRows(cfg) {
  if (!cfg) return [];
  const rows = Object.entries(cfg.per_class ?? {}).map(([code, value]) => ({
    key: code,
    label: code,
    value,
    kind: 'per_class',
  }));
  rows.push({
    key: 'degraded_banner_floor',
    label: 'degraded_banner_floor',
    value: cfg.degraded_banner_floor,
    kind: 'floor',
  });
  return rows;
}

// Thresholds are 2-decimal calibration values; format for display so the number
// input shows "0.85" not the raw IEEE-754 "0.8500000238418579". Comparison for the
// dirty check uses the same formatting on both sides.
function fmt(v) {
  return Number(v).toFixed(2);
}

function ThresholdRow({ row, onSave }) {
  const [draft, setDraft] = useState(fmt(row.value));
  const [saving, setSaving] = useState(false);
  // A blank or non-numeric input must NOT be treated as a value: Number("") === 0
  // would coerce a cleared field to 0.0, and a 0.0 floor disables the degraded
  // banner. The floor must be strictly > 0; per-class allows >= 0. The server is
  // the authority (422), but the button stays disabled for an unsubmittable draft.
  const parsed = draft.trim() === '' ? NaN : Number(draft);
  const minAllowed = row.kind === 'floor' ? 0 : -Infinity; // floor: strictly > 0 below
  const valid =
    Number.isFinite(parsed) &&
    parsed <= 1 &&
    (row.kind === 'floor' ? parsed > minAllowed : parsed >= 0);
  const dirty = valid && parsed !== Number(fmt(row.value));

  const save = async () => {
    setSaving(true);
    try {
      await onSave(row, parsed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <tr>
      <td className="configuration-mono">{row.label}</td>
      <td>
        <input
          className="configuration-input"
          type="number"
          min="0"
          max="1"
          step="0.01"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          data-testid={`configuration-input-${row.key}`}
        />
      </td>
      <td>
        <button
          className="configuration-btn configuration-btn--primary"
          onClick={save}
          disabled={!dirty || saving}
          data-testid={`configuration-save-${row.key}`}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </td>
    </tr>
  );
}

export function Configuration() {
  const [cfg, setCfg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCfg(await listThresholds());
    } catch (err) {
      setError(err.message || 'Could not load configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch-on-mount; load() is a stable useCallback.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  const onSave = useCallback(async (row, value) => {
    setActionError(null);
    try {
      const patch = row.kind === 'floor'
        ? { degraded_banner_floor: value }
        : { per_class: { [row.key]: value } };
      await patchThresholds(patch);
      await load();
    } catch (err) {
      setActionError(err.message || 'Could not save threshold');
    }
  }, [load]);

  if (loading) {
    return (
      <div className="configuration" data-testid="configuration-loading">
        <p className="configuration-muted">Loading configuration…</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="configuration" data-testid="configuration-error">
        <p className="configuration-error" role="alert">{error}</p>
        <button className="configuration-btn" onClick={load}>Retry</button>
      </div>
    );
  }

  const rows = toRows(cfg);

  return (
    <div className="configuration" data-testid="configuration-screen">
      <div className="configuration__header">
        <h2 className="configuration__title">Configuration — confidence thresholds</h2>
      </div>
      <p className="configuration-muted">
        Per-class detection confidence thresholds (0.0–1.0) and the fleet degraded-banner floor.
        Changes apply without a redeploy.
      </p>
      {actionError && <p className="configuration-error" role="alert">{actionError}</p>}
      <table className="configuration-table">
        <thead>
          <tr><th>Key</th><th>Threshold (0.0–1.0)</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <ThresholdRow key={row.key} row={row} onSave={onSave} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
