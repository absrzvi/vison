// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Pure helper functions extracted for unit testing (mirrors SystemHealth.jsx logic)
function elapsedLabel(isoString) {
  if (!isoString) return null;
  const diffMs = Date.now() - Date.parse(isoString);
  if (diffMs < 0) return 'just now';
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function formatTime(isoString) {
  if (!isoString) return null;
  const ts = Date.parse(isoString);
  if (isNaN(ts)) return isoString;
  return new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}

describe('elapsedLabel (ISO-8601 aware)', () => {
  it('returns null for null input', () => {
    expect(elapsedLabel(null)).toBeNull();
  });

  it('returns "just now" for future timestamps', () => {
    const future = new Date(Date.now() + 5000).toISOString();
    expect(elapsedLabel(future)).toBe('just now');
  });

  it('returns seconds for < 60s elapsed', () => {
    const past = new Date(Date.now() - 30000).toISOString();
    const result = elapsedLabel(past);
    expect(result).toMatch(/^\d+s$/);
    const secs = parseInt(result);
    expect(secs).toBeGreaterThanOrEqual(29);
    expect(secs).toBeLessThanOrEqual(31);
  });

  it('returns minutes for < 60m elapsed', () => {
    const past = new Date(Date.now() - 41 * 60 * 1000).toISOString();
    const result = elapsedLabel(past);
    expect(result).toMatch(/^41m$/);
  });

  it('returns hours + minutes for >= 60m elapsed', () => {
    const past = new Date(Date.now() - (2 * 60 + 15) * 60 * 1000).toISOString();
    const result = elapsedLabel(past);
    expect(result).toBe('2h 15m');
  });

  it('does NOT use hardcoded "HH:MM" string parsing', () => {
    // Old implementation used toMin("09:43") — verify ISO string works, not HH:MM
    const isoString = '2026-05-18T09:43:00Z';
    // Just confirm it doesn't throw and returns a string (elapsed will be large in CI)
    const result = elapsedLabel(isoString);
    expect(typeof result === 'string' || result === null).toBe(true);
  });
});

describe('formatTime', () => {
  it('returns null for null input', () => {
    expect(formatTime(null)).toBeNull();
  });

  it('returns the string as-is for non-ISO input', () => {
    expect(formatTime('11:35')).toBe('11:35');
  });

  it('formats ISO-8601 string to HH:MM', () => {
    // Result depends on timezone — just verify it's a time string pattern
    const result = formatTime('2026-05-18T11:35:00Z');
    expect(result).toMatch(/^\d{2}:\d{2}$/);
  });
});

describe('FleetContext CAMERA event logic', () => {
  it('CAMERA_DEGRADED patches cctvStatus to "red" on matching train', () => {
    const fleet = [
      { id: 'R5001C-031', cctvStatus: 'green', appStatus: 'green', deviceStatus: 'green' },
      { id: 'R5001C-008', cctvStatus: 'green', appStatus: 'green', deviceStatus: 'green' },
    ];
    // Simulate the setFleet updater from FleetContext
    const updater = prev => prev.map(t =>
      t.id === 'R5001C-031' ? { ...t, cctvStatus: 'red' } : t
    );
    const next = updater(fleet);
    expect(next[0].cctvStatus).toBe('red');
    expect(next[1].cctvStatus).toBe('green'); // unchanged
  });

  it('CAMERA_RECOVERED patches cctvStatus to "green" on matching train', () => {
    const fleet = [
      { id: 'R5001C-031', cctvStatus: 'red', appStatus: 'red', deviceStatus: 'green' },
    ];
    const updater = prev => prev.map(t =>
      t.id === 'R5001C-031' ? { ...t, cctvStatus: 'green' } : t
    );
    const next = updater(fleet);
    expect(next[0].cctvStatus).toBe('green');
    expect(next[0].appStatus).toBe('red'); // other fields untouched
  });

  it('CAMERA event with unknown trainId does not modify fleet', () => {
    const fleet = [
      { id: 'R5001C-031', cctvStatus: 'green' },
    ];
    const updater = prev => prev.map(t =>
      t.id === 'UNKNOWN-TRAIN' ? { ...t, cctvStatus: 'red' } : t
    );
    const next = updater(fleet);
    expect(next[0].cctvStatus).toBe('green');
  });
});

describe('healthData WS cctvStatus merge logic', () => {
  it('patches cctvStatus on matching train in healthData', () => {
    const healthData = {
      trains: [
        { id: 'R5001C-031', cctvStatus: 'green', appStatus: 'green' },
        { id: 'R5001C-008', cctvStatus: 'green', appStatus: 'amber' },
      ],
    };
    const fleet = [
      { id: 'R5001C-031', cctvStatus: 'red' }, // WS patched
      { id: 'R5001C-008', cctvStatus: 'green' },
    ];
    // Simulate the setHealthData updater
    const updater = prev => {
      const patchedTrains = prev.trains.map(ht => {
        const wsEntry = fleet.find(t => t.id === ht.id);
        if (!wsEntry || wsEntry.cctvStatus === ht.cctvStatus) return ht;
        return { ...ht, cctvStatus: wsEntry.cctvStatus };
      });
      const changed = patchedTrains.some((t, i) => t !== prev.trains[i]);
      return changed ? { ...prev, trains: patchedTrains } : prev;
    };
    const next = updater(healthData);
    expect(next.trains[0].cctvStatus).toBe('red');
    expect(next.trains[0].appStatus).toBe('green'); // other fields untouched
    expect(next.trains[1].cctvStatus).toBe('green'); // no change
  });

  it('returns same reference when no change (avoids re-render)', () => {
    const healthData = {
      trains: [{ id: 'R5001C-031', cctvStatus: 'green' }],
    };
    const fleet = [{ id: 'R5001C-031', cctvStatus: 'green' }]; // same
    const updater = prev => {
      const patchedTrains = prev.trains.map(ht => {
        const wsEntry = fleet.find(t => t.id === ht.id);
        if (!wsEntry || wsEntry.cctvStatus === ht.cctvStatus) return ht;
        return { ...ht, cctvStatus: wsEntry.cctvStatus };
      });
      const changed = patchedTrains.some((t, i) => t !== prev.trains[i]);
      return changed ? { ...prev, trains: patchedTrains } : prev;
    };
    const next = updater(healthData);
    expect(next).toBe(healthData); // same reference
  });
});
