/**
 * Mock analytics data — 30-day historical window, week ending 2026-05-16.
 */

export const ROUTES = [
  'Wien→Salzburg',
  'Salzburg→Wien',
  'Wien→Linz',
  'Linz→Graz',
  'Graz→Wien',
  'Wien→Innsbruck',
  'Innsbruck→Wien',
  'Wien→Klagenfurt',
];

// Hours 05:00–23:00 inclusive (19 hours)
export const HOURS = Array.from({ length: 19 }, (_, i) => `${String(i + 5).padStart(2, '0')}:00`);

// Occupancy heatmap: routes × hours — realistic commuter/intercity patterns
const BASE = [
  // Wien→Salzburg: busy morning departures, afternoon peak
  [18,22,35,48,71,88,82,61,55,52,58,74,89,91,78,62,48,38,28,],
  // Salzburg→Wien: reverse commute, evening return peak
  [15,18,28,42,58,65,60,55,52,60,72,85,92,88,74,58,42,32,22,],
  // Wien→Linz: strong morning, moderate day
  [12,18,32,55,82,91,78,62,48,44,50,58,68,72,65,52,40,30,20,],
  // Linz→Graz: moderate throughout, slight pm peak
  [10,14,22,35,48,55,52,50,48,52,58,65,71,68,60,50,40,30,18,],
  // Graz→Wien: morning inbound, evening outbound
  [14,20,38,62,85,88,75,58,50,48,55,68,80,85,78,62,48,35,22,],
  // Wien→Innsbruck: leisure travel, peaks midday/afternoon
  [10,12,18,25,38,52,65,72,75,78,80,82,85,80,72,60,48,35,22,],
  // Innsbruck→Wien: leisure return Sunday-like pattern
  [12,15,22,32,45,55,60,65,68,70,72,70,68,65,62,58,50,40,28,],
  // Wien→Klagenfurt: lower overall, leisure peaks
  [8, 10,16,22,32,45,55,62,65,68,65,62,58,55,52,48,40,30,18,],
];

// Per-range modifiers: slightly different peak hours + magnitudes to show real pattern variation
// 7d = recent week baseline, 14d = 2-week avg (slight morning bias), 30d = monthly avg (flatter)
const RANGE_OFFSETS = {
  '14d': [0, 0, 1, 0, -1, 1, 0, 0],  // route-level hour shift (which hour peaks)
  '30d': [1, 0, 1, 0, 0, -1, 0, 1],
};
const RANGE_SCALE = { '7d': 1.0, '14d': 0.97, '30d': 0.93 };

export function getOccupancyHeatmap(dateRange = '7d') {
  const scale = RANGE_SCALE[dateRange] ?? 1;
  const offsets = RANGE_OFFSETS[dateRange] ?? [];
  return ROUTES.map((route, r) => {
    const shift = offsets[r] ?? 0;
    const n = BASE[r].length; // 19
    const hours = HOURS.map((hour, h) => {
      const srcIdx = h - shift;
      // P1 fix: boundary hours that fall outside the source array are marked null (no data for this range/shift)
      // rather than silently clamping and duplicating edge values
      if (srcIdx < 0 || srcIdx >= n) {
        return { hour, occupancy: null };
      }
      return {
        hour,
        occupancy: Math.round(BASE[r][srcIdx] * scale),
      };
    });
    // Also expose peak-day count: how many of N days in range hit ≥85% at peak hour
    const peakOcc = Math.max(...hours.filter(h => h.occupancy != null).map(h => h.occupancy));
    const daysInRange = { '7d': 7, '14d': 14, '30d': 30 }[dateRange] ?? 7;
    // Approximate: days-over-threshold scales with how far peak exceeds 85
    const daysOver85 = peakOcc >= 85
      ? Math.round(daysInRange * Math.min(1, (peakOcc - 75) / 25))
      : 0;
    return { route, hours, peakOcc, daysInRange, daysOver85 };
  });
}

