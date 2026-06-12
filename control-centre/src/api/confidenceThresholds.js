const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

let _cache = null;

// AC20: thresholds fetched once on dashboard mount, cached for the session.
export function getConfidenceThresholds() {
  if (_cache) return _cache;
  _cache = fetch(`${API_BASE}/api/v1/config/confidence-thresholds`, {
    headers: { 'X-API-Key': API_KEY },
  }).then(res => {
    if (!res.ok) {
      const err = new Error(`API error ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }).catch(err => {
    _cache = null; // allow retry on next mount
    throw err;
  });
  return _cache;
}
