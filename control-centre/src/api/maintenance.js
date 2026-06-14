import { authHeaders, handle401 } from '../lib/auth/authFetch';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

const FETCH_TIMEOUT_MS = 10000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

export async function raiseMaintenanceTicket(trainId, issueSummary, raisedBy) {
  const res = handle401(await fetch(`${API_BASE}/api/v1/maintenance/tickets`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ train_id: trainId, issue_summary: issueSummary, raised_by: raisedBy }),
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  }));
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
