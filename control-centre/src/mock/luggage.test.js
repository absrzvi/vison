// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { getLuggageKPIs } from './luggage.js';

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

describe('getLuggageKPIs', () => {
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
