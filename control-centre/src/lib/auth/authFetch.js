// E11-S1 — central authenticated fetch. Injects the JWT Bearer header on every
// API call and converts a 401 into a single app-wide "session expired" signal:
// the token is cleared and a listener (AuthContext) redirects to /login.
//
// Every src/api/*.js call goes through authHeaders()/handle401 so the
// X-API-Key → Bearer swap lives in one place (replaces the per-file
// VITE_API_KEY header).

import { getToken, clearToken } from './tokenStore';

const _listeners = new Set();

// AuthContext subscribes so a 401 anywhere triggers logout+redirect once.
export function onUnauthorized(listener) {
  _listeners.add(listener);
  return () => _listeners.delete(listener);
}

function _emitUnauthorized() {
  clearToken();
  for (const l of _listeners) l();
}

// Authorization header for a fetch init. Returns {} when no token (the request
// will 401 and trigger the redirect).
export function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : { ...extra };
}

// Inspect a response; on 401 fire the global unauthorized signal. Returns the
// response unchanged so callers keep their existing error handling.
export function handle401(res) {
  if (res.status === 401) _emitUnauthorized();
  return res;
}

// Convenience wrapper: fetch with the Bearer header attached and 401 handled.
export async function authFetch(input, init = {}) {
  const res = await fetch(input, { ...init, headers: authHeaders(init.headers) });
  return handle401(res);
}