export function getDwellData(dateRange = '30d') {
  // actual dwell: 30d = long-run smoothed avg (lower); 14d = recent avg; 7d = most recent week (highest — recent issues)
  const actualScale = dateRange === '7d' ? 1.0 : dateRange === '14d' ? 0.95 : 0.88;
  // breaches: discrete event counts — accumulate over longer periods (more days = more total breach events)
  // 7d baseline (DWELL_DATA.breaches). 14d ≈ 2× weekly rate. 30d ≈ 4× weekly rate.
  const breachScale = dateRange === '7d' ? 1 : dateRange === '14d' ? 2 : 4;
  return DWELL_DATA.map(d => ({
    ...d,
    actual: Math.round(d.actual * actualScale),
    breaches: Math.round(d.breaches * breachScale),
    breachPeriodLabel: dateRange === '7d' ? 'this week' : dateRange === '14d' ? 'last 14 days' : 'last 30 days',
  }));
}

// Dwell time data — per station, avg actual vs scheduled dwell in seconds
export const DWELL_DATA = [
  { station: 'Wien Hbf',         scheduled: 120, actual: 128, breaches: 3,  topCause: 'High boarding volume' },
  { station: 'Salzburg Hbf',     scheduled: 90,  actual: 142, breaches: 12, topCause: 'Platform crowding · wheelchair boarding' },
  { station: 'Linz Hbf',         scheduled: 90,  actual: 98,  breaches: 2,  topCause: 'Late arriving connection' },
  { station: 'Graz Hbf',         scheduled: 120, actual: 115, breaches: 0,  topCause: null },
  { station: 'Innsbruck Hbf',    scheduled: 90,  actual: 134, breaches: 8,  topCause: 'Luggage congestion at vestibule' },
  { station: 'Bruck an der Mur', scheduled: 60,  actual: 104, breaches: 14, topCause: 'Extended boarding · high platform crowding' },
  { station: 'Klagenfurt Hbf',   scheduled: 90,  actual: 88,  breaches: 1,  topCause: null },
  { station: 'St. Pölten Hbf',   scheduled: 60,  actual: 72,  breaches: 4,  topCause: 'Tight turnaround — driver change' },
  { station: 'Wels Hbf',         scheduled: 60,  actual: 63,  breaches: 1,  topCause: null },
  { station: 'Villach Hbf',      scheduled: 90,  actual: 96,  breaches: 3,  topCause: 'Cross-platform transfer flow' },
];

// Dwell vs crowding scatter — each point is a service stop
export const DWELL_SCATTER = [
  { crowding: 20, dwell: 65,  station: 'Graz Hbf' },
  { crowding: 25, dwell: 70,  station: 'Wels Hbf' },
  { crowding: 30, dwell: 75,  station: 'Klagenfurt Hbf' },
  { crowding: 35, dwell: 82,  station: 'St. Pölten Hbf' },
  { crowding: 42, dwell: 88,  station: 'Linz Hbf' },
  { crowding: 50, dwell: 95,  station: 'Wien Hbf' },
  { crowding: 55, dwell: 100, station: 'Wien Hbf' },
  { crowding: 60, dwell: 108, station: 'Innsbruck Hbf' },
  { crowding: 65, dwell: 115, station: 'Innsbruck Hbf' },
  { crowding: 70, dwell: 122, station: 'Salzburg Hbf' },
  { crowding: 75, dwell: 130, station: 'Salzburg Hbf' },
  { crowding: 80, dwell: 138, station: 'Bruck an der Mur' },
  { crowding: 85, dwell: 148, station: 'Bruck an der Mur' },
  { crowding: 90, dwell: 162, station: 'Bruck an der Mur' },
];

// AI detection quality — last 7 days
export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export const DETECTION_TREND = [
  { day: 'Mon', unattended: 3, overcrowded: 8, oversized: 2, falsePositive: 1 },
  { day: 'Tue', unattended: 2, overcrowded: 6, oversized: 1, falsePositive: 0 },
  { day: 'Wed', unattended: 5, overcrowded: 11, oversized: 3, falsePositive: 2 },
  { day: 'Thu', unattended: 4, overcrowded: 9, oversized: 2, falsePositive: 1 },
  { day: 'Fri', unattended: 7, overcrowded: 18, oversized: 4, falsePositive: 2 },
  { day: 'Sat', unattended: 6, overcrowded: 14, oversized: 5, falsePositive: 1 },
  { day: 'Sun', unattended: 4, overcrowded: 10, oversized: 3, falsePositive: 0 },
];

