const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

if (!import.meta.env.VITE_API_URL) {
  console.warn('[health] VITE_API_URL not set — requests will hit the current origin');
}

// E10-S1 AC21: CC health summary with the server-computed degraded flag.
export async function getApiHealth(signal) {
  const res = await fetch(`${API_BASE}/api/v1/health`, {
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

export async function getSystemHealth(signal) {
  const res = await fetch(`${API_BASE}/api/v1/analytics/system-health`, {
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
