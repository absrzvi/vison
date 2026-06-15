// E11-S5 — admin confidence-threshold config client. Mirrors api/alertClasses.js
// (shared authHeaders + handle401 Bearer helpers). The GET is operator-readable
// on the server; the PATCH is admin-gated (require_role("admin")) — a non-admin
// token gets 403. Do NOT confuse with the read-only api/confidenceThresholds.js
// (session-cached GET consumed by UnifiedFeed) — this client is write-capable and
// used only by the admin Configuration screen.
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
  const res = handle401(await fetch(`${API_BASE}/api/v1/config${path}`, {
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

export function listThresholds() {
  return _send('/confidence-thresholds');
}

// patch: { per_class?: { [code]: number }, degraded_banner_floor?: number }
export function patchThresholds(patch) {
  return _send('/confidence-thresholds', { method: 'PATCH', body: patch });
}
