import { useMemo, useState } from 'react';
import { getDetectionTrend, getInferenceUptime, DETECTION_SUMMARY } from '../../mock/analytics';
import './AIDetection.css';

const TYPE_COLOR = {
  unattended:    '#CC0022',
  overcrowded:   '#E8A020',
  oversized:     '#6B8FCC',
  falsePositive: '#4B5563',
};

const RANGE_DAYS = { '7d': 7, '14d': 14, '30d': 30 };

// P1-B fix: guard totalEvents === 0; P1-C fix: return null for "no data"
function computeFpRate(trend) {
  const totalFp     = trend.reduce((s, d) => s + d.falsePositive, 0);
  const totalEvents = trend.reduce((s, d) => s + d.unattended + d.overcrowded + d.oversized, 0);
  if (totalEvents === 0 && totalFp === 0) return null; // no data — distinct from 0% FP
  if (totalEvents === 0) return 100;
  return Math.round((totalFp / (totalEvents + totalFp)) * 1000) / 10;
}

// Uptime bar: render from BASELINE so 70–100% range fills the bar track
const UPTIME_BASELINE = 70;
const UPTIME_RANGE    = 100 - UPTIME_BASELINE; // 30pp

export function AIDetection({ dateRange = '7d' }) {
  const days = RANGE_DAYS[dateRange] ?? 7;

  // P1-A fix: deterministic — getDetectionTrend returns baked constants, no Math.random()
  // P1-A fix: memoised so it's stable across parent re-renders
  const trend = useMemo(() => getDetectionTrend(dateRange), [dateRange]);
  const barLabel = days > 7 ? 'weekly totals' : 'Mon–Sun';

  // P2-C fix: uptime list respects dateRange
  const sortedUptime = useMemo(
    () => [...getInferenceUptime(dateRange)].sort((a, b) => a.uptime - b.uptime),
    [dateRange],
  );

  // P1-B fix: maxBar floor at 1 to avoid divide-by-zero / NaN
  const maxBar = Math.max(...trend.map(d => d.unattended + d.overcrowded + d.oversized), 1);

  const fpRate = computeFpRate(trend);
  const totalEvents = trend.reduce((s, d) => s + d.unattended + d.overcrowded + d.oversized, 0);

  const summary = {
    totalEvents,
    falsePositiveRate: fpRate,
    avgConfidence:  DETECTION_SUMMARY.avgConfidence,
    uptimeFleet:    DETECTION_SUMMARY.uptimeFleet,
  };

  // P3-A fix: column hover tooltip
  const [barTooltip, setBarTooltip] = useState(null);

  const handleBarEnter = (e, d) => {
    const total = d.unattended + d.overcrowded + d.oversized;
    const x = e.clientX + 12 + 200 > window.innerWidth ? e.clientX - 212 : e.clientX + 12;
    setBarTooltip({ x, y: e.clientY - 8, d, total });
  };

  return (
    <div className="ai-detection">

      {/* Summary KPIs */}
      <div className="ai-kpi-strip">
        <div className="ai-kpi">
          <span className="ai-kpi__value">{summary.totalEvents}</span>
          <span className="ai-kpi__label">Events · last {days} days</span>
        </div>
        <div className="ai-kpi-divider" />
        <div className="ai-kpi">
          {/* P1-C fix: distinguish "no data" from "0% FP rate" */}
          {summary.falsePositiveRate === null ? (
            <>
              <span className="ai-kpi__value" style={{ color: 'var(--obb-text-on-dark-4)' }}>—</span>
              <span className="ai-kpi__label">False positive rate (no data)</span>
            </>
          ) : (
            <>
              <span className="ai-kpi__value" style={{ color: summary.falsePositiveRate > 10 ? 'var(--obb-sev-medium)' : 'var(--obb-sev-normal)' }}>
                {summary.falsePositiveRate}%
              </span>
              <span className="ai-kpi__label">False positive rate</span>
            </>
          )}
        </div>
        <div className="ai-kpi-divider" />
        <div className="ai-kpi">
          <span className="ai-kpi__value" style={{ color: 'var(--obb-sev-normal)' }}>
            {summary.avgConfidence}%
          </span>
          <span className="ai-kpi__label">Avg confidence</span>
        </div>
        <div className="ai-kpi-divider" />
        <div className="ai-kpi">
          <span className="ai-kpi__value" style={{ color: summary.uptimeFleet < 95 ? 'var(--obb-sev-medium)' : 'var(--obb-sev-normal)' }}>
            {summary.uptimeFleet}%
          </span>
          <span className="ai-kpi__label">Fleet AI uptime</span>
        </div>
      </div>

      {/* Stacked bar chart */}
      <div className="analytics-section-title">
        Detection events by type — last {days} days
        <span className="analytics-section-note"> ({barLabel})</span>
      </div>

      {/* Legend + FP note separated — P3-B fix */}
      <div className="detection-chart__legend">
        {[['unattended','Unattended'], ['overcrowded','Overcrowded'], ['oversized','Oversized']].map(([key, label]) => (
          <div key={key} className="detection-legend-item">
            <span className="detection-legend-swatch" style={{ background: TYPE_COLOR[key] }} />
            <span>{label}</span>
          </div>
        ))}
      </div>
      {/* P3-B fix: FP note on its own line, not in the legend flex row */}
      <div className="analytics-section-note detection-fp-note">
        False positives shown separately below bars — excluded from event totals
      </div>

      {/* P2-B fix: min-height, no fixed height — bars grow upward naturally */}
      <div className="detection-chart">
        <div className="detection-chart__bars">
          {trend.map(d => {
            const total = d.unattended + d.overcrowded + d.oversized;
            const isEmpty = total === 0;
            return (
              <div
                key={d.day}
                className={`detection-bar-col${isEmpty ? ' detection-bar-col--empty' : ''}`}
                onMouseEnter={e => handleBarEnter(e, d)}
                onMouseLeave={() => setBarTooltip(null)}
              >
                <div className="detection-bar-col__total">{total}</div>
                <div className="detection-bar-col__stack" style={{ height: `${(total / maxBar) * 140}px` }}>
                  {[
                    { key: 'oversized',   val: d.oversized },
                    { key: 'overcrowded', val: d.overcrowded },
                    { key: 'unattended',  val: d.unattended },
                  ].map(({ key, val }) => val > 0 && (
                    <div
                      key={key}
                      className="detection-bar-segment"
                      style={{ flex: val, background: TYPE_COLOR[key] }}
                    />
                  ))}
                </div>
                {d.falsePositive > 0 && (
                  <div className="detection-bar-col__fp">
                    {d.falsePositive} FP
                  </div>
                )}
                <div className="detection-bar-col__day">{d.day}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* P3-A fix: column hover tooltip */}
      {barTooltip && (
        <div className="detection-bar__tooltip" style={{ top: barTooltip.y, left: barTooltip.x }}>
          <strong>{barTooltip.d.day}</strong> · {barTooltip.total} events
          <div className="detection-bar__tooltip-rows">
            <span style={{ color: TYPE_COLOR.unattended }}>Unattended {barTooltip.d.unattended}</span>
            <span style={{ color: TYPE_COLOR.overcrowded }}>Overcrowded {barTooltip.d.overcrowded}</span>
            <span style={{ color: TYPE_COLOR.oversized }}>Oversized {barTooltip.d.oversized}</span>
            {barTooltip.d.falsePositive > 0 && (
              <span style={{ color: 'var(--obb-text-on-dark-4)' }}>False positive {barTooltip.d.falsePositive}</span>
            )}
          </div>
        </div>
      )}

      {/* Per-train AI uptime */}
      <div className="analytics-section-title" style={{ marginTop: 24 }}>
        AI inference uptime by train (last {days} days)
      </div>
      <div className="ai-uptime-note">
        Incidents = inference gaps &gt; 5 min (container restart or loss of connectivity)
      </div>

      {/* P3-C fix: axis labels to show compressed 70–100% range */}
      <div className="uptime-axis">
        <div className="uptime-axis__label" style={{ left: '0%' }}>70%</div>
        <div className="uptime-axis__label" style={{ left: '50%' }}>85%</div>
        <div className="uptime-axis__label" style={{ left: '100%' }}>100%</div>
        <div className="uptime-axis__threshold" style={{ left: '50%' }} aria-hidden="true" />
      </div>

      <div className="uptime-list">
        {sortedUptime.map(t => {
          const color = t.uptime >= 95 ? 'var(--obb-sev-normal)' : t.uptime >= 85 ? 'var(--obb-sev-medium)' : 'var(--obb-sev-critical)';
          // P3-C fix: bar width mapped from BASELINE (70%) → 100%
          const barPct = ((t.uptime - UPTIME_BASELINE) / UPTIME_RANGE) * 100;
          return (
            <div key={t.train} className="uptime-row">
              <span className="uptime-row__train">{t.train}</span>
              <div className="uptime-row__bar-wrap">
                <div
                  className="uptime-row__bar"
                  style={{ width: `${Math.max(0, barPct)}%`, background: color }}
                />
              </div>
              <span className="uptime-row__pct" style={{ color }}>{t.uptime}%</span>
              <span className="uptime-row__incidents">{t.incidents} incident{t.incidents !== 1 ? 's' : ''}</span>
            </div>
          );
        })}
      </div>

    </div>
  );
}
