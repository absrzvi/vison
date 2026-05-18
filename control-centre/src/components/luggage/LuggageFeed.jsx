import { useState } from 'react';
import { LUGGAGE_STATES, NEXT_STATION, elapsedMin, formatTimestamp, normaliseConf } from '../../mock/luggage';
import { EscalationDetail } from '../live/EscalationDetail';
import './LuggageFeed.css';

const RESOLVED_STATES = new Set(['cleared', 'owner_returned']);
const SEV_BADGE = { red: 'badge--red', amber: 'badge--amber', green: 'badge--green' };

const confClass = (pct) => {
  if (pct == null) return '';
  if (pct >= 85) return 'luggage-item__confidence--high';
  if (pct >= 70) return 'luggage-item__confidence--med';
  return 'luggage-item__confidence--low';
};

const TYPE_FILTERS = [
  { key: 'all',         label: 'All' },
  { key: 'unattended',  label: 'Unattended' },
  { key: 'overcrowded', label: 'Overcrowded' },
  { key: 'oversized',   label: 'Oversized' },
  { key: 'resolved',    label: 'Resolved' },
];

const hasDoorRisk = (ev) =>
  ev.state === 'oversized' && /vestibule|door/i.test(ev.detail + ev.title);

// Sort: unattended first, then by elapsed desc
const sortEvents = (evs) => [...evs].sort((a, b) => {
  if (a.state === 'unattended' && b.state !== 'unattended') return -1;
  if (b.state === 'unattended' && a.state !== 'unattended') return 1;
  return (elapsedMin(a.timestamp) ?? -Infinity) > (elapsedMin(b.timestamp) ?? -Infinity) ? -1 : 1;
});

// Group sorted events by trainId, preserving sort order of first event in each group
function groupByTrain(events) {
  const groups = [];
  const seen = {};
  for (const ev of events) {
    if (!seen[ev.trainId]) {
      seen[ev.trainId] = { trainId: ev.trainId, events: [] };
      groups.push(seen[ev.trainId]);
    }
    seen[ev.trainId].events.push(ev);
  }
  return groups;
}

