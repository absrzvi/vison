const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

const FETCH_TIMEOUT_MS = 10000;

async function _post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
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

export function acknowledgeEscalation(id) {
  return _post(`/api/v1/escalations/${encodeURIComponent(id)}/acknowledge`);
}

export function resolveEscalation(id, outcome, actionTags, operatorId) {
  return _post(`/api/v1/escalations/${encodeURIComponent(id)}/resolve`, {
    outcome,
    action_tags: actionTags,
    operator_id: operatorId,
  });
}
