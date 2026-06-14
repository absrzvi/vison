import { authHeaders, handle401 } from '../lib/auth/authFetch';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

// 10-5 AC1: per-alert-class resolution-quality rates (no-action + explicit-FP).
export async function getResolutionRates(signal) {
  const res = handle401(await fetch(`${API_BASE}/api/v1/ai-quality/resolution-rates`, {
    headers: authHeaders(),
    signal,
  }));
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
