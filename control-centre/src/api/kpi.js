const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

// E10-S4: fleet-wide delay-minutes avoided over the trailing 24h. Slow-changing
// daily metric — fetched separately from the live SSE kpis (one-shot + interval),
// not pushed per-tick.
export async function getDelayMinutesAvoided(signal) {
  const res = await fetch(`${API_BASE}/api/v1/kpi/delay-minutes-avoided`, {
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
