import { useMemo, useState, useRef, useEffect } from 'react';
import { getOccupancyHeatmap, HOURS } from '../../mock/analytics';
import './OccupancyHeatmap.css';

function occupancyColor(pct) {
  if (pct >= 90) return { bg: '#7B0018', text: '#FFB3B3' };
  if (pct >= 75) return { bg: '#8B4000', text: '#FFD0A0' };
  if (pct >= 60) return { bg: '#7A5A00', text: '#FFE9A0' };
  if (pct >= 40) return { bg: '#1A4D2E', text: '#A0FFB8' };
  return { bg: '#0F2E1A', text: '#6FCF8A' };
}

// 5 legend entries matching the 5 bands in occupancyColor exactly
const LEGEND_BANDS = [
  { samplePct: 15, label: '<40%' },
  { samplePct: 50, label: '40–59%' },
  { samplePct: 65, label: '60–74%' },
  { samplePct: 80, label: '75–89%' },
  { samplePct: 95, label: '≥90%' },
];

const RANGE_DAYS = { '7d': 7, '14d': 14, '30d': 30 };
const TOOLTIP_WIDTH = 260; // approximate max tooltip width for edge-clamping

export function OccupancyHeatmap({ dateRange = '7d' }) {
  const days = RANGE_DAYS[dateRange] ?? 7;
  const data = useMemo(() => getOccupancyHeatmap(dateRange), [dateRange]);

  // P1 fix: hoveredCell tracks { ri, ci } for CSS class
  const [hoveredCell, setHoveredCell] = useState(null);
  // Tooltip: position + content
  const [tooltip, setTooltip] = useState(null);

  // P2 fix: scroll fade — only show when content overflows
  const scrollRef = useRef(null);
  const [showFade, setShowFade] = useState(false);

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
  }, [data]);

  // Peak hours derived from data (includes daysOver85 from mock)
  const peakHours = data.map(r => {
    const validHours = r.hours.filter(h => h.occupancy != null);
    if (!validHours.length) return { route: r.route, hour: '—', occupancy: 0, daysOver85: 0, daysInRange: days };
    const max = Math.max(...validHours.map(h => h.occupancy));
    const peak = validHours.find(h => h.occupancy === max);
    return { route: r.route, hour: peak.hour, occupancy: max, daysOver85: r.daysOver85, daysInRange: r.daysInRange };
  });

  const handleCellEnter = (e, ri, ci, route, hour, occ) => {
    setHoveredCell({ ri, ci });
    // P1 fix: clamp tooltip to viewport right edge
    const rawX = e.clientX + 12;
    const x = rawX + TOOLTIP_WIDTH > window.innerWidth ? e.clientX - TOOLTIP_WIDTH - 12 : rawX;
    setTooltip({ x, y: e.clientY - 8, route, hour, occ });
  };

  const handleCellLeave = () => {
    setHoveredCell(null);
    setTooltip(null);
  };

  return (
    <div className="occ-heatmap">
      {/* P3 fix: section subtitle clarifying unit */}
      <div className="analytics-section-title">
        Occupancy Heatmap — Avg % by route × hour (last {days} days)
        <span className="analytics-section-note"> · Values shown are average occupancy %</span>
      </div>

      <div className={`occ-heatmap__scroll-container${showFade ? ' occ-heatmap__scroll-container--overflow' : ''}`}>
        <div className="occ-heatmap__wrap" ref={scrollRef}>
          <div className="occ-heatmap__hour-axis">
            <div className="occ-heatmap__route-label" />
            {HOURS.map(h => (
              <div key={h} className="occ-heatmap__hour-tick">{h}</div>
            ))}
          </div>

          {data.map((row, ri) => (
            <div key={row.route} className="occ-heatmap__row">
              <div className="occ-heatmap__route-label" title={row.route}>{row.route}</div>
              {row.hours.map((cell, ci) => {
                const isHovered = hoveredCell?.ri === ri && hoveredCell?.ci === ci;
                // P1 fix: null occupancy = out-of-range boundary hour
                if (cell.occupancy == null) {
                  return (
                    <div
                      key={cell.hour}
                      className="occ-heatmap__cell occ-heatmap__cell--null"
                      aria-label={`${row.route}, ${cell.hour}, no data`}
                    >
                      —
                    </div>
                  );
                }
                const { bg, text } = occupancyColor(cell.occupancy);
                return (
                  <div
                    key={cell.hour}
                    // P1 fix: hover class applied
                    className={`occ-heatmap__cell${isHovered ? ' occ-heatmap__cell--hovered' : ''}`}
                    style={{ background: bg, color: text }}
                    onMouseEnter={e => handleCellEnter(e, ri, ci, row.route, cell.hour, cell.occupancy)}
                    onMouseLeave={handleCellLeave}
                    // P2 fix: keyboard accessibility
                    tabIndex={0}
                    role="gridcell"
                    aria-label={`${row.route}, ${cell.hour}, ${cell.occupancy}% average occupancy`}
                    onFocus={e => handleCellEnter(e, ri, ci, row.route, cell.hour, cell.occupancy)}
                    onBlur={handleCellLeave}
                  >
                    {/* P3 fix: show value with % unit */}
                    {cell.occupancy}%
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip: fixed position at cursor, clamped to viewport */}
      {tooltip && (
        <div
          className="occ-heatmap__tooltip"
          style={{ top: tooltip.y, left: tooltip.x }}
          aria-hidden="true"
        >
          {tooltip.route} · {tooltip.hour} · <strong>{tooltip.occ}% avg occupancy</strong>
        </div>
      )}

      {/* Legend — 5 bands matching occupancyColor exactly */}
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

      {/* Peak hour per route — shared grid layout for aligned axis + bars */}
      <div className="analytics-section-title" style={{ marginTop: 24 }}>Peak hour per route</div>
      {/* P2 fix: axis and rows share a CSS grid so labels align with bars */}
      <div className="peak-hour-table">
        {/* Axis row — sits in the same grid template as data rows */}
        <div className="peak-hour-row peak-hour-row--axis" aria-hidden="true">
          <div className="peak-hour-row__route" />
          <div className="peak-hour-row__hour" />
          {/* P2 fix: threshold and axis labels are inside the bar column, not offset by margin */}
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
              {/* P2 fix: threshold rendered as pseudo/absolute on overflow:visible parent, not clipped */}
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
            {/* P3 fix: days-over-threshold sub-label */}
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
