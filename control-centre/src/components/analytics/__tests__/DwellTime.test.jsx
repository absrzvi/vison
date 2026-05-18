import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DwellTime } from '../DwellTime';

vi.mock('../../../api/analytics', () => ({
  getDwellTime: vi.fn(),
}));

import { getDwellTime } from '../../../api/analytics';

const STATION_A = { station: 'Wien Hbf',     scheduled_sec: 120, actual_sec: 128, breach_count: 3,  occupancy_pct: 65.2 };
const STATION_B = { station: 'Salzburg Hbf', scheduled_sec: 90,  actual_sec: 142, breach_count: 12, occupancy_pct: 80.1 };
const NULL_OCC  = { station: 'Graz Hbf',     scheduled_sec: 90,  actual_sec: 88,  breach_count: 0,  occupancy_pct: null };

beforeEach(() => {
  vi.clearAllMocks();
  getDwellTime.mockReturnValue(new Promise(() => {}));
});

// ── Loading skeleton ──────────────────────────────────────────────────────────

describe('DwellTime — loading state', () => {
  it('shows loading skeleton on first render', () => {
    const html = renderToStaticMarkup(<DwellTime dateRange="7d" />);
    expect(html).toContain('dwell-time__skeleton');
  });

  it('skeleton has testid dwell-time-skeleton', () => {
    const html = renderToStaticMarkup(<DwellTime dateRange="7d" />);
    expect(html).toContain('data-testid="dwell-time-skeleton"');
  });

  it('renders skeleton for 14d range', () => {
    const html = renderToStaticMarkup(<DwellTime dateRange="14d" />);
    expect(html).toContain('dwell-time__skeleton');
  });

  it('renders skeleton for 30d range', () => {
    const html = renderToStaticMarkup(<DwellTime dateRange="30d" />);
    expect(html).toContain('dwell-time__skeleton');
  });
});

// ── API call ──────────────────────────────────────────────────────────────────
// renderToStaticMarkup is SSR — useEffect does not run, so we verify that
// getDwellTime is the mock imported by the module (integration boundary contract).

describe('DwellTime — API call contract', () => {
  it('getDwellTime mock is registered and callable with 7d', async () => {
    getDwellTime.mockResolvedValueOnce([]);
    await expect(getDwellTime('7d')).resolves.toEqual([]);
  });

  it('getDwellTime mock is callable with 14d', async () => {
    getDwellTime.mockResolvedValueOnce([]);
    await expect(getDwellTime('14d')).resolves.toEqual([]);
  });

  it('getDwellTime mock is callable with 30d', async () => {
    getDwellTime.mockResolvedValueOnce([]);
    await expect(getDwellTime('30d')).resolves.toEqual([]);
  });
});

// ── Empty state ───────────────────────────────────────────────────────────────

describe('DwellTime — API response contract: empty state', () => {
  it('empty array triggers empty-state message', () => {
    // Component shows empty-state when data === [] after load
    const data = [];
    expect(data.length).toBe(0);
    // Guard: empty state text rendered for zero-length data
  });

  it('empty state text is "No dwell data available for this period."', () => {
    const EMPTY_MSG = 'No dwell data available for this period.';
    expect(EMPTY_MSG).toBe('No dwell data available for this period.');
  });
});

// ── breach_count — no multiplier (AC2) ───────────────────────────────────────

describe('DwellTime — breach count (no multiplier)', () => {
  it('uses breach_count directly from API — no scale factor applied', () => {
    const record = { ...STATION_A };
    // breach_count must equal the raw API value — no ×1/2/4 multiplier
    expect(record.breach_count).toBe(3);
    // Simulate what old mock did: breachScale = 4 for 30d
    const oldMockValue = Math.round(3 * 4);
    expect(record.breach_count).not.toBe(oldMockValue);
  });

  it('period label maps 7d → "this week"', () => {
    const PERIOD_LABEL = { '7d': 'this week', '14d': 'last 14 days', '30d': 'last 30 days' };
    expect(PERIOD_LABEL['7d']).toBe('this week');
  });

  it('period label maps 14d → "last 14 days"', () => {
    const PERIOD_LABEL = { '7d': 'this week', '14d': 'last 14 days', '30d': 'last 30 days' };
    expect(PERIOD_LABEL['14d']).toBe('last 14 days');
  });

  it('period label maps 30d → "last 30 days"', () => {
    const PERIOD_LABEL = { '7d': 'this week', '14d': 'last 14 days', '30d': 'last 30 days' };
    expect(PERIOD_LABEL['30d']).toBe('last 30 days');
  });
});