// P1-A fix: deterministic weekly aggregations — no Math.random() in render
// Each week is a distinct historical total with slight variation baked in as constants
const WEEKLY_FACTORS = [0.85, 0.91, 0.97, 1.0, 1.05, 0.98, 0.93, 0.96];

function weekTotal(field) {
  return DETECTION_TREND.reduce((s, d) => s + d[field], 0);
}

export function getDetectionTrend(dateRange = '7d') {
  if (dateRange === '7d') return DETECTION_TREND;
  const weeks = dateRange === '14d' ? 2 : 4;
  return Array.from({ length: weeks }, (_, wi) => {
    const f = WEEKLY_FACTORS[wi] ?? 1;
    return {
      day: `W${wi + 1}`,
      unattended:    Math.round(weekTotal('unattended')    * f),
      overcrowded:   Math.round(weekTotal('overcrowded')   * f),
      oversized:     Math.round(weekTotal('oversized')     * f),
      falsePositive: Math.round(weekTotal('falsePositive') * f),
    };
  });
}

export const INFERENCE_UPTIME = [
  { train: 'R5001C-031', uptime: 87, incidents: 4 },
  { train: 'R5001C-022', uptime: 94, incidents: 2 },
  { train: 'R5001C-017', uptime: 99, incidents: 1 },
  { train: 'R5001C-008', uptime: 71, incidents: 6 },
  { train: 'R5001C-044', uptime: 98, incidents: 3 },
  { train: 'R5001C-055', uptime: 99, incidents: 1 },
  { train: 'R5001C-012', uptime: 96, incidents: 2 },
  { train: 'R5001C-003', uptime: 95, incidents: 2 },
];

// P2-C fix: per-range uptime — incidents accumulate over longer windows;
// uptime % drifts slightly to reflect broader averaging period
const UPTIME_INCIDENT_SCALE = { '7d': 1, '14d': 2, '30d': 4 };
const UPTIME_PCT_ADJUST = { '7d': 0, '14d': -0.5, '30d': -1.2 };

export function getInferenceUptime(dateRange = '7d') {
  const incScale = UPTIME_INCIDENT_SCALE[dateRange] ?? 1;
  const pctAdj   = UPTIME_PCT_ADJUST[dateRange] ?? 0;
  return INFERENCE_UPTIME.map(t => ({
    ...t,
    uptime: Math.max(70, Math.min(100, parseFloat((t.uptime + pctAdj).toFixed(1)))),
    incidents: Math.round(t.incidents * incScale),
  }));
}

export const DETECTION_SUMMARY = {
  totalEvents: 71,
  falsePositiveRate: 9.8,
  avgConfidence: 91,
  uptimeFleet: 92,
};

// Capacity exception mock data — per date range (distinct historical records, not clones)
export const EXCEPTION_DATE = '2026-05-15';

export const EXCEPTION_DATE_RANGES = {
  '7d':  { label: 'Last 7 days',  from: '2026-05-09', to: '2026-05-15', servicesOperated: 42 },
  '14d': { label: 'Last 14 days', from: '2026-05-02', to: '2026-05-15', servicesOperated: 84 },
  '30d': { label: 'Last 30 days', from: '2026-04-16', to: '2026-05-15', servicesOperated: 180 },
};

