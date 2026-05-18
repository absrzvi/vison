const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

const FETCH_TIMEOUT_MS = 10000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
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
  // 204 No Content — success with no body
  if (res.status === 204) return {};
  return res.json();
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

export function acknowledgeEscalation(id) {
  return _post(`/api/v1/escalations/${encodeURIComponent(id)}/acknowledge`);
}

export function getTrainAlerts(trainId) {
  return _get(`/api/v1/trains/${encodeURIComponent(trainId)}/alerts?status=active`);
}

export function resolveEscalation(id, outcome, actionTags, operatorId) {
  return _post(`/api/v1/escalations/${encodeURIComponent(id)}/resolve`, {
    outcome,
    action_tags: actionTags,
    operator_id: operatorId,
  });
}
