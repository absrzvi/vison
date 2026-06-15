// E11-S4 — admin alert-class kill-switch API client. All calls go through the
// shared Bearer/401 helpers (authHeaders + handle401). Every endpoint is
// admin-gated on the server (require_role("admin")) — a non-admin token gets 403.
// The disable/enable POSTs carry no body: the audit actor is the token's username.
import { authHeaders, handle401 } from '../lib/auth/authFetch';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const FETCH_TIMEOUT_MS = 10000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

async function _send(path, { method = 'GET' } = {}) {
  const res = handle401(await fetch(`${API_BASE}/api/v1/admin/alert-classes${path}`, {
    method,
    headers: authHeaders({}),
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  }));
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json())?.detail?.detail;
    } catch {
      detail = undefined;
    }
    const err = new Error(detail || `API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

export function listAlertClasses() {
  return _send('');
}

export function disableAlertClass(alertCode) {
  return _send(`/${encodeURIComponent(alertCode)}/disable`, { method: 'POST' });
}

export function enableAlertClass(alertCode) {
  return _send(`/${encodeURIComponent(alertCode)}/enable`, { method: 'POST' });
}
