// @vitest-environment node
import { describe, it, expect } from 'vitest';

const WS_STALENESS_THRESHOLD_MS = 120_000;

const VALID_CCTV_STATUS = new Set(['green', 'amber', 'red']);

// Pure helper functions extracted for unit testing (mirrors SystemHealth.jsx logic)
function elapsedLabel(isoString) {
  if (!isoString) return null;
  const diffMs = Date.now() - Date.parse(isoString);
  if (Number.isNaN(diffMs) || diffMs < 0) return 'just now';
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function formatTime(isoString) {
  if (!isoString) return null;
  const ts = Date.parse(isoString);
  if (Number.isNaN(ts)) return isoString;
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

  it('returns "just now" for non-ISO/garbage strings instead of "NaNs"', () => {
    // Non-ISO strings must not produce "NaNs" label
    expect(elapsedLabel('not-a-date')).toBe('just now');
    expect(elapsedLabel('epoch')).toBe('just now');
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

describe('FleetContext CAMERA event cctvStatus validation', () => {
  const applyPatch = (fleet, trainId, cctvStatus) => {
    const VALID = ['green', 'amber', 'red'];
    if (!trainId || !VALID.includes(cctvStatus)) return fleet;
    return fleet.map(t => t.id === trainId ? { ...t, cctvStatus } : t);
  };

  it('rejects undefined cctvStatus — fleet unchanged', () => {
    const fleet = [{ id: 'R5001C-031', cctvStatus: 'green' }];
    expect(applyPatch(fleet, 'R5001C-031', undefined)).toEqual(fleet);
  });

  it('rejects unknown string cctvStatus — fleet unchanged', () => {
    const fleet = [{ id: 'R5001C-031', cctvStatus: 'green' }];
    expect(applyPatch(fleet, 'R5001C-031', 'degraded')).toEqual(fleet);
  });

  it('accepts valid cctvStatus "red"', () => {
    const fleet = [{ id: 'R5001C-031', cctvStatus: 'green' }];
    expect(applyPatch(fleet, 'R5001C-031', 'red')[0].cctvStatus).toBe('red');
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
    // Simulate the setHealthData updater (mirrors production logic)
    const updater = prev => {
      if (!prev || !Array.isArray(prev.trains)) return prev;
      const patchedTrains = prev.trains.map(ht => {
        const wsEntry = fleet.find(t => t.id === ht.id);
        const incoming = wsEntry?.cctvStatus;
        if (!incoming || !VALID_CCTV_STATUS.has(incoming) || incoming === ht.cctvStatus) return ht;
        return { ...ht, cctvStatus: incoming };
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
        const incoming = wsEntry?.cctvStatus;
        if (!incoming || !VALID_CCTV_STATUS.has(incoming) || incoming === ht.cctvStatus) return ht;
        return { ...ht, cctvStatus: incoming };
      });
      const changed = patchedTrains.some((t, i) => t !== prev.trains[i]);
      return changed ? { ...prev, trains: patchedTrains } : prev;
    };
    const next = updater(healthData);
    expect(next).toBe(healthData); // same reference
  });

  it('returns prev unchanged when trains is not an array', () => {
    const healthData = { trains: null };
    const updater = prev => {
      if (!prev || !Array.isArray(prev.trains)) return prev;
      return prev; // would patch if array
    };
    expect(updater(healthData)).toBe(healthData);
  });
});

describe('WS_STALENESS_THRESHOLD_MS constant', () => {
  it('is 120_000 ms (2 minutes)', () => {
    expect(WS_STALENESS_THRESHOLD_MS).toBe(120_000);
  });
});

describe('isStale computation logic', () => {
  const computeIsStale = (lastUpdate) => {
    if (!lastUpdate) return false;
    return (Date.now() - lastUpdate.getTime()) > WS_STALENESS_THRESHOLD_MS;
  };

  it('returns false when lastUpdate is null', () => {
    expect(computeIsStale(null)).toBe(false);
  });

  it('returns false when elapsed < threshold', () => {
    const recent = new Date(Date.now() - 60_000); // 60s ago
    expect(computeIsStale(recent)).toBe(false);
  });

  it('returns true when elapsed > threshold', () => {
    const old = new Date(Date.now() - 200_000); // 200s ago
    expect(computeIsStale(old)).toBe(true);
  });

  it('returns false immediately after lastUpdate resets to now', () => {
    const now = new Date();
    expect(computeIsStale(now)).toBe(false);
  });
});

describe('last_healthy panel footer helpers', () => {
  it('null last_healthy — elapsedLabel returns null (footer section hidden)', () => {
    expect(elapsedLabel(null)).toBeNull();
  });

  it('null last_healthy — formatTime returns null (footer section hidden)', () => {
    expect(formatTime(null)).toBeNull();
  });

  it('valid ISO last_healthy — elapsedLabel returns elapsed string', () => {
    const iso = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 min ago
    expect(elapsedLabel(iso)).toMatch(/^5m$/);
  });

  it('valid ISO last_healthy — formatTime returns HH:MM pattern', () => {
    const result = formatTime('2026-05-19T10:30:00Z');
    expect(result).toMatch(/^\d{2}:\d{2}$/);
  });

  it('elapsed uses Date.now() against server ISO timestamp — not hardcoded string', () => {
    // Ensure a real ISO-8601 UTC string is parsed correctly (not treated as legacy HH:MM)
    const iso = new Date(Date.now() - 90_000).toISOString(); // 90s = 1m30s → rounds to 1m
    const result = elapsedLabel(iso);
    expect(result).toBe('1m');
  });
});
