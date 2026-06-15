// E11-S1 — JWT token store. In-memory (authoritative for the session) mirrored
// to sessionStorage so a page reload within the tab keeps the user logged in.
// sessionStorage (not localStorage) so the token does not outlive the tab.

const STORAGE_KEY = 'oebb_cc_token';

// sessionStorage is absent in non-browser contexts (e.g. the node test env).
// Fall back to in-memory only so importing this module never throws.
const _storage = typeof sessionStorage !== 'undefined' ? sessionStorage : null;

let _token = _storage?.getItem(STORAGE_KEY) || null;

export function getToken() {
  return _token;
}

export function setToken(token) {
  _token = token;
  if (!_storage) return;
  if (token) {
    _storage.setItem(STORAGE_KEY, token);
  } else {
    _storage.removeItem(STORAGE_KEY);
  }
}

export function clearToken() {
  setToken(null);
}

// Decode the `role` claim from the current JWT for UI gating ONLY (show/hide the
// admin screens). NOT a security boundary — the server independently enforces
// require_role on every admin endpoint (E11-S2). No signature check is done or
// needed here; a forged role only changes what the UI renders, never what the API
// permits. Returns null if there is no token or it can't be parsed.
export function getRole() {
  return _claim('role');
}

// Decode the `username` claim from the current JWT, for display on the Profile
// screen (E11-S3). Display-only, same non-security caveat as getRole().
export function getUsername() {
  return _claim('username');
}

function _claim(name) {
  if (!_token) return null;
  try {
    const payload = _token.split('.')[1];
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json)[name] ?? null;
  } catch {
    return null;
  }
}
