/**
 * RealWebSocketClient — connects to the cloud-backend /ws endpoint.
 *
 * Drop-in replacement for MockWebSocketClient. Same public API:
 *   new RealWebSocketClient(onMessage, onStatusChange)
 *   client.connect() / client.disconnect()
 *
 * ADR-9 subscription handshake: sends SubscriptionRequest JSON as the first
 * message after the WebSocket opens. Server replays last 50 matching events
 * then streams live events.
 */

const SUBSCRIPTION_REQUEST = {
  event_types: [
    'OCCUPANCY_UPDATE',
    'ALERT_RAISED',
    'DOOR_OBSTRUCTION',
    'JOURNEY_STARTED',
    'JOURNEY_ENDED',
    'OCCUPANCY_THRESHOLD_CROSSED',
  ],
  min_severity: 'info',
  coach_ids: null,
  reconnect_replay_depth: 50,
};

const SEVERITY_MAP = { info: 'green', warning: 'amber', critical: 'red' };

const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 30000;
const JITTER_FACTOR = 0.2;
const SEEN_IDS_MAX = 1000;

function backoffDelay(attempt) {
  const base = Math.min(BACKOFF_BASE_MS * 2 ** attempt, BACKOFF_MAX_MS);
  const jitter = base * JITTER_FACTOR * (Math.random() * 2 - 1);
  return Math.max(0, Math.round(base + jitter));
}

function formatTimestamp(ts) {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '--:--';
  return d.toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}

export class RealWebSocketClient {
  constructor(onMessage, onStatusChange) {
    this._onMessage = onMessage;
    this._onStatusChange = onStatusChange ?? (() => {});
    this._ws = null;
    this._attempt = 0;
    this._active = false;
    this._retryTimer = null;
    // Track seen event_ids to prevent duplicate delivery on replay overlap.
    // Capped at SEEN_IDS_MAX entries — oldest evicted first.
    this._seenIds = new Set();
    this._seenIdsQueue = [];
  }

  connect() {
    this._active = true;
    this._open();
  }

  disconnect() {
    this._active = false;
    this._attempt = 0;
    clearTimeout(this._retryTimer);
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.onerror = null;
      this._ws.close();
      this._ws = null;
    }
    this._onStatusChange('disconnected');
  }

  _open() {
    const wsUrl = import.meta.env.VITE_WS_URL;
    if (!wsUrl) {
      this._onStatusChange('disconnected');
      return;
    }

    // Close any lingering socket before opening a new one.
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.onerror = null;
      this._ws.close();
      this._ws = null;
    }

    this._ws = new WebSocket(wsUrl);

    this._ws.onopen = () => {
      this._attempt = 0;
      this._ws.send(JSON.stringify(SUBSCRIPTION_REQUEST));
      this._onStatusChange('connected');
    };

    this._ws.onmessage = (ev) => {
      let envelope;
      try {
        envelope = JSON.parse(ev.data);
      } catch {
        return;
      }
      this._handleEnvelope(envelope);
    };

    this._ws.onerror = () => {
      // onerror is always followed by onclose — let onclose handle reconnect.
    };

    this._ws.onclose = () => {
      if (!this._active) return;
      this._onStatusChange('reconnecting');
      const delay = backoffDelay(this._attempt++);
      this._retryTimer = setTimeout(() => {
        if (this._active) this._open();
      }, delay);
    };
  }

  _trackSeenId(id) {
    if (this._seenIds.has(id)) return true;
    this._seenIds.add(id);
    this._seenIdsQueue.push(id);
    if (this._seenIdsQueue.length > SEEN_IDS_MAX) {
      this._seenIds.delete(this._seenIdsQueue.shift());
    }
    return false;
  }

  _handleEnvelope(envelope) {
    const { event_id, vehicle_id, event_type, severity, payload, timestamp } = envelope;

    // Dedup — replayed events on reconnect may overlap with already-seen events.
    // event_id === 0 is falsy but valid; use null/undefined check instead.
    if (event_id != null && this._trackSeenId(event_id)) return;

    const frontendSeverity = SEVERITY_MAP[severity] ?? 'green';
    const safePayload = payload ?? {};

    if (event_type === 'OCCUPANCY_UPDATE') {
      this._onMessage({
        type: 'TRAIN_UPDATE',
        payload: {
          trainId: vehicle_id,
          severity: frontendSeverity,
          coachId: safePayload.coach_id ?? null,
          occupancy: safePayload.occupancy ?? null,
          timestamp,
        },
      });
      return;
    }

    if (event_type === 'ALERT_RAISED' || event_type === 'DOOR_OBSTRUCTION') {
      this._onMessage({
        type: 'ESCALATION_NEW',
        payload: {
          id: event_id,
          type: 'ai',
          trainId: vehicle_id,
          coachId: safePayload.coach_id ?? null,
          title: safePayload.title ?? event_type,
          detail: safePayload.detail ?? '',
          severity: frontendSeverity,
          status: 'unacknowledged',
          timestamp: formatTimestamp(timestamp),
          stillFrame: null,
        },
      });
      return;
    }

    if (event_type === 'OCCUPANCY_THRESHOLD_CROSSED') {
      this._onMessage({
        type: 'ESCALATION_NEW',
        payload: {
          id: event_id,
          type: 'occupancy',
          trainId: vehicle_id,
          coachId: safePayload.coach_id ?? null,
          title: `Overcrowding — Coach ${safePayload.coach_id ?? '?'}`,
          detail: safePayload.detail ?? 'Occupancy exceeded threshold.',
          severity: frontendSeverity,
          status: 'unacknowledged',
          timestamp: formatTimestamp(timestamp),
          stillFrame: null,
        },
      });
      return;
    }

    // JOURNEY_STARTED / JOURNEY_ENDED and any unknown types — pass through raw.
    this._onMessage({ type: event_type, payload: envelope });
  }
}