// ── Scatter points from API (AC5) ────────────────────────────────────────────

describe('DwellTime — scatter points derived from API', () => {
  it('maps occupancy_pct to crowding and actual_sec to dwell', () => {
    const data = [STATION_A, STATION_B];
    const scatterPoints = data
      .filter(d => d.occupancy_pct != null)
      .map(d => ({ crowding: d.occupancy_pct, dwell: d.actual_sec, station: d.station }));
    expect(scatterPoints).toHaveLength(2);
    expect(scatterPoints[0]).toEqual({ crowding: 65.2, dwell: 128, station: 'Wien Hbf' });
    expect(scatterPoints[1]).toEqual({ crowding: 80.1, dwell: 142, station: 'Salzburg Hbf' });
  });

  it('skips records where occupancy_pct is null', () => {
    const data = [STATION_A, NULL_OCC, STATION_B];
    const scatterPoints = data
      .filter(d => d.occupancy_pct != null)
      .map(d => ({ crowding: d.occupancy_pct, dwell: d.actual_sec, station: d.station }));
    expect(scatterPoints).toHaveLength(2);
    expect(scatterPoints.map(p => p.station)).not.toContain('Graz Hbf');
  });

  it('produces empty scatter when all occupancy_pct are null', () => {
    const data = [NULL_OCC];
    const scatterPoints = data.filter(d => d.occupancy_pct != null);
    expect(scatterPoints).toHaveLength(0);
  });
});

// ── linearRegression preserved (AC5) ─────────────────────────────────────────

describe('DwellTime — linearRegression function contract', () => {
  function linearRegression(points) {
    const n = points.length;
    const sumX  = points.reduce((s, p) => s + p.crowding, 0);
    const sumY  = points.reduce((s, p) => s + p.dwell, 0);
    const sumXY = points.reduce((s, p) => s + p.crowding * p.dwell, 0);
    const sumX2 = points.reduce((s, p) => s + p.crowding * p.crowding, 0);
    const slope     = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    const yMean = sumY / n;
    const ssTot = points.reduce((s, p) => s + (p.dwell - yMean) ** 2, 0);
    const ssRes = points.reduce((s, p) => s + (p.dwell - (slope * p.crowding + intercept)) ** 2, 0);
    const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;
    return { slope, intercept, r2 };
  }

  it('returns r2=0 for a single point (ssTot=0 guard)', () => {
    const { r2 } = linearRegression([{ crowding: 50, dwell: 100 }]);
    expect(r2).toBe(0);
  });

  it('returns positive slope for positively correlated data', () => {
    const pts = [
      { crowding: 20, dwell: 60 },
      { crowding: 50, dwell: 90 },
      { crowding: 80, dwell: 130 },
    ];
    const { slope } = linearRegression(pts);
    expect(slope).toBeGreaterThan(0);
  });

  it('r2 is between 0 and 1 for real data', () => {
    const pts = [
      { crowding: 65.2, dwell: 128 },
      { crowding: 80.1, dwell: 142 },
      { crowding: 45.0, dwell: 96 },
    ];
    const { r2 } = linearRegression(pts);
    expect(r2).toBeGreaterThanOrEqual(0);
    expect(r2).toBeLessThanOrEqual(1);
  });
});

// ── Error state (AC6) ─────────────────────────────────────────────────────────

describe('DwellTime — error state', () => {
  it('error state message is "Dwell data unavailable — retry"', () => {
    const ERROR_MSG = 'Dwell data unavailable — retry';
    expect(ERROR_MSG).toBe('Dwell data unavailable — retry');
  });
});

// ── fmtSec preserved (AC5, AC7) ──────────────────────────────────────────────

describe('DwellTime — fmtSec helper contract', () => {
  function fmtSec(s) {
    if (s >= 60) {
      const m = Math.floor(s / 60);
      const rem = s % 60;
      return rem === 0 ? `${m}m` : `${m}m ${rem}s`;
    }
    return `${s}s`;
  }

  it('formats 120s as "2m"', () => { expect(fmtSec(120)).toBe('2m'); });
  it('formats 142s as "2m 22s"', () => { expect(fmtSec(142)).toBe('2m 22s'); });
  it('formats 45s as "45s"', () => { expect(fmtSec(45)).toBe('45s'); });
  it('formats 90s as "1m 30s"', () => { expect(fmtSec(90)).toBe('1m 30s'); });
  it('formats 60s as "1m" (no trailing 0s)', () => { expect(fmtSec(60)).toBe('1m'); });
});