// Additional exceptions for 14d window (prior week, 2026-05-08)
const EXCEPTIONS_14D_EXTRA = [
  {
    id: 'exc-6',
    severity: 'red',
    trainId: 'R5001C-031',
    departure: '17:42',
    route: 'Wien → Salzburg',
    coaches: ['C3'],
    peakOccupancy: 92,
    trendDirection: 'up',
    trendWeeks: 2,
    conradFlag: null,
    date: '2026-05-08',
    timeline: [
      { time: '17:42', c3: 62 },
      { time: '17:55', c3: 82 },
      { time: '18:05', c3: 92 },
      { time: '18:20', c3: 85 },
      { time: '18:35', c3: 76 },
      { time: '18:50', c3: 68 },
    ],
    weeklyPeak: [65, 70, 74, 80, 84, 88, 92],
    status: 'in_review',
    priority: 'High',
    reviewNote: 'Recurring Friday evening. Escalated to capacity review.',
  },
  {
    id: 'exc-7',
    severity: 'amber',
    trainId: 'R5001C-055',
    departure: '15:10',
    route: 'Wien → Innsbruck',
    coaches: ['C5', 'C6'],
    peakOccupancy: 88,
    trendDirection: 'new',
    trendWeeks: 1,
    conradFlag: null,
    date: '2026-05-09',
    timeline: [
      { time: '15:10', c5: 55, c6: 50 },
      { time: '15:25', c5: 74, c6: 70 },
      { time: '15:40', c5: 88, c6: 84 },
      { time: '15:55', c5: 82, c6: 78 },
      { time: '16:10', c5: 70, c6: 65 },
      { time: '16:25', c5: 58, c6: 55 },
    ],
    weeklyPeak: [62, 68, 74, 80, 85, 87, 88],
    status: 'dismissed',
  },
];

// Additional exceptions for 30d window (weeks 3–4, Apr–early May)
const EXCEPTIONS_30D_EXTRA = [
  ...EXCEPTIONS_14D_EXTRA,
  {
    id: 'exc-8',
    severity: 'red',
    trainId: 'R5001C-022',
    departure: '18:05',
    route: 'Graz → Wien',
    coaches: ['C4', 'C5'],
    peakOccupancy: 95,
    trendDirection: 'up',
    trendWeeks: 4,
    conradFlag: {
      time: '18:22',
      note: 'Fourth consecutive Friday over threshold. Platform assistance requested at Bruck an der Mur.',
    },
    date: '2026-04-24',
    timeline: [
      { time: '18:05', c4: 60, c5: 58 },
      { time: '18:20', c4: 82, c5: 80 },
      { time: '18:35', c4: 95, c5: 91 },
      { time: '18:50', c4: 88, c5: 84 },
      { time: '19:05', c4: 78, c5: 72 },
      { time: '19:20', c4: 65, c5: 60 },
    ],
    weeklyPeak: [80, 85, 88, 91, 93, 94, 95],
    status: 'in_review',
    priority: 'High',
    reviewNote: 'Chronic issue on Friday 18:05. Review timetable capacity for this service.',
  },
  {
    id: 'exc-9',
    severity: 'amber',
    trainId: 'R5001C-008',
    departure: '07:50',
    route: 'Salzburg → Wien',
    coaches: ['C2'],
    peakOccupancy: 86,
    trendDirection: 'improving',
    trendWeeks: 0,
    conradFlag: null,
    date: '2026-04-30',
    timeline: [
      { time: '07:50', c2: 62 },
      { time: '08:05', c2: 80 },
      { time: '08:20', c2: 86 },
      { time: '08:35', c2: 80 },
      { time: '08:50', c2: 70 },
      { time: '09:05', c2: 60 },
    ],
    weeklyPeak: [92, 90, 88, 87, 86, 86, 86],
    status: 'dismissed',
  },
  {
    id: 'exc-10',
    severity: 'amber',
    trainId: 'R5001C-003',
    departure: '09:20',
    route: 'Wien → Klagenfurt',
    coaches: ['C3'],
    peakOccupancy: 87,
    trendDirection: 'stable',
    trendWeeks: 0,
    conradFlag: null,
    date: '2026-05-03',
    timeline: [
      { time: '09:20', c3: 58 },
      { time: '09:35', c3: 76 },
      { time: '09:50', c3: 87 },
      { time: '10:05', c3: 83 },
      { time: '10:20', c3: 74 },
      { time: '10:35', c3: 64 },
    ],
    weeklyPeak: [85, 86, 87, 86, 87, 87, 87],
    status: 'unreviewed',
  },
];

export function getExceptionsForRange(range) {
  if (range === '30d') return [...CAPACITY_EXCEPTIONS, ...EXCEPTIONS_30D_EXTRA];
  if (range === '14d') return [...CAPACITY_EXCEPTIONS, ...EXCEPTIONS_14D_EXTRA];
  return CAPACITY_EXCEPTIONS;
}

