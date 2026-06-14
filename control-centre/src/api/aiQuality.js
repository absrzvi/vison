const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

// 10-5 AC1: per-alert-class resolution-quality rates (no-action + explicit-FP).
export async function getResolutionRates(signal) {
  const res = await fetch(`${API_BASE}/api/v1/ai-quality/resolution-rates`, {
    headers: { 'X-API-Key': API_KEY },
    signal,
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
