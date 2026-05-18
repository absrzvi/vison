import { useState, useEffect, useMemo } from 'react';
import { getDwellTime } from '../../api/analytics';
import './DwellTime.css';

// P2 fix: suppress trailing "0s" on round minutes
function fmtSec(s) {
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return rem === 0 ? `${m}m` : `${m}m ${rem}s`;
  }
  return `${s}s`;
}

function delayColor(actual, scheduled) {
  const pct = actual / scheduled;
  if (pct >= 1.4)  return 'var(--obb-sev-critical)';
  if (pct >= 1.15) return 'var(--obb-sev-medium)';
  if (pct < 1.0)   return 'var(--obb-sev-normal)';
  return 'var(--obb-sev-normal)';
}

// P1 fix: compute linear regression + R² from scatter data
function linearRegression(points) {
  const n = points.length;
  const sumX  = points.reduce((s, p) => s + p.crowding, 0);
  const sumY  = points.reduce((s, p) => s + p.dwell, 0);
  const sumXY = points.reduce((s, p) => s + p.crowding * p.dwell, 0);
  const sumX2 = points.reduce((s, p) => s + p.crowding * p.crowding, 0);
  const slope     = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;
  // R²
  const yMean = sumY / n;
  const ssTot = points.reduce((s, p) => s + (p.dwell - yMean) ** 2, 0);
  const ssRes = points.reduce((s, p) => s + (p.dwell - (slope * p.crowding + intercept)) ** 2, 0);
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot;
  return { slope, intercept, r2 };
}

// Map scatter data coords to plot % (crowding 15–95, dwell 40–170)
const CROWD_MIN = 15, CROWD_RANGE = 80;
const DWELL_MIN = 40, DWELL_RANGE = 130;
function toPlotX(crowding) { return ((crowding - CROWD_MIN) / CROWD_RANGE) * 100; }
function toPlotY(dwell)    { return ((dwell - DWELL_MIN) / DWELL_RANGE) * 100; }

// P3 fix: station colour palette for scatter dots
const STATION_COLORS = {
  'Graz Hbf':         '#4A9EFF',
  'Wels Hbf':         '#22C55E',
  'Klagenfurt Hbf':   '#A855F7',
  'St. Pölten Hbf':   '#F472B6',
  'Linz Hbf':         '#FB923C',
  'Wien Hbf':         '#FACC15',
  'Innsbruck Hbf':    '#2DD4BF',
  'Salzburg Hbf':     '#F87171',
  'Bruck an der Mur': '#FF3B3B',
};
const STATION_LIST = Object.keys(STATION_COLORS);

const PERIOD_LABEL = { '7d': 'this week', '14d': 'last 14 days', '30d': 'last 30 days' };
const RANGE_DAYS   = { '7d': 7, '14d': 14, '30d': 30 };

const SCATTER_TOOLTIP_WIDTH = 280;

