const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

export async function getAiPipelineHealth(signal) {
  const res = await fetch(`${API_BASE}/api/v1/health/ai-pipeline`, {
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
