import { useEffect, useMemo, useState } from 'react';
import { getDetectionQuality } from '../../api/analytics';
import './AIDetection.css';

const TYPE_COLOR = {
  falsePositive: '#4B5563',
  events:        '#CC0022',
};

const RANGE_DAYS = { '7d': 7, '14d': 14, '30d': 30 };

const DAY_ABBR = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const UPTIME_BASELINE = 70;
const UPTIME_RANGE    = 100 - UPTIME_BASELINE; // 30pp

function aggregateBars(daily_bars, dateRange) {
  if (dateRange === '7d') {
    return daily_bars.map(d => ({
      ...d,
      day: DAY_ABBR[new Date(d.date + 'T00:00:00').getDay()],
    }));
  }
  const weeks = [];
  daily_bars.forEach((bar, i) => {
    const weekIdx = Math.floor(i / 7);
    if (!weeks[weekIdx]) weeks[weekIdx] = { label: `W${weekIdx + 1}`, total_events: 0, fp_count: 0 };
    weeks[weekIdx].total_events += bar.total_events;
    weeks[weekIdx].fp_count     += bar.fp_count;
  });
  return weeks.map(w => ({ ...w, day: w.label }));
}

export function AIDetection({ dateRange = '7d' }) {
  const days = RANGE_DAYS[dateRange] ?? 7;

  const [state, setState] = useState({ data: null, loading: true, error: false });
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState({ data: null, loading: true, error: false });
    getDetectionQuality(dateRange).then(
      data => setState({ data, loading: false, error: false }),
      ()   => setState({ data: null, loading: false, error: true }),
    );
  }, [dateRange, retryCount]);

  const bars = useMemo(
    () => (state.data ? aggregateBars(state.data.daily_bars, dateRange) : []),
    [state.data, dateRange],
  );

  const maxBar = Math.max(...bars.map(d => d.total_events), 1);

  const sortedUptime = useMemo(
    () => (state.data ? [...state.data.per_train_uptime].sort((a, b) => a.uptime_pct - b.uptime_pct) : []),
    [state.data],
  );

  const [barTooltip, setBarTooltip] = useState(null);

  const handleBarEnter = (e, d) => {
    const x = e.clientX + 12 + 200 > window.innerWidth ? e.clientX - 212 : e.clientX + 12;
    setBarTooltip({ x, y: e.clientY - 8, d });
  };

  if (state.loading) {
    return (
      <div className="ai-detection__skeleton" data-testid="ai-detection-skeleton" />
    );
  }

  if (state.error) {
    return (
      <div className="ai-detection ai-detection--error">
        <p>Detection quality data unavailable — retry</p>
        <button className="analytics-retry-btn" onClick={() => setRetryCount(c => c + 1)}>
          Retry
        </button>
      </div>
    );
  }

  const kpi = state.data.kpi;
  const fpRate = kpi.fp_rate;

  return (
    <div className="ai-detection">

      {/* Summary KPIs */}
      <div className="ai-kpi-strip">
        <div className="ai-kpi">
          <span className="ai-kpi__value">{kpi.total_events}</span>
          <span className="ai-kpi__label">Events · last {days} days</span>
        </div>
        <div className="ai-kpi-divider" />
        <div className="ai-kpi">
          {fpRate === null ? (
            <>
              <span className="ai-kpi__value" style={{ color: 'var(--obb-text-on-dark-4)' }}>—</span>
              <span className="ai-kpi__label">False positive rate (no data)</span>
            </>
          ) : (
            <>
              <span className="ai-kpi__value" style={{ color: fpRate > 10 ? 'var(--obb-sev-medium)' : 'var(--obb-sev-normal)' }}>
                {fpRate}%
              </span>
              <span className="ai-kpi__label">False positive rate</span>
            </>
          )}
        </div>
        <div className="ai-kpi-divider" />
        <div className="ai-kpi">
          <span className="ai-kpi__value" style={{ color: 'var(--obb-sev-normal)' }}>
            {kpi.avg_confidence ?? '—'}%
          </span>
          <span className="ai-kpi__label">Avg confidence</span>
        </div>
        <div className="ai-kpi-divider" />
        <div className="ai-kpi">
          <span className="ai-kpi__value" style={{ color: (kpi.fleet_uptime_pct ?? 0) < 95 ? 'var(--obb-sev-medium)' : 'var(--obb-sev-normal)' }}>
            {kpi.fleet_uptime_pct ?? '—'}%
          </span>
          <span className="ai-kpi__label">Fleet AI uptime</span>
        </div>
      </div>

      {/* Bar chart */}
      <div className="analytics-section-title">
        Detection events — last {days} days
        <span className="analytics-section-note"> ({dateRange === '7d' ? 'Mon–Sun' : 'weekly totals'})</span>
      </div>

      <div className="analytics-section-note detection-fp-note">
        False positives shown separately below bars — excluded from event totals
      </div>

      <div className="detection-chart">
        <div className="detection-chart__bars">
          {bars.map(d => {
            const total   = d.total_events;
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
                  {total > 0 && (
                    <div
                      className="detection-bar-segment"
                      style={{ flex: 1, background: TYPE_COLOR.events }}
                    />
                  )}
                </div>
                {d.fp_count > 0 && (
                  <div className="detection-bar-col__fp">
                    {d.fp_count} FP
                  </div>
                )}
                <div className="detection-bar-col__day">{d.day}</div>
              </div>
            );
          })}
        </div>
      </div>

      {barTooltip && (
        <div className="detection-bar__tooltip" style={{ top: barTooltip.y, left: barTooltip.x }}>
          <strong>{barTooltip.d.day}</strong> · {barTooltip.d.total_events} events
          {barTooltip.d.fp_count > 0 && (
            <div className="detection-bar__tooltip-rows">
              <span style={{ color: TYPE_COLOR.falsePositive }}>False positive {barTooltip.d.fp_count}</span>
            </div>
          )}
        </div>
      )}

      {/* Per-train AI uptime */}
      <div className="analytics-section-title" style={{ marginTop: 24 }}>
        AI inference uptime by train (last {days} days)
      </div>
      <div className="ai-uptime-note">
        Incidents = inference gaps &gt; 5 min (container restart or loss of connectivity)
      </div>

      <div className="uptime-axis">
        <div className="uptime-axis__label" style={{ left: '0%' }}>70%</div>
        <div className="uptime-axis__label" style={{ left: '50%' }}>85%</div>
        <div className="uptime-axis__label" style={{ left: '100%' }}>100%</div>
        <div className="uptime-axis__threshold" style={{ left: '50%' }} aria-hidden="true" />
      </div>

      <div className="uptime-list">
        {sortedUptime.map(t => {
          const color  = t.uptime_pct >= 85 ? 'var(--obb-sev-normal)' : t.uptime_pct >= 70 ? 'var(--obb-sev-medium)' : 'var(--obb-sev-critical)';
          const barPct = ((t.uptime_pct - UPTIME_BASELINE) / UPTIME_RANGE) * 100;
          return (
            <div key={t.train_id} className="uptime-row">
              <span className="uptime-row__train">{t.train_id}</span>
              <div className="uptime-row__bar-wrap">
                <div
                  className="uptime-row__bar"
                  style={{ width: `${Math.max(0, barPct)}%`, background: color }}
                />
              </div>
              <span className="uptime-row__pct" style={{ color }}>{t.uptime_pct}%</span>
            </div>
          );
        })}
      </div>

    </div>
  );
}
