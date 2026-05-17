import { useState, useMemo, useEffect, useRef } from 'react';
import { EXCEPTION_DATE, EXCEPTION_DATE_RANGES, getExceptionsForRange } from '../../mock/analytics';
import './ExceptionWorkflow.css';

const PRIORITY_OPTIONS = ['Low', 'Medium', 'High'];

// Derive peak occupancy per coach from timeline data
function coachPeaks(exception) {
  const timeKeys = exception.timeline.length > 0
    ? Object.keys(exception.timeline[0]).filter(k => k !== 'time')
    : exception.coaches.map(c => c.toLowerCase());
  return timeKeys.map(key => ({
    coach: key.toUpperCase(),
    peak: Math.max(...exception.timeline.map(row => row[key] ?? 0)),
    exceeded: exception.coaches.includes(key.toUpperCase()),
  }));
}

function coachColor(pct, exceeded) {
  if (pct >= 90) return 'var(--obb-sev-critical)';
  if (pct >= 85) return exceeded ? 'var(--obb-sev-warning)' : 'var(--obb-sev-warning)';
  return 'var(--obb-sev-normal)';
}

function TrendBadge({ direction, weeks }) {
  if (direction === 'up')        return <span className="exc-trend exc-trend--up">↑ {weeks} consecutive week{weeks !== 1 ? 's' : ''}</span>;
  if (direction === 'improving') return <span className="exc-trend exc-trend--down">Improving ↓</span>;
  if (direction === 'new')       return <span className="exc-trend exc-trend--new">New</span>;
  return <span className="exc-trend exc-trend--stable">Stable</span>;
}

function MiniSparkline({ peaks }) {
  if (!peaks || peaks.length < 2) return null;
  const max = Math.max(...peaks, 85);
  const w = 80, h = 32;
  const pts = peaks.map((v, i) => {
    const x = (i / (peaks.length - 1)) * w;
    const y = h - (v / max) * h;
    return `${x},${y}`;
  }).join(' ');
  const threshY = h - (85 / max) * h;
  return (
    <svg width={w} height={h} className="exc-sparkline" aria-hidden="true">
      <line x1={0} y1={threshY} x2={w} y2={threshY} stroke="var(--obb-sev-warning)" strokeWidth="1" strokeDasharray="3,2" />
      <polyline points={pts} fill="none" stroke="var(--obb-blue-accent)" strokeWidth="1.5" />
    </svg>
  );
}

// Coach occupancy bar chart — replaces the timeline
function CoachOccupancyChart({ exception }) {
  const coaches = coachPeaks(exception);
  if (!coaches.length) return null;

  return (
    <div className="exc-coach-chart">
      <div className="exc-chart-title">Peak occupancy by coach — {exception.trainId} · {exception.departure}</div>
      <div className="exc-coach-bars">
        {coaches.map(({ coach, peak, exceeded }) => {
          const color = coachColor(peak, exceeded);
          return (
            <div key={coach} className="exc-coach-row">
              <span className="exc-coach-row__label">{coach}</span>
              <div className="exc-coach-row__track">
                {/* 85% threshold marker */}
                <div className="exc-coach-row__threshold" aria-hidden="true" />
                <div
                  className="exc-coach-row__bar"
                  style={{ width: `${peak}%`, background: color }}
                />
              </div>
              <span
                className="exc-coach-row__pct"
                style={{ color: exceeded ? color : 'var(--obb-text-on-dark-4)' }}
              >
                {peak}%
              </span>
              {exceeded && (
                <span className="exc-coach-row__flag" style={{ color }}>▲</span>
              )}
            </div>
          );
        })}
      </div>
      <div className="exc-coach-axis">
        <span className="exc-coach-axis__tick" style={{ left: '0%' }}>0</span>
        <span className="exc-coach-axis__tick" style={{ left: '50%' }}>50%</span>
        <span className="exc-coach-axis__tick exc-coach-axis__tick--warn" style={{ left: '85%' }}>85%</span>
        <span className="exc-coach-axis__tick" style={{ left: '100%' }}>100%</span>
      </div>
    </div>
  );
}

// 7-day peak bar chart
const WT_W = 400, WT_H = 100;
const WT_PAD_L = 28, WT_PAD_R = 8, WT_PAD_T = 10, WT_PAD_B = 22;
const WT_CHART_W = WT_W - WT_PAD_L - WT_PAD_R;
const WT_CHART_H = WT_H - WT_PAD_T - WT_PAD_B;