export function DwellTime({ dateRange = '30d' }) {
  const [state, setState] = useState({ data: null, loading: true, error: false });
  const [retryCount, setRetryCount] = useState(0);
  const [scatterTooltip, setScatterTooltip] = useState(null);
  const [schedTooltip, setSchedTooltip] = useState(null);

  useEffect(() => {
    setState({ data: null, loading: true, error: false }); // eslint-disable-line react-hooks/set-state-in-effect
    setScatterTooltip(null);
    setSchedTooltip(null);
    getDwellTime(dateRange)
      .then(data => setState({ data, loading: false, error: false }))
      .catch(() => setState({ data: null, loading: false, error: true }));
  }, [dateRange, retryCount]);

  // Scatter points from API — filter null occupancy_pct
  const scatterPoints = useMemo(
    () =>
      Array.isArray(state.data)
        ? state.data
            .filter(d => d.occupancy_pct != null)
            .map(d => ({ crowding: d.occupancy_pct, dwell: d.actual_sec, station: d.station }))
        : [],
    [state.data],
  );

  // Regression constants — computed from live scatter data
  const regression = useMemo(() => {
    if (scatterPoints.length < 2) return null;
    const { slope, intercept, r2 } = linearRegression(scatterPoints);
    const trendX1 = CROWD_MIN;
    const trendY1 = slope * CROWD_MIN + intercept;
    const trendX2 = CROWD_MIN + CROWD_RANGE;
    const trendY2 = slope * (CROWD_MIN + CROWD_RANGE) + intercept;
    const dwellPer10 = Math.round(slope * 10);
    const correlationLabel = r2 >= 0.7 ? 'Strong' : r2 >= 0.4 ? 'Moderate' : 'Weak';
    return { slope, intercept, r2, trendX1, trendY1, trendX2, trendY2, dwellPer10, correlationLabel };
  }, [scatterPoints]);

  if (state.loading) {
    return (
      <div className="dwell-time">
        <div className="dwell-time__skeleton" data-testid="dwell-time-skeleton" />
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="dwell-time">
        <div className="dwell-error">
          Dwell data unavailable — retry
          <button className="dwell-error__retry" onClick={() => setRetryCount(c => c + 1)}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const dwellData = Array.isArray(state.data) ? state.data : [];
  const days = RANGE_DAYS[dateRange] ?? 30;

  if (!dwellData.length) {
    return (
      <div className="dwell-time">
        <div className="dwell-empty">No dwell data available for this period.</div>
      </div>
    );
  }

  const maxActual = Math.max(...dwellData.map(d => d.actual_sec));

  const handleScatterEnter = (e, pt) => {
    const rawX = e.clientX + 12;
    const x = rawX + SCATTER_TOOLTIP_WIDTH > window.innerWidth ? e.clientX - SCATTER_TOOLTIP_WIDTH - 12 : rawX;
    setScatterTooltip({ x, y: e.clientY - 8, station: pt.station, crowding: pt.crowding, dwell: pt.dwell });
  };

  return (
    <div className="dwell-time">

      {/* Bar chart */}
      <div className="analytics-section-title">
        Avg dwell time by station — actual vs scheduled (last {days} days)
      </div>
      <div className="dwell-bar-legend">
        <span className="dwell-bar-legend__item">
          <span className="dwell-bar-legend__sched-line" /> Scheduled (tick)
        </span>
        <span className="dwell-bar-legend__item">
          <span className="dwell-bar-legend__actual-block" /> Actual
        </span>
      </div>
      <div className="dwell-bars">
        {dwellData.map(d => {
          const color = delayColor(d.actual_sec, d.scheduled_sec);
          const excess = d.actual_sec - d.scheduled_sec;
          const scheduledLeft = `${(d.scheduled_sec / maxActual) * 100}%`;
          const isUnder = excess < 0;
          return (
            <div key={d.station} className="dwell-bar-row">
              <div className="dwell-bar-row__station">{d.station}</div>
              <div className="dwell-bar-row__chart">
                <div
                  className="dwell-bar-row__actual"
                  style={{ width: `${(d.actual_sec / maxActual) * 100}%`, background: color }}
                />
                {/* P2 fix: scheduled tick with wider hover zone via wrapper + custom tooltip */}
                <div
                  className="dwell-bar-row__scheduled-wrap"
                  style={{ left: scheduledLeft }}
                  onMouseEnter={e => setSchedTooltip({
                    x: e.clientX + 10,
                    y: e.clientY - 8,
                    label: `Scheduled: ${fmtSec(d.scheduled_sec)}`,
                  })}
                  onMouseLeave={() => setSchedTooltip(null)}
                >
                  <div className="dwell-bar-row__scheduled" />
                </div>
              </div>
              {/* P1 fix: values in grid-row 2 — below the bar, not on top of it */}
              <div className="dwell-bar-row__values">
                <span style={{ color }} className="dwell-bar-row__actual-val">{fmtSec(d.actual_sec)}</span>
                <span className="dwell-bar-row__sched-val">sched {fmtSec(d.scheduled_sec)}</span>
                {/* P2 fix: show negative delta in green when under schedule */}
                {excess > 0 && (
                  <span className="dwell-bar-row__excess" style={{ color }}>+{fmtSec(excess)}</span>
                )}
                {isUnder && (
                  <span className="dwell-bar-row__under">−{fmtSec(Math.abs(excess))} within schedule</span>
                )}
              </div>
              {d.breach_count > 0 && (
                <div className="dwell-bar-row__breaches" style={{ color }}>
                  {d.breach_count} breach{d.breach_count > 1 ? 'es' : ''} {PERIOD_LABEL[dateRange] ?? 'this period'}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Scheduled tick custom tooltip */}
      {schedTooltip && (
        <div className="dwell-sched__tooltip" style={{ top: schedTooltip.y, left: schedTooltip.x }}>
          {schedTooltip.label}
        </div>
      )}

      {/* Scatter plot */}
      <div className="analytics-section-title" style={{ marginTop: 28 }}>
        Platform crowding vs dwell time — correlation
      </div>
      <div className="dwell-scatter">
        <div className="dwell-scatter__chart">
          {/* P1 fix: Y-axis ticks absolutely positioned to match gridline bottom% */}
          <div className="dwell-scatter__y-axis">
            <span className="dwell-scatter__y-label">Dwell (s)</span>
            <div className="dwell-scatter__y-ticks">
              {[160, 120, 80, 40].map(v => (
                <div
                  key={v}
                  className="dwell-scatter__y-tick"
                  style={{ bottom: `${toPlotY(v)}%` }}
                >
                  {v}s
                </div>
              ))}
            </div>
          </div>
          <div className="dwell-scatter__plot">
            {[160, 120, 80, 40].map(v => (
              <div
                key={v}
                className="dwell-scatter__gridline"
                style={{ bottom: `${toPlotY(v)}%` }}
              />
            ))}
            {regression && (
              <svg className="dwell-scatter__trend-line" viewBox="0 0 100 100" preserveAspectRatio="none">
                <line
                  x1={`${toPlotX(regression.trendX1)}%`} y1={`${100 - toPlotY(regression.trendY1)}%`}
                  x2={`${toPlotX(regression.trendX2)}%`} y2={`${100 - toPlotY(regression.trendY2)}%`}
                  stroke="rgba(100,160,255,0.35)" strokeWidth="1.5" strokeDasharray="4 3"
                />
              </svg>
            )}
            {/* P3 fix: dots coloured by station */}
            {scatterPoints.map((pt, i) => (
              <div
                key={i}
                className="dwell-scatter__dot"
                style={{
                  left: `${toPlotX(pt.crowding)}%`,
                  bottom: `${toPlotY(pt.dwell)}%`,
                  background: STATION_COLORS[pt.station] ?? 'var(--obb-blue-accent)',
                }}
                onMouseEnter={e => handleScatterEnter(e, pt)}
                onMouseLeave={() => setScatterTooltip(null)}
              />
            ))}
          </div>
        </div>

        {/* P3 fix: X-axis ticks absolutely positioned by value, not flex-spaced */}
        <div className="dwell-scatter__x-axis">
          {[20, 40, 60, 80, 90].map(v => (
            <div
              key={v}
              className="dwell-scatter__x-tick"
              style={{ left: `${toPlotX(v)}%` }}
            >
              {v}%
            </div>
          ))}
        </div>
        <div className="dwell-scatter__x-label">Platform crowding (%)</div>

        {/* P1 fix: correlation strength derived from R² */}
        {regression && (
          <div className="dwell-scatter__insight">
            {regression.correlationLabel} positive correlation (R²={regression.r2.toFixed(2)}) — each 10% increase in platform crowding adds approximately <strong>{regression.dwellPer10}s</strong> of dwell time.
          </div>
        )}

        {/* P3 fix: station colour legend */}
        <div className="dwell-scatter__station-legend">
          {STATION_LIST.map(s => (
            <div key={s} className="dwell-scatter__station-legend-item">
              <span className="dwell-scatter__station-dot" style={{ background: STATION_COLORS[s] }} />
              <span className="dwell-scatter__station-label">{s}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scatter tooltip */}
      {scatterTooltip && (
        <div className="dwell-scatter__tooltip" style={{ top: scatterTooltip.y, left: scatterTooltip.x }}>
          <strong>{scatterTooltip.station}</strong> · Crowding {scatterTooltip.crowding}% · Dwell {fmtSec(scatterTooltip.dwell)}
        </div>
      )}
    </div>
  );
}
