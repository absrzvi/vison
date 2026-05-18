/**
 * Mock luggage monitoring data — matches ADR-9 luggage event contract.
 * Each event has a trainId, coachId, state, and detection metadata.
 */

export const LUGGAGE_STATES = {
  unattended:   { label: 'Unattended',   color: '#CC0022', severity: 'red'   },
  overcrowded:  { label: 'Overcrowded',  color: '#E8A020', severity: 'amber' },
  oversized:    { label: 'Oversized',    color: '#E8A020', severity: 'amber' },
  owner_returned: { label: 'Owner returned', color: '#22AA66', severity: 'green' },
  cleared:      { label: 'Cleared',      color: '#4B8B6F', severity: 'green' },
};

export const LUGGAGE_EVENTS = [
  {
    id: 'lug-001',
    trainId: 'R5001C-031',
    coachId: 'C4',
    state: 'unattended',
    title: 'Unattended bag — C4 luggage rack',
    detail: 'Black rucksack, upper rack, row 12. No owner detected within 3m for 9 min.',
    duration: '9 min',
    confidence: 94,
    timestamp: '11:23',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C4+luggage+rack+%E2%80%94+11%3A23%3A04',
      capturedAt: '11:23:04',
      camera: 'C4-rack-overhead',
      confidence: 94,
    },
  },
  {
    id: 'lug-002',
    trainId: 'R5001C-003',
    coachId: 'C2',
    state: 'overcrowded',
    title: 'Luggage area full — C2',
    detail: 'Overhead rack at capacity. 3 passengers unable to store bags. Aisle partially blocked.',
    duration: '14 min',
    confidence: 88,
    timestamp: '11:09',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C2+rack+overhead+%E2%80%94+11%3A09%3A22',
      capturedAt: '11:09:22',
      camera: 'C2-rack-overhead',
      confidence: 88,
    },
  },
  {
    id: 'lug-003',
    trainId: 'R5001C-003',
    coachId: 'C5',
    state: 'overcrowded',
    title: 'Luggage area full — C5',
    detail: 'Vestibule luggage zone at capacity. Large suitcases blocking door clearance.',
    duration: '21 min',
    confidence: 91,
    timestamp: '10:52',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C5+vestibule+%E2%80%94+10%3A52%3A47',
      capturedAt: '10:52:47',
      camera: 'C5-vestibule',
      confidence: 91,
    },
  },
  {
    id: 'lug-004',
    trainId: 'R5001C-012',
    coachId: 'C3',
    state: 'oversized',
    title: 'Oversized item — C3 vestibule',
    detail: 'Large bicycle partially blocking vestibule. Not secured to rack.',
    duration: '6 min',
    confidence: 97,
    timestamp: '11:31',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C3+vestibule+%E2%80%94+11%3A31%3A18',
      capturedAt: '11:31:18',
      camera: 'C3-vestibule',
      confidence: 97,
    },
  },
  {
    id: 'lug-005',
    trainId: 'R5001C-044',
    coachId: 'C1',
    state: 'overcrowded',
    title: 'Luggage area full — C1',
    detail: 'High boarding at Bruck an der Mur. Rack capacity exceeded, bags on floor.',
    duration: '5 min',
    confidence: 85,
    timestamp: '11:12',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C1+rack+overhead+%E2%80%94+11%3A12%3A03',
      capturedAt: '11:12:03',
      camera: 'C1-rack-overhead',
      confidence: 85,
    },
  },
  {
    id: 'lug-006',
    trainId: 'R5001C-055',
    coachId: 'C6',
    state: 'owner_returned',
    title: 'Owner returned — C6 rack',
    detail: 'Owner returned to previously unattended item. Item confirmed attended.',
    duration: null,
    confidence: 90,
    timestamp: '11:18',
    stillFrame: null,
  },
  {
    id: 'lug-007',
    trainId: 'R5001C-017',
    coachId: 'C2',
    state: 'cleared',
    title: 'Cleared — C2 aisle bag',
    detail: 'Conductor confirmed item removed from aisle. Area clear.',
    duration: null,
    confidence: null,
    timestamp: '10:44',
    stillFrame: null,
  },
];

// Per-train luggage summary — used by the map and drill-in panel
export function getLuggageSummaryByTrain(events) {
  const map = {};
  events.forEach(ev => {
    if (!map[ev.trainId]) map[ev.trainId] = { active: 0, overcrowded: 0, cleared: 0, events: [] };
    map[ev.trainId].events.push(ev);
    if (ev.state === 'cleared' || ev.state === 'owner_returned') {
      map[ev.trainId].cleared += 1;
    } else if (ev.state === 'overcrowded') {
      map[ev.trainId].overcrowded += 1;
      map[ev.trainId].active += 1;
    } else {
      map[ev.trainId].active += 1;
    }
  });
  return map;
}

