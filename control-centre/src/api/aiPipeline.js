import { authHeaders, handle401 } from '../lib/auth/authFetch';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export async function getAiPipelineHealth(signal) {
  const res = handle401(await fetch(`${API_BASE}/api/v1/health/ai-pipeline`, {
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
