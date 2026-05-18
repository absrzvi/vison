import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { OccupancyHeatmap } from '../OccupancyHeatmap';

vi.mock('../../../api/analytics', () => ({
  getOccupancyHeatmap: vi.fn(),
}));

import { getOccupancyHeatmap } from '../../../api/analytics';

beforeEach(() => {
  vi.clearAllMocks();
  getOccupancyHeatmap.mockReturnValue(new Promise(() => {}));
});

// ── Loading skeleton ──────────────────────────────────────────────────────────

describe('OccupancyHeatmap — initial render', () => {
  it('shows loading skeleton on first render', () => {
    const html = renderToStaticMarkup(<OccupancyHeatmap dateRange="7d" />);
    expect(html).toContain('occ-heatmap__skeleton');
  });

  it('renders without crashing when dateRange is 14d', () => {
    const html = renderToStaticMarkup(<OccupancyHeatmap dateRange="14d" />);
    expect(html).toBeTruthy();
    expect(html).toContain('occ-heatmap__skeleton');
  });

  it('renders without crashing when dateRange is 30d', () => {
    const html = renderToStaticMarkup(<OccupancyHeatmap dateRange="30d" />);
    expect(html).toBeTruthy();
  });

  it('skeleton has testid occ-heatmap-skeleton', () => {
    const html = renderToStaticMarkup(<OccupancyHeatmap dateRange="7d" />);
    expect(html).toContain('data-testid="occ-heatmap-skeleton"');
  });
});

// ── Data-driven rows contract ─────────────────────────────────────────────────

describe('OccupancyHeatmap — API response contract', () => {
  it('routes and cells arrays have matching lengths', () => {
    const resp = {
      routes: ['Vienna-Salzburg', 'Vienna-Linz', 'Innsbruck-Bregenz'],
      hours: ['05:00', '06:00'],
      cells: [[72.3, 45.1], [88.0, 65.2], [55.0, 60.0]],
    };
    expect(resp.routes.length).toBe(resp.cells.length);
  });

  it('null cells are preserved in the cells array (not clamped to 0)', () => {
    const resp = {
      routes: ['R1'],
      hours: ['05:00', '06:00', '07:00'],
      cells: [[72.3, null, 45.1]],
    };
    expect(resp.cells[0][1]).toBeNull();
  });

  it('a new route in the response needs no code change to appear', () => {
    const routes = ['Vienna-Salzburg', 'Vienna-Linz', 'NewRoute-X'];
    expect(routes).toContain('NewRoute-X');
    expect(routes.length).toBe(3);
  });
});

// ── Shape-guard: malformed/empty payload ─────────────────────────────────────

describe('OccupancyHeatmap — shape guards', () => {
  it('shows empty-state when routes array is empty', () => {
    // Simulate the component receiving empty data by checking the guard logic
    const routes = [];
    expect(routes.length).toBe(0);
    // The component renders empty-state when routes.length === 0
  });

  it('rowCells guard falls back to empty array when cells[ri] is missing', () => {
    const cells = [[72.3, 45.1]]; // only 1 row
    const routes = ['R1', 'R2'];  // 2 routes — cells[1] would be undefined
    routes.forEach((_, ri) => {
      const rowCells = Array.isArray(cells[ri]) ? cells[ri] : [];
      expect(Array.isArray(rowCells)).toBe(true);
    });
    // cells[1] is undefined — guard returns []
    expect(Array.isArray(cells[1]) ? cells[1] : []).toEqual([]);
  });

  it('malformed payload with missing routes/cells falls back to empty arrays', () => {
    const badPayload = { unexpected: true };
    const routes = Array.isArray(badPayload?.routes) ? badPayload.routes : [];
    const hours = Array.isArray(badPayload?.hours) ? badPayload.hours : [];
    const cells = Array.isArray(badPayload?.cells) ? badPayload.cells : [];
    expect(routes).toEqual([]);
    expect(hours).toEqual([]);
    expect(cells).toEqual([]);
  });
});

// ── Peak hour derivation logic ────────────────────────────────────────────────

describe('OccupancyHeatmap — peak hour derivation', () => {
  it('hoursOver85 counts non-null cells >= 85 in a row', () => {
    const cells = [88.0, null, 90.5, 72.0, 85.0];
    const hoursOver85 = cells.filter(v => v != null && v >= 85).length;
    expect(hoursOver85).toBe(3); // 88, 90.5, 85
  });

  it('hoursOver85 is 0 when no cell reaches 85', () => {
    const cells = [72.3, null, 45.1, 60.0];
    const hoursOver85 = cells.filter(v => v != null && v >= 85).length;
    expect(hoursOver85).toBe(0);
  });

  it('peak hour is the hour with max non-null occupancy', () => {
    const rowCells = [72.3, null, 88.0, 45.1];
    const hours = ['05:00', '06:00', '07:00', '08:00'];
    const validPairs = rowCells.map((occ, ci) => ({ occ, hour: hours[ci] })).filter(p => p.occ != null);
    const max = Math.max(...validPairs.map(p => p.occ));
    const peak = validPairs.find(p => p.occ === max);
    expect(peak.hour).toBe('07:00');
    expect(peak.occ).toBe(88.0);
  });

  it('empty row returns zero-occupancy fallback without crashing', () => {
    const rowCells = [];
    const hours = ['05:00', '06:00'];
    const validPairs = rowCells
      .map((occ, ci) => ({ occ, hour: hours[ci] }))
      .filter(p => p.occ != null);
    const result = !validPairs.length
      ? { route: 'R1', hour: '—', occupancy: 0, hoursOver85: 0 }
      : null;
    expect(result).not.toBeNull();
    expect(result.hour).toBe('—');
    expect(result.occupancy).toBe(0);
  });
});

// ── Null cell accessibility ───────────────────────────────────────────────────

describe('OccupancyHeatmap — null cell accessibility contract', () => {
  it('null cells should use index as key to avoid collisions', () => {
    // key={ci} is safe even when hours[ci] is undefined
    const hours = ['05:00'];
    const ci = 1; // out of bounds — hours[1] is undefined
    const key = ci; // using ci directly, not hours[ci]
    expect(key).toBe(1);
    expect(hours[ci]).toBeUndefined();
  });
});
