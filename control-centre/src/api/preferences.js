import {
  DEFAULT_ALERT_THRESHOLD_SECONDS,
  DEFAULT_STALENESS_THRESHOLD_SECONDS,
} from '../constants/preferences';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

const FETCH_TIMEOUT_MS = 10000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

const _DEFAULTS = {
  threshold_sec: DEFAULT_ALERT_THRESHOLD_SECONDS,
  staleness_threshold_sec: DEFAULT_STALENESS_THRESHOLD_SECONDS,
};

/**
 * Fetch operator preferences. Returns defaults on 404 (no row saved yet).
 * Throws on network errors or unexpected non-404 error statuses.
 */
export async function getPreferences() {
  const res = await fetch(`${API_BASE}/api/v1/operators/me/preferences`, {
    method: 'GET',
    headers: { 'X-API-Key': API_KEY },
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (res.status === 404) return { ..._DEFAULTS };
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * Patch operator preferences. Throws on any non-200 response so the caller
 * can revert the UI and show an error toast.
 */
export async function patchPreferences(patch) {
  const res = await fetch(`${API_BASE}/api/v1/operators/me/preferences`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify(patch),
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    try {
      err.detail = await res.json();
    } catch { /* ignore parse failure */ }
    throw err;
  }
  return res.json();
}
