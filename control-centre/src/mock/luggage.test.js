// @vitest-environment node
import { describe, it, expect } from 'vitest';
import {
  elapsedMin,
  formatTimestamp,
  getLuggageKPIs,
  LUGGAGE_EVENTS,
} from './luggage.js';

// ── E5-S4: elapsedMin ISO-only ───────────────────────────────────────────────

const NOW = '2026-05-19T09:35:00.000Z'; // 35 min after scenario anchor

describe('elapsedMin', () => {
  it('returns correct minutes for ISO timestamp with explicit nowTs', () => {
    // 09:35 - 08:48 = 47 min
    expect(elapsedMin('2026-05-19T08:48:00.000Z', NOW)).toBe(47);
  });

  it('returns 0 when timestamp equals nowTs', () => {
    expect(elapsedMin(NOW, NOW)).toBe(0);
  });

  it('returns 0 when timestamp is in the future relative to nowTs', () => {
    expect(elapsedMin('2026-05-19T10:00:00.000Z', NOW)).toBe(0);
  });

  it('returns null for null timestamp', () => {
    expect(elapsedMin(null, NOW)).toBeNull();
  });

  it('returns null for undefined timestamp', () => {
    expect(elapsedMin(undefined, NOW)).toBeNull();
  });

  it('returns null for an unparseable string', () => {
    expect(elapsedMin('not-a-date', NOW)).toBeNull();
  });
});

// ── E5-S4: formatTimestamp ISO-only ─────────────────────────────────────────

describe('formatTimestamp', () => {
  it('returns a time string for a valid ISO input', () => {
    const result = formatTimestamp('2026-05-19T08:48:00.000Z');
    expect(result).toMatch(/^\d{2}:\d{2}$/);
  });

  it('returns --:-- for null', () => {
    expect(formatTimestamp(null)).toBe('--:--');
  });

  it('returns --:-- for undefined', () => {
    expect(formatTimestamp(undefined)).toBe('--:--');
  });

  it('returns --:-- for an unparseable string', () => {
    expect(formatTimestamp('garbage')).toBe('--:--');
  });
});

// ── E5-S4: getLuggageKPIs smoke test with LUGGAGE_EVENTS ────────────────────

describe('getLuggageKPIs with LUGGAGE_EVENTS', () => {
  it('returns a valid shape without throwing', () => {
    const kpis = getLuggageKPIs(LUGGAGE_EVENTS);
    expect(typeof kpis.totalActive).toBe('number');
    expect(typeof kpis.unattended).toBe('number');
    expect(typeof kpis.overcrowded).toBe('number');
    expect(typeof kpis.oversized).toBe('number');
    expect(typeof kpis.clearedLastHour).toBe('number');
  });

  it('correctly counts active vs cleared events using relative fixtures', () => {
    const now = new Date().toISOString();
    const recentEvents = [
      { id: 'r1', trainId: 'T1', coachId: 'C1', state: 'unattended',      timestamp: now, confidence: 90 },
      { id: 'r2', trainId: 'T1', coachId: 'C1', state: 'overcrowded',     timestamp: now, confidence: 90 },
      { id: 'r3', trainId: 'T1', coachId: 'C1', state: 'oversized',       timestamp: now, confidence: 90 },
      { id: 'r4', trainId: 'T1', coachId: 'C1', state: 'owner_returned',  timestamp: now, confidence: 90 },
      { id: 'r5', trainId: 'T1', coachId: 'C1', state: 'cleared',         timestamp: now, confidence: 90 },
    ];
    const kpis = getLuggageKPIs(recentEvents);
    expect(kpis.totalActive).toBe(3);
    expect(kpis.clearedLastHour).toBe(2);
  });

  it('returns non-null longestUnattended when unattended events exist', () => {
    const kpis = getLuggageKPIs(LUGGAGE_EVENTS);
    expect(kpis.longestUnattended).not.toBeNull();
    expect(kpis.longestUnattended).toMatch(/\d+ min/);
  });
});

// ── E5-S3: getLuggageKPIs threshold tests ───────────────────────────────────

function minutesAgo(n) {
  return new Date(Date.now() - n * 60 * 1000).toISOString();
}

const makeEvent = (state, minsAgo) => ({
  id: `t-${minsAgo}-${state}`,
  trainId: 'R5001C-031',
  coachId: 'C1',
  state,
  timestamp: minutesAgo(minsAgo),
  confidence: 90,
});

describe('getLuggageKPIs threshold', () => {
  describe('unattendedAlerts threshold', () => {
    it('events below threshold produce unattendedAlerts === 0', () => {
      const events = [makeEvent('unattended', 2)]; // 2 min ago, threshold 5
      const kpis = getLuggageKPIs(events, 5);
      expect(kpis.unattendedAlerts).toBe(0);
    });

    it('events at or above threshold are counted in unattendedAlerts', () => {
      const events = [
        makeEvent('unattended', 6),  // 6 min >= 5 threshold → alert
        makeEvent('unattended', 5),  // 5 min >= 5 threshold → alert
        makeEvent('unattended', 3),  // 3 min < 5 threshold → no alert
      ];
      const kpis = getLuggageKPIs(events, 5);
      expect(kpis.unattendedAlerts).toBe(2);
    });
  });

  describe('totalActive is threshold-agnostic', () => {
    it('totalActive counts all active states regardless of threshold', () => {
      const events = [
        makeEvent('unattended', 1),
        makeEvent('overcrowded', 1),
        makeEvent('oversized', 1),
        makeEvent('cleared', 1),
      ];
      const kpis = getLuggageKPIs(events, 10);
      expect(kpis.totalActive).toBe(3);
    });
  });

  describe('unattended raw count is threshold-agnostic', () => {
    it('unattended equals all unattended events regardless of threshold', () => {
      const events = [
        makeEvent('unattended', 1),
        makeEvent('unattended', 20),
      ];
      const kpis = getLuggageKPIs(events, 10);
      expect(kpis.unattended).toBe(2);
      expect(kpis.unattendedAlerts).toBe(1); // only 20-min event exceeds threshold
    });
  });

  describe('default threshold', () => {
    it('default thresholdMin is 5', () => {
      const events = [
        makeEvent('unattended', 6),  // exceeds default 5
        makeEvent('unattended', 3),  // below default 5
      ];
      const kpis = getLuggageKPIs(events);
      expect(kpis.unattendedAlerts).toBe(1);
    });
  });
});
