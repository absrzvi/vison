// Silent-dismissal telemetry (story 10-2 AC2 / D5).
//
// Emitted when an operator opens an unacknowledged escalation and leaves without
// acknowledging. Must survive page unload (tab close / navigation), so this uses
// `fetch(..., { keepalive: true })` fire-and-forget — the documented successor to
// navigator.sendBeacon that, unlike sendBeacon, can still send the X-API-Key
// header the endpoint requires. We deliberately do NOT await: an awaited fetch in
// an unload handler is cancelled, whereas a keepalive request is flushed by the
// browser after the page goes away.

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY = import.meta.env.VITE_API_KEY ?? '';

export function emitSilentlyDismissed({ escalationId, operatorId, tViewed, tDismissed, dwellFocusMs }) {
  const path = `/api/v1/escalations/${encodeURIComponent(escalationId)}/silently-dismissed`;
  try {
    fetch(`${API_BASE}${path}`, {
      method: 'POST',
      keepalive: true,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify({
        operator_id: operatorId,
        t_viewed: tViewed,
        t_dismissed: tDismissed,
        dwell_focus_ms: dwellFocusMs,
      }),
    }).catch(() => {
      // Fire-and-forget telemetry: a failed beacon must never surface to the operator.
    });
  } catch {
    // sendBeacon/fetch can throw synchronously in rare environments; swallow.
  }
}
