const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

export async function getSystemHealth() {
  const res = await fetch(`${API_BASE}/api/v1/analytics/system-health`, {
    headers: { 'X-API-Key': API_KEY },
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
