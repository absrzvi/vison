import { authHeaders, handle401 } from '../lib/auth/authFetch';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

// Cache the in-flight promise so concurrent mounts share one request, but null it
// the instant the request settles in failure so a later re-login (same tab, after
// a 401 cleared the token) refetches instead of replaying the rejected promise.
let _inflight = null;

// AC20: thresholds fetched once on dashboard mount, cached for the session.
export function getConfidenceThresholds() {
  if (_inflight) return _inflight;
  _inflight = fetch(`${API_BASE}/api/v1/config/confidence-thresholds`, {
    headers: authHeaders(),
  }).then(handle401).then(res => {
    if (!res.ok) {
      const err = new Error(`API error ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }).catch(err => {
    _inflight = null; // failure is never cached — next call refetches
    throw err;
  });
  return _inflight;
}
