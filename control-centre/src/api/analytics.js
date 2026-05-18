const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

const FETCH_TIMEOUT_MS = 10_000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

async function _get(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: { 'X-API-Key': API_KEY },
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function _post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return {};
  return res.json();
}

export function getOccupancyHeatmap(range = '7d') {
  return _get(`/api/v1/analytics/occupancy-heatmap?range=${encodeURIComponent(range)}`);
}

export function getDetectionQuality(range = '7d') {
  return _get(`/api/v1/analytics/detection-quality?range=${encodeURIComponent(range)}`);
}

export function getDwellTime(range = '7d') {
  return _get(`/api/v1/analytics/dwell-time?range=${encodeURIComponent(range)}`);
}

export function getCapacityExceptions(range = '7d') {
  return _get(`/api/v1/analytics/exceptions?range=${encodeURIComponent(range)}`);
}

export function reviewException(id, note, priority) {
  return _post(`/api/v1/analytics/exceptions/${encodeURIComponent(id)}/review`, {
    note,
    priority,
  });
}

export function dismissException(id) {
  return _post(`/api/v1/analytics/exceptions/${encodeURIComponent(id)}/dismiss`);
}

export function reopenException(id) {
  return _post(`/api/v1/analytics/exceptions/${encodeURIComponent(id)}/reopen`);
}

export async function exportCapacityReviewCsv() {
  const dateStr = new Date().toISOString().slice(0, 10);
  const res = await fetch(`${API_BASE}/api/v1/capacity-review-queue/export?format=csv`, {
    method: 'GET',
    headers: { 'X-API-Key': API_KEY },
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `capacity-review-${dateStr}.csv`;
  a.click();
  // Revoke after a short delay so the browser has time to initiate the download
  setTimeout(() => URL.revokeObjectURL(url), 100);
}