function WeeklyTrendChart({ exception }) {
  const peaks = exception.weeklyPeak;
  const barSlot = WT_CHART_W / peaks.length;
  const barW = barSlot * 0.55;
  const toY = (v) => WT_PAD_T + WT_CHART_H - (v / 100) * WT_CHART_H;
  const threshY = toY(85);

  return (
    <div className="exc-chart-wrap">
      <div className="exc-chart-title">7-day peak — same service · same time slot</div>
      <svg
        viewBox={`0 0 ${WT_W} ${WT_H}`}
        width="100%"
        style={{ display: 'block' }}
        aria-label={`7-day trend — ${exception.trainId}`}
      >
        {[0, 50, 85, 100].map(v => {
          const y = toY(v);
          return (
            <g key={v}>
              <line x1={WT_PAD_L} y1={y} x2={WT_W - WT_PAD_R} y2={y}
                stroke="var(--obb-border-dark)" strokeWidth="0.5" />
              <text x={WT_PAD_L - 4} y={y + 3.5} fontSize="8"
                fill="var(--obb-text-on-dark-4)" textAnchor="end">{v}</text>
            </g>
          );
        })}
        <line x1={WT_PAD_L} y1={threshY} x2={WT_W - WT_PAD_R} y2={threshY}
          stroke="var(--obb-sev-warning)" strokeWidth="1" strokeDasharray="4,3" opacity="0.7" />
        {peaks.map((v, i) => {
          const x = WT_PAD_L + i * barSlot + (barSlot - barW) / 2;
          const barH = (v / 100) * WT_CHART_H;
          const y = toY(v);
          const color = v >= 85 ? 'var(--obb-sev-critical)' : 'var(--obb-sev-warning)';
          const labelOffset = peaks.length - 1 - i;
          const label = labelOffset === 0 ? 'Today' : `−${labelOffset}`;
          return (
            <g key={i}>
              <rect x={x} y={y} width={barW} height={barH} fill={color} opacity="0.8" rx="2" />
              <text x={x + barW / 2} y={WT_H - 6} fontSize="8"
                fill="var(--obb-text-on-dark-4)" textAnchor="middle">{label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ReviewModal({ exception, onConfirm, onCancel }) {
  const [note, setNote] = useState('');
  const [priority, setPriority] = useState('');
  const canSubmit = priority.length > 0;

  return (
    <div className="exc-modal-backdrop" onClick={onCancel}>
      <div className="exc-modal" onClick={e => e.stopPropagation()}>
        <div className="exc-modal__header">
          <span className="exc-modal__title">Add to capacity review queue</span>
          <button className="exc-modal__close" onClick={onCancel}>&times;</button>
        </div>
        <div className="exc-modal__service">{exception.trainId} · {exception.route} · {exception.date ?? EXCEPTION_DATE}</div>

        <label className="exc-modal__label">Note <span className="exc-modal__optional">(optional)</span></label>
        <textarea
          className="exc-modal__textarea"
          placeholder="Add context for the fleet planning team…"
          value={note}
          onChange={e => setNote(e.target.value)}
          maxLength={200}
          rows={3}
        />
        <div className="exc-modal__charcount">{note.length} / 200</div>

        <label className="exc-modal__label">Priority <span className="exc-modal__required">required</span></label>
        <div className="exc-modal__priority-row">
          {PRIORITY_OPTIONS.map(p => (
            <button
              key={p}
              className={`exc-priority-btn ${priority === p ? 'exc-priority-btn--active exc-priority-btn--' + p.toLowerCase() : ''}`}
              onClick={() => setPriority(p)}
            >{p}</button>
          ))}
        </div>
        {!canSubmit && <div className="exc-modal__validation">Select a priority to continue</div>}

        <div className="exc-modal__actions">
          <button className="btn btn--primary" onClick={() => onConfirm(note, priority)} disabled={!canSubmit}>
            Add to queue
          </button>
          <button className="btn btn--ghost" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// Group exceptions by route, preserving severity sort within each group
function groupByRoute(exceptions) {
  const map = new Map();
  exceptions.forEach(exc => {
    if (!map.has(exc.route)) map.set(exc.route, []);
    map.get(exc.route).push(exc);
  });
  // Sort groups by worst severity in group (red first)
  return [...map.entries()].sort(([, a], [, b]) => {
    const sevA = a.some(e => e.severity === 'red') ? 0 : 1;
    const sevB = b.some(e => e.severity === 'red') ? 0 : 1;
    return sevA - sevB;
  });
}

export function ExceptionWorkflow({ dateRange = '7d' }) {
  const rangeInfo = EXCEPTION_DATE_RANGES[dateRange] ?? EXCEPTION_DATE_RANGES['7d'];
  const [exceptions, setExceptions] = useState(() => getExceptionsForRange(dateRange));
  const [selectedId, setSelectedId] = useState(null);
  const [reviewModalFor, setReviewModalFor] = useState(null);
  const [showDismissed, setShowDismissed] = useState(false);
  const detailRef = useRef(null);

  useEffect(() => {
    setExceptions(getExceptionsForRange(dateRange));
    setSelectedId(null);
    setShowDismissed(false);
  }, [dateRange]);

  const selectedExc = useMemo(() => exceptions.find(e => e.id === selectedId) ?? null, [exceptions, selectedId]);

  useEffect(() => {
    if (detailRef.current) detailRef.current.scrollTop = 0;
  }, [selectedId]);

  const redCount      = exceptions.filter(e => e.severity === 'red'   && e.status !== 'dismissed').length;
  const amberCount    = exceptions.filter(e => e.severity === 'amber' && e.status !== 'dismissed').length;
  const conradCount   = exceptions.filter(e => e.conradFlag).length;
  const dismissedCount = exceptions.filter(e => e.status === 'dismissed').length;

  const handleDismiss = (id) => {
    setExceptions(prev => prev.map(e => e.id === id ? { ...e, status: 'dismissed' } : e));
    if (selectedId === id) setSelectedId(null);
  };

  const handleReopen = (id) => {
    setExceptions(prev => prev.map(e => e.id === id ? { ...e, status: 'unreviewed' } : e));
  };

  const handleReview = (id) => setReviewModalFor(id);

  const handleReviewConfirm = (note, priority) => {
    const queuedAt = new Date().toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
    setExceptions(prev => prev.map(e => e.id === reviewModalFor ? { ...e, status: 'in_review', reviewNote: note, priority, queuedAt } : e));
    setReviewModalFor(null);
  };

  const activeExceptions = useMemo(() => [
    ...exceptions.filter(e => e.severity === 'red'   && e.status !== 'dismissed'),
    ...exceptions.filter(e => e.severity === 'amber' && e.status !== 'dismissed'),
  ], [exceptions]);

  const dismissedExceptions = useMemo(() =>
    exceptions.filter(e => e.status === 'dismissed'),
  [exceptions]);

  // Route groups for active exceptions
  const routeGroups = useMemo(() => groupByRoute(activeExceptions), [activeExceptions]);

  return (
    <>
    <div className="exc-workflow">
      {/* Summary strip */}
      <div className="exc-summary-strip">
        <div className="exc-summary-strip__left">
          <span className="exc-summary-stat">
            <span className="exc-summary-stat__val">{rangeInfo.servicesOperated}</span>
            <span className="exc-summary-stat__label">services operated</span>
          </span>
          <span className="exc-summary-sep" />
          <span className="exc-summary-stat">
            <span className={`exc-summary-stat__val ${redCount > 0 ? 'exc-summary-stat__val--red' : ''}`}>{redCount} red</span>
            <span className="exc-summary-stat__dot"> · </span>
            <span className={`exc-summary-stat__val ${amberCount > 0 ? 'exc-summary-stat__val--amber' : ''}`}>{amberCount} amber</span>
            <span className="exc-summary-stat__label"> exceptions</span>
          </span>
          <span className="exc-summary-sep" />
          <span className="exc-summary-stat">
            <span className="exc-summary-stat__val">{conradCount}</span>
            <span className="exc-summary-stat__label"> Conrad flag{conradCount !== 1 ? 's' : ''}</span>
          </span>
        </div>
        <div className="exc-summary-strip__date">{rangeInfo.label} · {rangeInfo.from} – {rangeInfo.to}</div>
      </div>

      {/* Two-column layout */}
      <div className="exc-columns">
        {/* Exception list — grouped by route */}
        <div className="exc-list">
          {activeExceptions.length === 0 && (
            <div className="exc-list__empty">No exceptions in {rangeInfo.label.toLowerCase()} — all services within threshold.</div>
          )}

          {routeGroups.map(([route, excs]) => (
            <div key={route} className="exc-route-group">
              <div className="exc-route-group__header">
                <span className="exc-route-group__name">{route}</span>
                <span className="exc-route-group__count">{excs.length}</span>
              </div>
              {excs.map(exc => (
                <ExceptionCard
                  key={exc.id}
                  exc={exc}
                  selected={selectedId === exc.id}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          ))}

          {showDismissed && dismissedExceptions.length > 0 && (
            <div className="exc-list__section-label">Dismissed</div>
          )}
          {showDismissed && dismissedExceptions.map(exc => (
            <ExceptionCard
              key={exc.id}
              exc={exc}
              selected={selectedId === exc.id}
              onSelect={setSelectedId}
            />
          ))}

          {dismissedCount > 0 && (
            <button
              className="exc-list__dismissed-toggle"
              onClick={() => setShowDismissed(v => !v)}
            >
              {showDismissed ? `Hide dismissed (${dismissedCount})` : `Show dismissed (${dismissedCount})`}
            </button>
          )}
        </div>

        {/* Service detail */}
        <div className="exc-detail" ref={detailRef}>
          {!selectedExc && (
            <div className="exc-detail__placeholder">Select a service from the list to view details</div>
          )}
          {selectedExc && (
            <>
              <div className="exc-detail__header">
                <div className="exc-detail__heading">
                  <span className={`exc-sev-dot exc-sev-dot--${selectedExc.severity}`} />
                  <h2 className="exc-detail__title">{selectedExc.trainId} · {selectedExc.route} · {selectedExc.date ?? EXCEPTION_DATE}</h2>
                </div>
                <span className={`badge ${selectedExc.severity === 'red' ? 'badge--red' : 'badge--amber'}`}>
                  {selectedExc.severity === 'red' ? 'Red' : 'Amber'}
                </span>
              </div>

              {selectedExc.conradFlag && (
                <div className="exc-flag-box">
                  <span className="exc-flag-box__label">🚩 Conrad flagged this service</span>
                  <span className="exc-flag-box__time">{selectedExc.conradFlag.time}</span>
                  <p className="exc-flag-box__note">"{selectedExc.conradFlag.note}"</p>
                </div>
              )}

              {/* Coach occupancy chart replaces timeline */}
              <CoachOccupancyChart exception={selectedExc} />
              <WeeklyTrendChart exception={selectedExc} />

              <div className="exc-action-strip">
                {selectedExc.status === 'unreviewed' && (
                  <>
                    <button className="btn btn--primary" onClick={() => handleReview(selectedExc.id)}>
                      Add to capacity review queue
                    </button>
                    <button className="btn btn--secondary" onClick={() => handleDismiss(selectedExc.id)}>
                      No action required
                    </button>
                  </>
                )}
                {selectedExc.status === 'in_review' && (
                  <div className="exc-action-strip__reviewed">
                    <span>Queued for capacity review · Priority: <strong>{selectedExc.priority}</strong></span>
                    {selectedExc.queuedAt && (
                      <span className="exc-action-strip__queued-at">Added at {selectedExc.queuedAt}</span>
                    )}
                  </div>
                )}
                {selectedExc.status === 'dismissed' && (
                  <div className="exc-action-strip__dismissed">
                    <span>Marked no action required</span>
                    <button className="btn btn--ghost exc-action-strip__reopen" onClick={() => handleReopen(selectedExc.id)}>
                      Reopen
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>

    {reviewModalFor && (
      <ReviewModal
        exception={exceptions.find(e => e.id === reviewModalFor)}
        onConfirm={handleReviewConfirm}
        onCancel={() => setReviewModalFor(null)}
      />
    )}
    </>
  );
}

function ExceptionCard({ exc, selected, onSelect }) {
  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(selected ? null : exc.id);
    }
  };

  return (
    <div
      className={`exc-card exc-card--${exc.severity} ${exc.status === 'dismissed' ? 'exc-card--dismissed' : ''} ${selected ? 'exc-card--selected' : ''}`}
      onClick={() => onSelect(selected ? null : exc.id)}
      tabIndex={0}
      role="button"
      aria-pressed={selected}
      onKeyDown={handleKey}
    >
      <div className="exc-card__top">
        <span className={`exc-sev-dot exc-sev-dot--${exc.severity}`} />
        <span className="exc-card__service">{exc.trainId} · {exc.departure}</span>
        {exc.date && <span className="exc-card__date">{exc.date}</span>}
        {exc.status === 'in_review' && <span className="exc-card__pill exc-card__pill--review">In review</span>}
        {exc.status === 'dismissed' && <span className="exc-card__pill exc-card__pill--dismissed">Dismissed</span>}
      </div>
      <div className="exc-card__meta">
        <span className="exc-card__coaches">Coaches {exc.coaches.join(', ')} · Peak: {exc.peakOccupancy}%</span>
      </div>
      <div className="exc-card__bottom">
        <TrendBadge direction={exc.trendDirection} weeks={exc.trendWeeks} />
      </div>
      {exc.conradFlag && (
        <div className="exc-card__flag-row">
          <span className="exc-card__flag">🚩 Conrad flagged</span>
        </div>
      )}
    </div>
  );
}