const ACTIVE_STATES = new Set(['unattended', 'overcrowded', 'oversized']);

// Convert active luggage events into escalation-shaped objects so they flow
// through the unified feed alongside AI/staff/roland escalations.
export function luggageEventsToEscalations(events) {
  return events
    .filter(e => ACTIVE_STATES.has(e.state))
    .map(e => ({
      id: `lug-esc-${e.id}`,
      type: 'luggage',
      trainId: e.trainId,
      coachId: e.coachId,
      title: e.title,
      detail: e.detail + (e.duration ? ` · ${e.duration}` : ''),
      severity: LUGGAGE_STATES[e.state].severity,
      status: 'unacknowledged',
      timestamp: e.timestamp,
      stillFrame: e.stillFrame ?? null,
    }));
}

// Prepend a new luggage event with id-based dedup — mirrors FleetContext LUGGAGE_EVENT handler.
// Exported so tests import the same logic rather than re-implementing it.
export function applyLuggageEvent(prev, incoming) {
  const { id } = incoming ?? {};
  if (!id) return prev;
  if (prev.some(e => e.id === id)) return prev;
  return [incoming, ...prev];
}

// Next station per train — mock data for operator decision context
export const NEXT_STATION = {
  'R5001C-031': 'Salzburg Hbf',
  'R5001C-022': 'Linz Hbf',
  'R5001C-017': 'St. Pölten',
  'R5001C-008': 'Leoben',
  'R5001C-044': 'Bruck an der Mur',
  'R5001C-055': 'Innsbruck Hbf',
  'R5001C-012': 'Salzburg Hbf',
  'R5001C-003': 'Wiener Neustadt',
};

// Parse "HH:MM" timestamp into minutes since midnight for elapsed calculation
function toMinutes(ts) {
  if (!ts) return null;
  const [h, m] = ts.split(':').map(Number);
  if (isNaN(h) || isNaN(m)) return null;
  return h * 60 + m;
}

const ISO_RE = /^\d{4}-\d{2}-\d{2}T/;

const HH_MM_RE = /^\d{2}:\d{2}$/;

export function formatTimestamp(ts) {
  if (!ts) return '--:--';
  if (ISO_RE.test(ts)) {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '--:--';
    return d.toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
  }
  if (HH_MM_RE.test(ts)) return ts;
  return '--:--';
}

export function elapsedMin(timestamp, nowTs = null) {
  if (!timestamp) return null;
  if (ISO_RE.test(timestamp)) {
    const t = new Date(timestamp).getTime();
    if (isNaN(t)) return null;
    const nowMs = nowTs && ISO_RE.test(nowTs) ? new Date(nowTs).getTime() : Date.now();
    if (isNaN(nowMs)) return null;
    return Math.max(0, Math.round((nowMs - t) / 60000));
  }
  // Legacy HH:MM path — uses '11:35' mock anchor
  const refStr = nowTs ?? '11:35';
  const ref = toMinutes(refStr);
  const t2 = toMinutes(timestamp);
  if (ref == null || t2 == null) return null;
  return Math.max(0, ref - t2);
}

export function normaliseConf(c) {
  if (c == null || typeof c !== 'number' || !isFinite(c)) return null;
  return c > 0 && c < 1 ? Math.round(c * 100) : Math.round(c);
}

export function getLuggageKPIs(events) {
  const active = events.filter(e => e.state !== 'cleared' && e.state !== 'owner_returned');
  const unattendedEvents = active.filter(e => e.state === 'unattended');
  const otherActive = active.filter(e => e.state !== 'unattended');

  const maxElapsed = (evs) => {
    const durations = evs.map(e => elapsedMin(e.timestamp)).filter(v => v != null);
    return durations.length > 0 ? Math.max(...durations) : null;
  };

  const luMax = maxElapsed(unattendedEvents);
  const laMax = maxElapsed(otherActive);

  return {
    totalActive: active.length,
    unattended: unattendedEvents.length,
    overcrowded: active.filter(e => e.state === 'overcrowded').length,
    oversized: active.filter(e => e.state === 'oversized').length,
    clearedLastHour: events.filter(e => e.state === 'cleared' || e.state === 'owner_returned').length,
    longestUnattended: luMax != null ? `${luMax} min` : null,
    longestActive: laMax != null ? `${laMax} min` : null,
  };
}
