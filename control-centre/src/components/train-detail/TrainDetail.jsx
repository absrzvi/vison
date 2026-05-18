import { useState, useEffect, useRef } from 'react';
import { EscalationDetail } from '../live/EscalationDetail';
import { SOURCE_LABEL, SEV_CLASS } from '../../constants/escalation';
import { useFleetData } from '../../context/FleetContext';
import './TrainDetail.css';

// 4-band occupancy scale: gives operators finer granularity than the 3-band severity model
const OCCUPANCY_COLOR = (pct) =>
  pct >= 90 ? '#FF3B3B' : pct >= 75 ? '#FF6B00' : pct >= 50 ? '#F5A623' : '#22C55E';

const STATUS_LABEL = { red: 'Alert', amber: 'Attention', green: 'Operational' };


export function TrainDetail({ train, escalations, onClose, onAcknowledge, onResolve }) {
  const [dwellAcked, setDwellAcked] = useState(false);
  const [selectedEscId, setSelectedEscId] = useState(null);
  const { trainAlerts, trainAlertsLoading, trainAlertsError, fetchTrainAlerts } = useFleetData();

  // Fetch alerts on mount and whenever the train id changes; also reset selected escalation.
  const prevTrainIdRef = useRef(train.id);
  if (prevTrainIdRef.current !== train.id) {
    prevTrainIdRef.current = train.id;
    setSelectedEscId(null);
  }

  useEffect(() => {
    fetchTrainAlerts(train.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [train.id]);

  // Derive from live props by ID so status always reflects latest context state
  const selectedEsc = escalations.find(e => e.id === selectedEscId) ?? null;

  // null = not yet fetched (treat as loading), array = fetched
  const activeAlerts = trainAlerts[train.id] ?? null;
  // Show loading if explicitly loading OR if data hasn't arrived yet (null)
  const alertsLoading = !!trainAlertsLoading[train.id] || activeAlerts === null;
  const alertsError = trainAlertsError[train.id] ?? null;

  // All other open escalations (acknowledged but not resolved)
  const openEscalations = escalations.filter(e => e.status === 'acknowledged');

  return (
    <>
    <div className="train-detail">
      <div className="train-detail__header">
        <div className="train-detail__identity">
          <h2 className="train-detail__id">{train.id}</h2>
          <span className={`badge ${SEV_CLASS[train.severity]}`}>{STATUS_LABEL[train.severity]}</span>
        </div>
        <button className="train-detail__close" onClick={onClose} aria-label="Close train detail">&times;</button>
      </div>

      <div className="train-detail__route">
        {train.route}
        {train.dwellStatus
          ? <span className="train-detail__route-delay"> · +{train.dwellStatus.delayMin} min · next dep {train.dwellStatus.scheduledDep}</span>
          : null
        }
      </div>

      {train.dwellStatus && (
        <div className="train-detail__dwell-banner">
          <div className="dwell-banner__row">
            <span className="dwell-banner__label">Dwelling at station</span>
            <span className="dwell-banner__delay">+{train.dwellStatus.delayMin} min</span>
          </div>
          <div className="dwell-banner__detail">
            <span className="dwell-banner__station">{train.dwellStatus.station}</span>
            <span className="dwell-banner__sep">·</span>
            <span>Sched. dep. {train.dwellStatus.scheduledDep}</span>
            <span className="dwell-banner__sep">·</span>
            <span>Stopped since {train.dwellStatus.dwellingSince}</span>
          </div>
          <div className="dwell-banner__crowding">
            Platform crowding: <strong>{train.dwellStatus.platformCrowding}</strong>
          </div>
          <div className="dwell-banner__actions">
            {dwellAcked
              ? <span className="dwell-banner__acked">Dispatch acknowledged</span>
              : <button className="btn btn--secondary dwell-banner__dispatch-btn" onClick={() => setDwellAcked(true)}>
                  Acknowledge &amp; Dispatch
                </button>
            }
          </div>
        </div>
      )}

      <section className="train-detail__section">
        <h3 className="train-detail__section-title">Coach Occupancy</h3>
        <div className="coach-grid">
          {train.coaches.map(coach => (
            <div
              key={coach.id}
              className={`coach-cell ${coach.hasAlert ? 'coach-cell--alert' : ''}`}
              style={{ cursor: 'default' }}
            >
              <span className="coach-cell__label">{coach.id}</span>
              <span className="coach-cell__occ" style={{ color: OCCUPANCY_COLOR(coach.occupancy) }}>
                {coach.occupancy}%
              </span>
              {coach.hasAlert && <span className="coach-cell__alert-dot" title="Active alert" />}
            </div>
          ))}
        </div>
      </section>

      <section className="train-detail__section" data-testid="td-alerts-list">
        <h3 className="train-detail__section-title">
          Active Alerts {activeAlerts && activeAlerts.length > 0 ? `(${activeAlerts.length})` : ''}
        </h3>
        {alertsLoading && <p className="train-detail__empty">Loading alerts…</p>}
        {alertsError && !alertsLoading && (
          <div className="train-detail__alerts-error">
            <p className="train-detail__empty">Alert data unavailable</p>
            <button className="btn btn--ghost" onClick={() => fetchTrainAlerts(train.id)}>Retry</button>
          </div>
        )}
        {!alertsLoading && !alertsError && activeAlerts && activeAlerts.length === 0 && (
          <p className="train-detail__empty">No active alerts for this train</p>
        )}
        {!alertsLoading && !alertsError && activeAlerts && activeAlerts.length > 0 && activeAlerts.map(a => {
          // alert_id may match an escalation id for drill-in; fall back to no selection if not found
          const matchingEsc = escalations.find(e => e.id === a.alert_id);
          return (
            <button
              key={a.alert_id}
              className={`train-detail__alert-row train-detail__alert-row--${a.type}`}
              onClick={() => matchingEsc && setSelectedEscId(a.alert_id)}
              style={matchingEsc ? undefined : { cursor: 'default' }}
            >
              <span className="train-detail__alert-type">{a.title}</span>
              {a.coach_id && <span className="train-detail__alert-detail">{a.coach_id}</span>}
              {a.confidence != null && <span className="train-detail__alert-detail">{a.confidence}%</span>}
              <span className="train-detail__alert-detail">{a.raised_at}</span>
            </button>
          );
        })}
      </section>

      {openEscalations.length > 0 && (
        <section className="train-detail__section">
          <h3 className="train-detail__section-title">Open Escalations ({openEscalations.length})</h3>
          {openEscalations.map(e => (
            <button
              key={e.id}
              className={`train-detail__esc-row ${selectedEscId === e.id ? 'train-detail__esc-row--selected' : ''}`}
              onClick={() => setSelectedEscId(selectedEscId === e.id ? null : e.id)}
            >
              <span className={`badge ${SEV_CLASS[e.severity]}`}>{SOURCE_LABEL[e.type]}</span>
              <span className="train-detail__esc-title">{e.title}</span>
              <span className="train-detail__esc-status">{e.status}</span>
            </button>
          ))}
        </section>
      )}
    </div>

    {selectedEsc && (
      <EscalationDetail
        escalation={selectedEsc}
        onClose={() => setSelectedEscId(null)}
        onAcknowledge={(id) => { onAcknowledge?.(id); }}
        onResolve={(id, outcome, tags) => { onResolve?.(id, outcome, tags); setSelectedEscId(null); }}
      />
    )}

    </>
  );
}
