// @vitest-environment node
import { describe, it, expect } from 'vitest';
import {
  elapsedMin,
  formatTimestamp,
  getLuggageKPIs,
  getLuggageSummaryByTrain,
  normaliseConf,
} from '../luggage.js';

// ── Security Tests ───────────────────────────────────────────────────────────

describe('Security: confidence normalisation', () => {
  it('clamps decimal confidence to non-negative integer', () => {
    expect(normaliseConf(0.94)).toBe(94);
    expect(normaliseConf(94)).toBe(94);
    expect(normaliseConf(0)).toBe(0);
    expect(normaliseConf(null)).toBe(null);
  });

  it('does not produce NaN or negative confidence from edge inputs', () => {
    const result = normaliseConf(0.001);
    expect(result).toBeGreaterThanOrEqual(0);
    expect(Number.isNaN(result)).toBe(false);
  });

  it('returns null for non-numeric input', () => {
    expect(normaliseConf(NaN)).toBe(null);
    expect(normaliseConf(Infinity)).toBe(null);
  });
});

// ── T5.1 — elapsedMin with ISO timestamp ────────────────────────────────────

describe('elapsedMin — ISO timestamp', () => {
  it('returns positive integer for ISO timestamp 5 min ago', () => {
    const event_ts = '2026-05-19T10:00:00Z';
    const now_ts   = '2026-05-19T10:05:00Z';
    expect(elapsedMin(event_ts, now_ts)).toBe(5);
  });

  it('returns 0 for timestamp equal to now', () => {
    const ts = '2026-05-19T10:00:00Z';
    expect(elapsedMin(ts, ts)).toBe(0);
  });

  it('returns null for invalid ISO string', () => {
    expect(elapsedMin('not-a-date')).toBe(null);
  });

  it('returns null when nowTs is an unparseable string', () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    // Non-ISO nowTs produces NaN → elapsedMin returns null (ISO-only after E5-S4)
    expect(elapsedMin(fiveMinAgo, 'not-a-date')).toBeNull();
  });
});

// ── T5.2 — elapsedMin edge cases (ISO-only after E5-S4) ─────────────────────

describe('elapsedMin — edge cases', () => {
  it('returns null for HH:MM timestamp (unparseable by Date)', () => {
    // HH:MM is no longer a supported format after E5-S4 migration
    expect(elapsedMin('11:23')).toBeNull();
  });

  it('returns null when nowTs is an HH:MM string (unparseable ISO)', () => {
    const ts = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(elapsedMin(ts, '11:00')).toBeNull();
  });

  it('returns null for null input', () => {
    expect(elapsedMin(null)).toBe(null);
  });
});

// ── T5.3/T5.4 — formatTimestamp ─────────────────────────────────────────────

describe('formatTimestamp', () => {
  it('converts ISO string to HH:MM format string', () => {
    const result = formatTimestamp('2026-05-19T10:05:00Z');
    expect(result).toMatch(/^\d{2}:\d{2}$/);
  });

  it('returns --:-- for HH:MM string (no longer a supported passthrough after E5-S4)', () => {
    expect(formatTimestamp('11:23')).toBe('--:--');
  });

  it('returns --:-- for null input', () => {
    expect(formatTimestamp(null)).toBe('--:--');
  });

  it('returns --:-- for invalid ISO string', () => {
    expect(formatTimestamp('totally-invalid')).toBe('--:--');
  });

  it('does not match string with bare T (e.g. "11:23T") as ISO', () => {
    expect(formatTimestamp('11:23T')).toBe('--:--');
  });
});

// ── T5.5 — getLuggageKPIs with ISO timestamps ───────────────────────────────

describe('getLuggageKPIs — ISO timestamps', () => {
  it('returns positive longestUnattended for event 10 min ago', () => {
    const tenMinAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
    const events = [{
      id: 'live-1',
      trainId: 'R5001C-031',
      coachId: 'C4',
      state: 'unattended',
      timestamp: tenMinAgo,
      confidence: 0.94,
    }];
    const kpis = getLuggageKPIs(events);
    expect(kpis.longestUnattended).not.toBe(null);
    expect(kpis.longestUnattended).not.toBe('0 min');
    const mins = parseInt(kpis.longestUnattended, 10);
    expect(mins).toBeGreaterThanOrEqual(9);
  });
});

// ── T5.6 — normaliseConf production function ─────────────────────────────────

describe('normaliseConf', () => {
  it('decimal 0.94 normalises to 94', () => {
    expect(normaliseConf(0.94)).toBe(94);
  });

  it('integer 94 normalises to 94', () => {
    expect(normaliseConf(94)).toBe(94);
  });

  it('integer 1 normalises to 1 (not 100)', () => {
    expect(normaliseConf(1)).toBe(1);
  });

  it('integer 0 normalises to 0', () => {
    expect(normaliseConf(0)).toBe(0);
  });

  it('returns null for null', () => {
    expect(normaliseConf(null)).toBe(null);
  });

  it('returns null for NaN', () => {
    expect(normaliseConf(NaN)).toBe(null);
  });
});

// ── T5.7 — getLuggageSummaryByTrain with normalised coachId ─────────────────

describe('getLuggageSummaryByTrain — live coachId C4', () => {
  it('produces a map key C4 matching allCoachIds array', () => {
    const allCoachIds = Array.from({ length: 8 }, (_, i) => `C${i + 1}`);
    const events = [{
      id: 'live-1',
      trainId: 'R5001C-031',
      coachId: 'C4',
      state: 'unattended',
      timestamp: new Date().toISOString(),
      confidence: 0.94,
    }];
    const summary = getLuggageSummaryByTrain(events);
    const trainSummary = summary['R5001C-031'];
    expect(trainSummary).toBeDefined();
    const coachMap = {};
    trainSummary.events.forEach(ev => {
      if (!coachMap[ev.coachId]) coachMap[ev.coachId] = [];
      coachMap[ev.coachId].push(ev);
    });
    const coaches = allCoachIds.map(id => ({ id, events: coachMap[id] ?? [] }));
    const c4 = coaches.find(c => c.id === 'C4');
    expect(c4).toBeDefined();
    expect(c4.events.length).toBe(1);
  });
});
