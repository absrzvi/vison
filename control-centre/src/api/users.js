// E11-S2 — admin user-management API client. All calls go through the shared
// Bearer/401 helpers (authHeaders + handle401). Every endpoint is admin-gated on
// the server (require_role("admin")) — a non-admin token gets 403.
import { authHeaders, handle401 } from '../lib/auth/authFetch';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const FETCH_TIMEOUT_MS = 10000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

async function _send(path, { method = 'GET', body } = {}) {
  const res = handle401(await fetch(`${API_BASE}/api/v1/admin/users${path}`, {
    method,
    headers: authHeaders(body ? { 'Content-Type': 'application/json' } : {}),
    body: body ? JSON.stringify(body) : undefined,
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

export function listUsers() {
  return _send('');
}

export function createUser({ username, password, role }) {
  return _send('', { method: 'POST', body: { username, password, role } });
}

export function patchUser(userId, patch) {
  return _send(`/${userId}`, { method: 'PATCH', body: patch });
}

export function resetPassword(userId, password) {
  return _send(`/${userId}/reset-password`, { method: 'POST', body: { password } });
}
