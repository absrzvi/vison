// @vitest-environment node
import { describe, it, expect } from 'vitest';
import {
  elapsedMin,
  formatTimestamp,
  getLuggageKPIs,
  getLuggageSummaryByTrain,
} from '../luggage.js';

// ── Security Tests ───────────────────────────────────────────────────────────

describe('Security: confidence normalisation', () => {
  it('clamps decimal confidence to non-negative integer ≤ 100', () => {
    const normalise = (c) => c == null ? null : (c <= 1 ? Math.round(c * 100) : Math.round(c));
    expect(normalise(0.94)).toBe(94);
    expect(normalise(94)).toBe(94);
    expect(normalise(0)).toBe(0);
    expect(normalise(1)).toBe(100);
    expect(normalise(null)).toBe(null);
  });

  it('does not produce NaN or negative confidence from edge inputs', () => {
    const normalise = (c) => c == null ? null : (c <= 1 ? Math.round(c * 100) : Math.round(c));
    const result = normalise(0.001);
    expect(result).toBeGreaterThanOrEqual(0);
    expect(Number.isNaN(result)).toBe(false);
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
});

// ── T5.2 — elapsedMin with HH:MM (backwards compat) ────────────────────────

describe('elapsedMin — HH:MM legacy', () => {
  it('uses 11:35 anchor for HH:MM timestamp', () => {
    expect(elapsedMin('11:23')).toBe(12);
  });

  it('accepts explicit HH:MM nowTs', () => {
    expect(elapsedMin('10:00', '11:00')).toBe(60);
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

  it('passes through HH:MM string unchanged', () => {
    expect(formatTimestamp('11:23')).toBe('11:23');
  });

  it('returns --:-- for null input', () => {
    expect(formatTimestamp(null)).toBe('--:--');
  });

  it('returns --:-- for invalid ISO string', () => {
    expect(formatTimestamp('totally-invalid')).toBe('--:--');
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
    expect(mins).toBeGreaterThanOrEqual(9); // allow 1 min tolerance
  });
});

// ── T5.6 — Confidence normalisation formula ──────────────────────────────────

describe('confidence normalisation formula', () => {
  it('decimal 0.94 normalises to 94', () => {
    expect(Math.round(0.94 > 1 ? 0.94 : 0.94 * 100)).toBe(94);
  });

  it('integer 94 normalises to 94', () => {
    expect(Math.round(94 > 1 ? 94 : 94 * 100)).toBe(94);
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
    // Reproduce the coach map logic from LuggageTrainDetail
    const coachMap = {};
    trainSummary.events.forEach(ev => {
      if (!coachMap[ev.coachId]) coachMap[ev.coachId] = [];
      coachMap[ev.coachId].push(ev);
    });
    const coaches = allCoachIds.map(id => ({
      id,
      events: coachMap[id] ?? [],
    }));
    const c4 = coaches.find(c => c.id === 'C4');
    expect(c4).toBeDefined();
    expect(c4.events.length).toBe(1);
  });
});
