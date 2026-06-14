// E11-S1 — auth API: login (public) + logout. login mints a JWT against the
// cloud-backend; the token store + Bearer header are handled in lib/auth.
import { setToken, clearToken } from '../lib/auth/tokenStore';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

/**
 * Exchange username+password for a JWT. Stores the token on success.
 * Throws an Error with `.status` on failure (401 = bad credentials).
 */
export async function login(username, password) {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = new Error(res.status === 401 ? 'Invalid username or password' : `Login failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  const body = await res.json();
  setToken(body.access_token);
  return body;
}

export function logout() {
  clearToken();
}
