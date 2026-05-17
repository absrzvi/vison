const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

async function _post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function acknowledgeEscalation(id) {
  return _post(`/api/v1/escalations/${id}/acknowledge`);
}

export function resolveEscalation(id, outcome, actionTags, operatorId) {
  return _post(`/api/v1/escalations/${id}/resolve`, {
    outcome,
    action_tags: actionTags,
    operator_id: operatorId,
  });
}
