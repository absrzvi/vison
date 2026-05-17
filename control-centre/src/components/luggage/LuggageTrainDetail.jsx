import { useNavigate } from 'react-router-dom';
import { LUGGAGE_STATES } from '../../mock/luggage';
import './LuggageTrainDetail.css';

const STATE_PRIORITY = ['unattended', 'oversized', 'overcrowded', 'owner_returned', 'cleared'];

export function LuggageTrainDetail({ trainId, trainSummary, allCoachIds, onClose }) {
  const navigate = useNavigate();
  const events = trainSummary?.events ?? [];

  // Build per-coach state
  const coachMap = {};
  events.forEach(ev => {
    if (!coachMap[ev.coachId]) coachMap[ev.coachId] = [];
    coachMap[ev.coachId].push(ev);
  });

  const coaches = allCoachIds.map(id => {
    const coachEvents = coachMap[id] ?? [];
    const worstState = STATE_PRIORITY.find(s => coachEvents.some(e => e.state === s)) ?? null;
    return { id, events: coachEvents, worstState };
  });

  const activeCount = events.filter(e => e.state !== 'cleared' && e.state !== 'owner_returned').length;

  return (
    <div className="luggage-train-detail">
      <div className="luggage-train-detail__header">
        <div className="luggage-train-detail__identity">
          <h2 className="luggage-train-detail__id">{trainId}</h2>
          {activeCount > 0
            ? <span className="badge badge--amber">{activeCount} active</span>
            : <span className="badge badge--green">Clear</span>
          }
        </div>
        <button
          className="btn btn--secondary luggage-td__occ-btn"
          onClick={() => navigate('/dashboard/occupancy', { state: { selectTrainId: trainId } })}
          title={`View ${trainId} in Occupancy tab`}
        >View in Occupancy</button>
        <button className="train-detail__close" onClick={onClose} aria-label="Close">&times;</button>
      </div>

      <div className="luggage-train-detail__section-title">Luggage status by coach</div>

      <div className="luggage-coach-grid">
        {coaches.map(coach => {
          const stateInfo = coach.worstState ? LUGGAGE_STATES[coach.worstState] : null;
          const isActive = coach.worstState && coach.worstState !== 'cleared' && coach.worstState !== 'owner_returned';
          return (
            <div
              key={coach.id}
              className={`luggage-coach-cell ${isActive ? 'luggage-coach-cell--active' : ''}`}
              style={isActive ? { borderColor: stateInfo?.color + '66', background: stateInfo?.color + '10' } : {}}
            >
              <span className="luggage-coach-cell__id">{coach.id}</span>
              {stateInfo
                ? <span className="luggage-coach-cell__state" style={{ color: stateInfo.color }}>{stateInfo.label}</span>
                : <span className="luggage-coach-cell__clear">Clear</span>
              }
              {coach.events.length > 0 && (
                <span className="luggage-coach-cell__count">{coach.events.length} event{coach.events.length > 1 ? 's' : ''}</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="luggage-train-detail__section-title luggage-train-detail__section-title--spaced">Events</div>
      <div className="luggage-train-detail__events">
        {events.length === 0
          ? <p className="luggage-train-detail__empty">No luggage events for this train.</p>
          : events.map(ev => {
            const stateInfo = LUGGAGE_STATES[ev.state];
            return (
              <div key={ev.id} className="luggage-train-detail__event-row">
                <span className={`badge ${ev.state === 'unattended' ? 'badge--red' : stateInfo?.severity === 'green' ? 'badge--green' : 'badge--amber'}`}>
                  {stateInfo?.label ?? ev.state}
                </span>
                <div className="luggage-train-detail__event-info">
                  <span className="luggage-train-detail__event-coach">{ev.coachId}</span>
                  <span className="luggage-train-detail__event-title">{ev.title}</span>
                </div>
                <span className="luggage-train-detail__event-time">{ev.timestamp}</span>
              </div>
            );
          })
        }
      </div>
    </div>
  );
}
