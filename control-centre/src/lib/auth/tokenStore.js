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
