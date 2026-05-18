import { useState, useMemo, useEffect, useRef } from 'react';
import {
  getCapacityExceptions,
  reviewException,
  dismissException,
  reopenException,
} from '../../api/analytics';
import './ExceptionWorkflow.css';

const PRIORITY_OPTIONS = ['Low', 'Medium', 'High'];
const CONDUCTOR_APP_URL = import.meta.env.VITE_CONDUCTOR_APP_URL ?? '';

function sevClass(severity) {
  if (severity === 'critical') return 'red';
  if (severity === 'warning')  return 'amber';
  return 'info';
}

function coachColor(pct) {
  if (pct >= 90) return 'var(--obb-sev-critical)';
  if (pct >= 85) return 'var(--obb-sev-warning)';
  return 'var(--obb-sev-normal)';
}

function CoachOccupancyChart({ coachPeaks, trainId, departure }) {
  if (!coachPeaks || !coachPeaks.length) return null;
  return (
    <div className="exc-coach-chart">
      <div className="exc-chart-title">Peak occupancy by coach — {trainId} · {departure}</div>
      <div className="exc-coach-bars">
        {coachPeaks.map(({ coach_id, peak_pct }) => {
          const color = coachColor(peak_pct);
          const exceeded = peak_pct >= 85;
          return (
            <div key={coach_id} className="exc-coach-row">
              <span className="exc-coach-row__label">{coach_id}</span>
              <div className="exc-coach-row__track">
                <div className="exc-coach-row__threshold" aria-hidden="true" />
                <div
                  className="exc-coach-row__bar"
                  style={{ width: `${peak_pct}%`, background: color }}
                />
              </div>
              <span
                className="exc-coach-row__pct"
                style={{ color: exceeded ? color : 'var(--obb-text-on-dark-4)' }}
              >
                {peak_pct}%
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

function WeeklyTrendChart({ trend, trainId }) {
  if (!trend || !trend.length) return null;
  const peaks = trend;
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
        aria-label={`7-day trend — ${trainId}`}
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
        <div className="exc-modal__service">{exception.train_id} · {exception.route} · {exception.date}</div>

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

function groupByRoute(exceptions) {
  const map = new Map();
  exceptions.forEach(exc => {
    if (!map.has(exc.route)) map.set(exc.route, []);
    map.get(exc.route).push(exc);
  });
  return [...map.entries()].sort(([, a], [, b]) => {
    const sevA = a.some(e => e.severity === 'critical') ? 0 : 1;
    const sevB = b.some(e => e.severity === 'critical') ? 0 : 1;
    return sevA - sevB;
  });
}

function rangeDates(range) {
  const today = new Date();
  const days = range === '30d' ? 30 : range === '14d' ? 14 : 7;
  const from = new Date(today);
  from.setDate(from.getDate() - (days - 1));
  const fmt = d => d.toLocaleDateString('de-AT', { day: '2-digit', month: '2-digit', year: 'numeric' });
  return { from: fmt(from), to: fmt(today), label: `Last ${days} days` };
}

function LoadingSkeleton() {
  return (
    <div className="exc-list">
      {[1, 2, 3].map(i => (
        <div key={i} className="exc-card exc-card--skeleton" aria-hidden="true" />
      ))}
    </div>
  );
}

export function ExceptionWorkflow({ dateRange = '7d' }) {
  const [exceptions, setExceptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [reviewModalFor, setReviewModalFor] = useState(null);
  const [showDismissed, setShowDismissed] = useState(false);
  const detailRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      setSelectedId(null);
      setShowDismissed(false);
      try {
        const data = await getCapacityExceptions(dateRange);
        if (!cancelled) { setExceptions(data); setLoading(false); }
      } catch (err) {
        if (!cancelled) { setError(err); setLoading(false); }
      }
    };

    fetchData();
    return () => { cancelled = true; };
  }, [dateRange]);

  const selectedExc = useMemo(
    () => exceptions.find(e => e.exception_id === selectedId) ?? null,
    [exceptions, selectedId],
  );

  useEffect(() => {
    if (detailRef.current) detailRef.current.scrollTop = 0;
  }, [selectedId]);

  const criticalCount  = exceptions.filter(e => e.severity === 'critical' && e.status !== 'dismissed').length;
  const warningCount   = exceptions.filter(e => e.severity === 'warning'  && e.status !== 'dismissed').length;
  const conradCount    = exceptions.filter(e => e.conradFlag).length;
  const dismissedCount = exceptions.filter(e => e.status === 'dismissed').length;

  const handleDismiss = (id) => {
    setExceptions(prev => prev.map(e => e.exception_id === id ? { ...e, status: 'dismissed' } : e));
    if (selectedId === id) setSelectedId(null);
    dismissException(id).catch(() => {
      // revert optimistic update on failure
      setExceptions(prev => prev.map(e => e.exception_id === id ? { ...e, status: 'unreviewed' } : e));
    });
  };

  const handleReopen = (id) => {
    setExceptions(prev => prev.map(e => e.exception_id === id ? { ...e, status: 'unreviewed' } : e));
    reopenException(id).catch(() => {
      setExceptions(prev => prev.map(e => e.exception_id === id ? { ...e, status: 'dismissed' } : e));
    });
  };

  const handleReview = (id) => setReviewModalFor(id);

  const handleReviewConfirm = (note, priority) => {
    const id = reviewModalFor;
    setReviewModalFor(null);
    setExceptions(prev => prev.map(e =>
      e.exception_id === id
        ? { ...e, status: 'in_review', reviewNote: note, priority, queuedAt: new Date().toISOString() }
        : e,
    ));
    reviewException(id, note, priority)
      .then(res => {
        setExceptions(prev => prev.map(e =>
          e.exception_id === id ? { ...e, queuedAt: res.queued_at ?? e.queuedAt } : e,
        ));
      })
      .catch(() => {
        setExceptions(prev => prev.map(e => e.exception_id === id ? { ...e, status: 'unreviewed' } : e));
      });
  };

  const activeExceptions = useMemo(() => [
    ...exceptions.filter(e => e.severity === 'critical' && e.status !== 'dismissed'),
    ...exceptions.filter(e => e.severity === 'warning'  && e.status !== 'dismissed'),
    ...exceptions.filter(e => e.severity === 'info'     && e.status !== 'dismissed'),
  ], [exceptions]);

  const dismissedExceptions = useMemo(() =>
    exceptions.filter(e => e.status === 'dismissed'),
  [exceptions]);

  const routeGroups = useMemo(() => groupByRoute(activeExceptions), [activeExceptions]);

  const rangeInfo = rangeDates(dateRange);

  if (loading) {
    return (
      <div className="exc-workflow">
        <LoadingSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="exc-workflow">
        <div className="exc-error-state">
          <p>Exception data unavailable – retry</p>
          <button
            className="btn btn--secondary"
            onClick={() => { setError(null); setLoading(true); setExceptions([]); }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
    <div className="exc-workflow">
      <div className="exc-summary-strip">
        <div className="exc-summary-strip__left">
          <span className="exc-summary-stat">
            <span className={`exc-summary-stat__val ${criticalCount > 0 ? 'exc-summary-stat__val--red' : ''}`}>{criticalCount} critical</span>
            <span className="exc-summary-stat__dot"> · </span>
            <span className={`exc-summary-stat__val ${warningCount > 0 ? 'exc-summary-stat__val--amber' : ''}`}>{warningCount} warning</span>
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

      <div className="exc-columns">
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
                  key={exc.exception_id}
                  exc={exc}
                  selected={selectedId === exc.exception_id}
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
              key={exc.exception_id}
              exc={exc}
              selected={selectedId === exc.exception_id}
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

        <div className="exc-detail" ref={detailRef}>
          {!selectedExc && (
            <div className="exc-detail__placeholder">Select a service from the list to view details</div>
          )}
          {selectedExc && (
            <>
              <div className="exc-detail__header">
                <div className="exc-detail__heading">
                  <span className={`exc-sev-dot exc-sev-dot--${sevClass(selectedExc.severity)}`} />
                  <h2 className="exc-detail__title">{selectedExc.train_id} · {selectedExc.route} · {selectedExc.date}</h2>
                </div>
                <span className={`badge badge--${sevClass(selectedExc.severity) === 'red' ? 'red' : 'amber'}`}>
                  {selectedExc.severity === 'critical' ? 'Critical' : selectedExc.severity === 'warning' ? 'Warning' : 'Info'}
                </span>
              </div>

              {selectedExc.conradFlag && (
                <div className="exc-flag-box">
                  <span className="exc-flag-box__label">🚩 Conrad flagged this service</span>
                  <p className="exc-flag-box__note">"{selectedExc.conradFlag.note}"</p>
                  {CONDUCTOR_APP_URL && selectedExc.conradFlag.flag_id && (
                    <a
                      className="exc-flag-box__link"
                      href={`${CONDUCTOR_APP_URL}/flags/${selectedExc.conradFlag.flag_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View Conrad's full flag ↗
                    </a>
                  )}
                </div>
              )}

              <CoachOccupancyChart
                coachPeaks={selectedExc.coach_peaks}
                trainId={selectedExc.train_id}
                departure={selectedExc.departure}
              />
              <WeeklyTrendChart trend={selectedExc.trend} trainId={selectedExc.train_id} />

              <div className="exc-action-strip">
                {selectedExc.status === 'unreviewed' && (
                  <>
                    <button className="btn btn--primary" onClick={() => handleReview(selectedExc.exception_id)}>
                      Add to capacity review queue
                    </button>
                    <button className="btn btn--secondary" onClick={() => handleDismiss(selectedExc.exception_id)}>
                      No action required
                    </button>
                  </>
                )}
                {selectedExc.status === 'in_review' && (
                  <div className="exc-action-strip__reviewed">
                    <span>Queued for capacity review · Priority: <strong>{selectedExc.priority}</strong></span>
                    {selectedExc.queuedAt && (
                      <span className="exc-action-strip__queued-at">Added at {new Date(selectedExc.queuedAt).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' })}</span>
                    )}
                  </div>
                )}
                {selectedExc.status === 'dismissed' && (
                  <div className="exc-action-strip__dismissed">
                    <span>Marked no action required</span>
                    <button className="btn btn--ghost exc-action-strip__reopen" onClick={() => handleReopen(selectedExc.exception_id)}>
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
        exception={exceptions.find(e => e.exception_id === reviewModalFor)}
        onConfirm={handleReviewConfirm}
        onCancel={() => setReviewModalFor(null)}
      />
    )}
    </>
  );
}

function ExceptionCard({ exc, selected, onSelect }) {
  const cls = sevClass(exc.severity);
  const peakOccupancy = exc.coach_peaks?.length
    ? Math.max(...exc.coach_peaks.map(cp => cp.peak_pct))
    : null;
  const coachIds = exc.coach_peaks?.filter(cp => cp.peak_pct >= 85).map(cp => cp.coach_id) ?? [];

  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(selected ? null : exc.exception_id);
    }
  };

  return (
    <div
      className={`exc-card exc-card--${cls} ${exc.status === 'dismissed' ? 'exc-card--dismissed' : ''} ${selected ? 'exc-card--selected' : ''}`}
      onClick={() => onSelect(selected ? null : exc.exception_id)}
      tabIndex={0}
      role="button"
      aria-pressed={selected}
      onKeyDown={handleKey}
    >
      <div className="exc-card__top">
        <span className={`exc-sev-dot exc-sev-dot--${cls}`} />
        <span className="exc-card__service">{exc.train_id} · {exc.departure}</span>
        {exc.date && <span className="exc-card__date">{exc.date}</span>}
        {exc.status === 'in_review' && <span className="exc-card__pill exc-card__pill--review">In review</span>}
        {exc.status === 'dismissed' && <span className="exc-card__pill exc-card__pill--dismissed">Dismissed</span>}
      </div>
      {(coachIds.length > 0 || peakOccupancy !== null) && (
        <div className="exc-card__meta">
          {coachIds.length > 0 && <span className="exc-card__coaches">Coaches {coachIds.join(', ')} · </span>}
          {peakOccupancy !== null && <span>Peak: {peakOccupancy}%</span>}
        </div>
      )}
      {exc.conradFlag && (
        <div className="exc-card__flag-row">
          <span className="exc-card__flag">🚩 Conrad flagged</span>
        </div>
      )}
    </div>
  );
}