export function LuggageFeed({ events, onTrainSelect }) {
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [ackedIds, setAckedIds] = useState(new Set());
  const [collapsedTrains, setCollapsedTrains] = useState(new Set());
  const [resolvedExpanded, setResolvedExpanded] = useState(false);

  // Count per filter for pill badges
  const countFor = (key) => {
    if (key === 'resolved') return events.filter(e => RESOLVED_STATES.has(e.state)).length;
    if (key === 'all') return events.filter(e => !RESOLVED_STATES.has(e.state)).length;
    return events.filter(e => e.state === key).length;
  };

  // Active filtered events
  const activeFiltered = sortEvents(
    events.filter(e => {
      if (typeFilter === 'resolved') return false; // handled separately
      if (typeFilter !== 'all') return e.state === typeFilter && !RESOLVED_STATES.has(e.state);
      return !RESOLVED_STATES.has(e.state);
    })
  );

  // Resolved events (always shown at bottom as disclosure)
  const resolvedEvents = sortEvents(events.filter(e => RESOLVED_STATES.has(e.state)));

  // When "Resolved" filter pill is active, show only resolved grouped
  const showOnlyResolved = typeFilter === 'resolved';

  const trainGroups = groupByTrain(showOnlyResolved ? resolvedEvents : activeFiltered);

  const toEscShape = (ev) => ({
    id: ev.id,
    type: 'luggage',
    trainId: ev.trainId,
    coachId: ev.coachId,
    title: ev.title,
    detail: ev.detail,
    severity: LUGGAGE_STATES[ev.state]?.severity ?? 'amber',
    status: RESOLVED_STATES.has(ev.state) ? 'resolved' : ackedIds.has(ev.id) ? 'acknowledged' : 'unacknowledged',
    timestamp: ev.timestamp,
    stillFrame: ev.stillFrame ?? null,
  });

  const handleAck = (e, evId) => {
    e.stopPropagation();
    setAckedIds(prev => new Set([...prev, evId]));
  };

  const toggleTrainCollapse = (trainId) => {
    setCollapsedTrains(prev => {
      const next = new Set(prev);
      next.has(trainId) ? next.delete(trainId) : next.add(trainId);
      return next;
    });
  };

  const renderCard = (ev) => {
    const stateInfo = LUGGAGE_STATES[ev.state];
    const isActive = !RESOLVED_STATES.has(ev.state);
    const isUnattended = ev.state === 'unattended';
    const doorRisk = hasDoorRisk(ev);
    const elapsed = elapsedMin(ev.timestamp);
    const nextStation = NEXT_STATION[ev.trainId];
    const isAcked = ackedIds.has(ev.id);

    return (
      <div
        key={ev.id}
        className={[
          'luggage-item',
          isUnattended ? 'luggage-item--unattended' : isActive ? 'luggage-item--active' : 'luggage-item--resolved',
          selectedEvent?.id === ev.id ? 'luggage-item--selected' : '',
          isAcked ? 'luggage-item--acked' : '',
        ].filter(Boolean).join(' ')}
        onClick={() => setSelectedEvent(selectedEvent?.id === ev.id ? null : ev)}
      >
        <div className="luggage-item__header">
          <span className={`badge ${SEV_BADGE[stateInfo?.severity ?? 'amber']}`}>
            {stateInfo?.label ?? ev.state}
          </span>
          {doorRisk && (
            <span className="luggage-item__door-risk" title="Door clearance risk">⚠ DOOR</span>
          )}
          <span className="luggage-item__title">{ev.title}</span>
          <div className="luggage-item__header-right">
            {ev.confidence != null && (() => {
              const conf = normaliseConf(ev.confidence);
              return (
                <span className={`luggage-item__confidence ${confClass(conf)}`}>
                  {conf}%
                </span>
              );
            })()}
            {elapsed != null && (
              <span className={`luggage-item__elapsed${elapsed >= 25 ? ' luggage-item__elapsed--crit' : elapsed >= 15 ? ' luggage-item__elapsed--warn' : ''}`}>
                {elapsed} min
              </span>
            )}
          </div>
        </div>

        <div className="luggage-item__detail">{ev.detail}</div>

        <div className="luggage-item__meta">
          {ev.coachId != null && (
            <span className="luggage-item__coach-chip">{ev.coachId}</span>
          )}
          {nextStation && isActive && (
            <span className="luggage-item__next-station">→ {nextStation}</span>
          )}
          {isActive && !isAcked && (
            <button className="luggage-item__ack-btn" onClick={e => handleAck(e, ev.id)}>
              Ack
            </button>
          )}
          {isAcked && (
            <span className="luggage-item__acked-label">Acknowledged</span>
          )}
        </div>
      </div>
    );
  };

  const isEmpty = trainGroups.length === 0 && (showOnlyResolved || resolvedEvents.length === 0);

  return (
    <>
    <div className="luggage-feed">
      <div className="luggage-feed__header">
        <span className="luggage-feed__title">Luggage Events</span>
        <div className="filter-pills">
          {TYPE_FILTERS.map(f => {
            const cnt = countFor(f.key);
            return (
              <button
                key={f.key}
                className={`filter-pill ${typeFilter === f.key ? 'filter-pill--active' : ''}`}
                onClick={() => setTypeFilter(f.key)}
              >
                {f.label}{cnt > 0 ? ` (${cnt})` : ''}
              </button>
            );
          })}
        </div>
      </div>

      <div className="luggage-feed__list">
        {isEmpty && (
          <div className="luggage-feed__empty">No events matching this filter.</div>
        )}

        {/* Train-grouped event cards */}
        {trainGroups.map(({ trainId, events: groupEvents }) => {
          const isCollapsed = collapsedTrains.has(trainId);
          const nextStation = NEXT_STATION[trainId];
          const hasUnattended = groupEvents.some(e => e.state === 'unattended');
          const hasCrit = groupEvents.some(e => !RESOLVED_STATES.has(e.state) && !ackedIds.has(e.id));

          return (
            <div key={trainId} className="luggage-train-group">
              <button
                className={[
                  'luggage-train-group__header',
                  hasUnattended ? 'luggage-train-group__header--unattended' : hasCrit ? 'luggage-train-group__header--active' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => toggleTrainCollapse(trainId)}
              >
                <span className="luggage-train-group__id">{trainId}</span>
                <span className="luggage-train-group__count">
                  {groupEvents.length} event{groupEvents.length !== 1 ? 's' : ''}
                </span>
                {nextStation && (
                  <span className="luggage-train-group__station">→ {nextStation}</span>
                )}
                <button
                  className="luggage-train-group__drill"
                  onClick={e => { e.stopPropagation(); onTrainSelect(trainId); }}
                  title="Open train detail"
                >
                  Train detail ↗
                </button>
                <span className="luggage-train-group__chevron">{isCollapsed ? '▶' : '▼'}</span>
              </button>
              {!isCollapsed && groupEvents.map(renderCard)}
            </div>
          );
        })}

        {/* Resolved disclosure row — shown only in "all" view, not in resolved filter */}
        {!showOnlyResolved && resolvedEvents.length > 0 && (
          <div className="luggage-resolved-disclosure">
            <button
              className="luggage-resolved-disclosure__toggle"
              onClick={() => setResolvedExpanded(v => !v)}
            >
              {resolvedExpanded ? '▼' : '▶'} {resolvedEvents.length} resolved event{resolvedEvents.length !== 1 ? 's' : ''}
            </button>
            {resolvedExpanded && (
              <div className="luggage-resolved-disclosure__body">
                {groupByTrain(resolvedEvents).map(({ trainId, events: groupEvents }) => (
                  <div key={trainId} className="luggage-train-group">
                    <div className="luggage-train-group__header luggage-train-group__header--resolved">
                      <span className="luggage-train-group__id">{trainId}</span>
                      <span className="luggage-train-group__count">{groupEvents.length} resolved</span>
                    </div>
                    {groupEvents.map(renderCard)}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>

    {selectedEvent && (
      <EscalationDetail
        escalation={toEscShape(selectedEvent)}
        onClose={() => setSelectedEvent(null)}
        onAcknowledge={(id) => setAckedIds(prev => new Set([...prev, id]))}
        onResolve={() => setSelectedEvent(null)}
      />
    )}
    </>
  );
}