export const CAPACITY_EXCEPTIONS = [
  {
    id: 'exc-1',
    severity: 'red',
    trainId: 'R5001C-031',
    departure: '17:42',
    route: 'Wien → Salzburg',
    coaches: ['C3', 'C4'],
    peakOccupancy: 94,
    trendDirection: 'up',
    trendWeeks: 3,
    conradFlag: {
      time: '17:55',
      note: 'Coaches 3 and 4 completely full from Wien. Standing passengers blocking vestibule.',
    },
    timeline: [
      { time: '17:42', c3: 68, c4: 72 },
      { time: '17:55', c3: 85, c4: 91 },
      { time: '18:05', c3: 94, c4: 98 },
      { time: '18:20', c3: 88, c4: 92 },
      { time: '18:35', c3: 80, c4: 84 },
      { time: '18:50', c3: 72, c4: 75 },
    ],
    weeklyPeak: [72, 78, 81, 85, 88, 91, 94],
    status: 'unreviewed',
  },
  {
    id: 'exc-2',
    severity: 'red',
    trainId: 'R5001C-022',
    departure: '18:05',
    route: 'Graz → Wien',
    coaches: ['C5'],
    peakOccupancy: 91,
    trendDirection: 'up',
    trendWeeks: 2,
    conradFlag: null,
    timeline: [
      { time: '18:05', c5: 55 },
      { time: '18:20', c5: 74 },
      { time: '18:35', c5: 88 },
      { time: '18:50', c5: 91 },
      { time: '19:05', c5: 87 },
      { time: '19:20', c5: 79 },
    ],
    weeklyPeak: [65, 70, 75, 80, 85, 88, 91],
    status: 'unreviewed',
  },
  {
    id: 'exc-3',
    severity: 'amber',
    trainId: 'R5001C-017',
    departure: '08:15',
    route: 'Wien → Linz',
    coaches: ['C2'],
    peakOccupancy: 87,
    trendDirection: 'new',
    trendWeeks: 1,
    conradFlag: null,
    timeline: [
      { time: '08:15', c2: 62 },
      { time: '08:30', c2: 78 },
      { time: '08:45', c2: 87 },
      { time: '09:00', c2: 84 },
      { time: '09:15', c2: 76 },
      { time: '09:30', c2: 68 },
    ],
    weeklyPeak: [55, 60, 65, 70, 75, 80, 87],
    status: 'unreviewed',
  },
  {
    id: 'exc-4',
    severity: 'amber',
    trainId: 'R5001C-008',
    departure: '07:50',
    route: 'Salzburg → Wien',
    coaches: ['C1', 'C3'],
    peakOccupancy: 85,
    trendDirection: 'improving',
    trendWeeks: 0,
    conradFlag: {
      time: '08:10',
      note: 'C1 and C3 consistently full from Salzburg. Passengers redistributing to C5 but aisle still congested.',
    },
    timeline: [
      { time: '07:50', c1: 60, c3: 58 },
      { time: '08:05', c1: 78, c3: 72 },
      { time: '08:20', c1: 85, c3: 80 },
      { time: '08:35', c1: 82, c3: 76 },
      { time: '08:50', c1: 75, c3: 68 },
      { time: '09:05', c1: 65, c3: 60 },
    ],
    weeklyPeak: [95, 90, 88, 86, 85, 85, 85],
    status: 'unreviewed',
  },
  {
    id: 'exc-5',
    severity: 'amber',
    trainId: 'R5001C-044',
    departure: '16:30',
    route: 'Wien → Innsbruck',
    coaches: ['C4'],
    peakOccupancy: 86,
    trendDirection: 'stable',
    trendWeeks: 0,
    conradFlag: null,
    timeline: [
      { time: '16:30', c4: 50 },
      { time: '16:45', c4: 70 },
      { time: '17:00', c4: 86 },
      { time: '17:15', c4: 82 },
      { time: '17:30', c4: 75 },
      { time: '17:45', c4: 65 },
    ],
    weeklyPeak: [84, 86, 85, 87, 86, 85, 86],
    status: 'unreviewed',
  },
];
