import { useState, useRef, useEffect } from 'react';
import { getOccupancyHeatmap } from '../../api/analytics';
import './OccupancyHeatmap.css';

function occupancyColor(pct) {
  if (pct >= 90) return { bg: '#7B0018', text: '#FFB3B3' };
  if (pct >= 75) return { bg: '#8B4000', text: '#FFD0A0' };
  if (pct >= 60) return { bg: '#7A5A00', text: '#FFE9A0' };
  if (pct >= 40) return { bg: '#1A4D2E', text: '#A0FFB8' };
  return { bg: '#0F2E1A', text: '#6FCF8A' };
}

const LEGEND_BANDS = [
  { samplePct: 15, label: '<40%' },
  { samplePct: 50, label: '40–59%' },
  { samplePct: 65, label: '60–74%' },
  { samplePct: 80, label: '75–89%' },
  { samplePct: 95, label: '≥90%' },
];

const RANGE_DAYS = { '7d': 7, '14d': 14, '30d': 30 };
const TOOLTIP_WIDTH = 260;
const SKELETON_ROUTE_COUNT = 4;

export function OccupancyHeatmap({ dateRange = '7d' }) {
  const days = RANGE_DAYS[dateRange] ?? 7;
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const [retryCount, setRetryCount] = useState(0);
  const [hoveredCell, setHoveredCell] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const scrollRef = useRef(null);
  const [showFade, setShowFade] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null }); // eslint-disable-line react-hooks/set-state-in-effect
    getOccupancyHeatmap(dateRange)
      .then(data => { if (!cancelled) setState({ data, loading: false, error: null }); })
      .catch(err => { if (!cancelled) setState({ data: null, loading: false, error: err }); });
    return () => { cancelled = true; };
  }, [dateRange, retryCount]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const check = () => setShowFade(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
    check();
    el.addEventListener('scroll', check, { passive: true });
    window.addEventListener('resize', check, { passive: true });
    return () => {
      el.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
    };
  }, [state.data]);

  const handleCellEnter = (e, ri, ci, route, hour, occ) => {
    setHoveredCell({ ri, ci });
    const rawX = e.clientX + 12;
    const x = rawX + TOOLTIP_WIDTH > window.innerWidth ? e.clientX - TOOLTIP_WIDTH - 12 : rawX;
    setTooltip({ x, y: e.clientY - 8, route, hour, occ });
  };

  const handleCellLeave = () => {
    setHoveredCell(null);
    setTooltip(null);
  };

  if (state.loading) {
    return (
      <div className="occ-heatmap occ-heatmap__skeleton" data-testid="occ-heatmap-skeleton">
        <div className="analytics-section-title skeleton-pulse" style={{ width: '40%', height: 16, borderRadius: 4 }} />
        <div className="occ-heatmap__skeleton-grid">
          {Array.from({ length: SKELETON_ROUTE_COUNT }).map((_, i) => (
            <div key={i} className="occ-heatmap__skeleton-row skeleton-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="occ-heatmap occ-heatmap__error" data-testid="occ-heatmap-error">
        <span>Occupancy data unavailable</span>
        <button
          className="analytics-retry-btn"
          onClick={() => setRetryCount(n => n + 1)}
        >
          Retry
        </button>
      </div>
    );
  }

  const { routes, hours, cells } = state.data;

  // Derive peak hours from API response — no separate request
  const peakHours = routes.map((route, ri) => {
    const rowCells = cells[ri];
    const validPairs = rowCells
      .map((occ, ci) => ({ occ, hour: hours[ci] }))
      .filter(p => p.occ != null);
    if (!validPairs.length) return { route, hour: '—', occupancy: 0, daysOver85: 0, daysInRange: days };
    const max = Math.max(...validPairs.map(p => p.occ));
    const peak = validPairs.find(p => p.occ === max);
    const daysOver85 = rowCells.filter(v => v != null && v >= 85).length;
    return { route, hour: peak.hour, occupancy: max, daysOver85, daysInRange: days };
  });

  return (
    <div className="occ-heatmap">
      <div className="analytics-section-title">
        Occupancy Heatmap — Avg % by route × hour (last {days} days)
        <span className="analytics-section-note"> · Values shown are average occupancy %</span>
      </div>

      <div className={`occ-heatmap__scroll-container${showFade ? ' occ-heatmap__scroll-container--overflow' : ''}`}>
        <div className="occ-heatmap__wrap" ref={scrollRef}>
          <div className="occ-heatmap__hour-axis">
            <div className="occ-heatmap__route-label" />
            {hours.map(h => (
              <div key={h} className="occ-heatmap__hour-tick">{h}</div>
            ))}
          </div>

          {routes.map((route, ri) => (
            <div key={route} className="occ-heatmap__row">
              <div className="occ-heatmap__route-label" title={route}>{route}</div>
              {cells[ri].map((occ, ci) => {
                const isHovered = hoveredCell?.ri === ri && hoveredCell?.ci === ci;
                const hour = hours[ci];
                if (occ == null) {
                  return (
                    <div
                      key={hour}
                      className="occ-heatmap__cell occ-heatmap__cell--null"
                      aria-label={`${route}, ${hour}, no data`}
                    >
                      —
                    </div>
                  );
                }
                const { bg, text } = occupancyColor(occ);
                return (
                  <div
                    key={hour}
                    className={`occ-heatmap__cell${isHovered ? ' occ-heatmap__cell--hovered' : ''}`}
                    style={{ background: bg, color: text }}
                    onMouseEnter={e => handleCellEnter(e, ri, ci, route, hour, occ)}
                    onMouseLeave={handleCellLeave}
                    tabIndex={0}
                    role="gridcell"
                    aria-label={`${route}, ${hour}, ${occ}% average occupancy`}
                    onFocus={e => handleCellEnter(e, ri, ci, route, hour, occ)}
                    onBlur={handleCellLeave}
                  >
                    {occ}%
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {tooltip && (
        <div
          className="occ-heatmap__tooltip"
          style={{ top: tooltip.y, left: tooltip.x }}
          aria-hidden="true"
        >
          {tooltip.route} · {tooltip.hour} · <strong>{tooltip.occ}% avg occupancy</strong>
        </div>
      )}

      <div className="occ-heatmap__legend">
        {LEGEND_BANDS.map(({ samplePct, label }) => {
          const { bg } = occupancyColor(samplePct);
          return (
            <div key={label} className="occ-legend-item">
              <div className="occ-legend-swatch" style={{ background: bg }} />
              <span className="occ-legend-label">{label}</span>
            </div>
          );
        })}
      </div>

      <div className="analytics-section-title" style={{ marginTop: 24 }}>Peak hour per route</div>
      <div className="peak-hour-table">
        <div className="peak-hour-row peak-hour-row--axis" aria-hidden="true">
          <div className="peak-hour-row__route" />
          <div className="peak-hour-row__hour" />
          <div className="peak-hour-row__bar-wrap peak-hour-row__bar-wrap--axis">
            <div className="peak-hour-axis__tick peak-hour-axis__tick--50">50%</div>
            <div className="peak-hour-axis__tick peak-hour-axis__tick--85">85%</div>
          </div>
          <div className="peak-hour-row__pct" />
        </div>

        {peakHours.map(p => (
          <div key={p.route} className="peak-hour-row">
            <span className="peak-hour-row__route">{p.route}</span>
            <span className="peak-hour-row__hour">{p.hour}</span>
            <div className="peak-hour-row__bar-wrap">
              <div className="peak-hour-row__bar"
                style={{
                  width: `${p.occupancy}%`,
                  background: occupancyColor(p.occupancy).bg,
                  borderRight: `2px solid ${occupancyColor(p.occupancy).text}`,
                }}
              />
              <div className="peak-hour-row__threshold" aria-hidden="true" />
            </div>
            <span className="peak-hour-row__pct" style={{ color: occupancyColor(p.occupancy).text }}>
              {p.occupancy}%
            </span>
            {p.daysOver85 > 0 && (
              <span className="peak-hour-row__days-note">
                {p.daysOver85}/{p.daysInRange} days ≥85%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
