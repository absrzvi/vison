import { useState } from 'react';
import { EscalationDetail } from './EscalationDetail';
import { SOURCE_LABEL, SEV_CLASS } from '../../constants/escalation';
import './UnifiedFeed.css';

const TYPE_FILTERS = [
  { key: 'all',       label: 'All' },
  { key: 'ai',        label: 'AI' },
  { key: 'occupancy', label: 'Occupancy' },
  { key: 'luggage',   label: 'Luggage' },
  { key: 'conductor', label: 'Staff' },
  { key: 'roland',    label: 'Roland' },
];

const STATUS_FILTERS = [
  { key: 'unacknowledged', label: 'Unacknowledged' },
  { key: 'acknowledged',   label: 'Acknowledged' },
  { key: 'resolved',       label: 'Resolved' },
];

const SEV_FILTERS = [
  { key: 'red',   label: 'Critical' },
  { key: 'amber', label: 'Warning' },
  { key: 'green', label: 'Info' },
];

export function UnifiedFeed({ escalations, activeFilter, onFilterChange, statusFilter: statusFilterProp, onStatusFilterChange, onClearFilters, onAcknowledge, onResolve, onTrainSelect }) {
  const [selectedEscId, setSelectedEscId] = useState(null);
  const [localStatusFilter, setLocalStatusFilter] = useState(null);
  const [sevFilter, setSevFilter] = useState(null);

  // Use prop-controlled statusFilter if provided, otherwise local state
  const statusFilter = statusFilterProp !== undefined ? statusFilterProp : localStatusFilter;
  const setStatusFilter = onStatusFilterChange ?? setLocalStatusFilter;

  const filtered = escalations.filter(e => {
    if (activeFilter !== 'all' && e.type !== activeFilter) return false;
    // By default hide resolved — only show them when the Resolved pill is active
    if (!statusFilter && e.status === 'resolved') return false;
    if (statusFilter && e.status !== statusFilter) return false;
    if (sevFilter && e.severity !== sevFilter) return false;
    return true;
  });

  const toggleStatus = (key) => setStatusFilter(prev => prev === key ? null : key);
  const toggleSev    = (key) => setSevFilter(prev => prev === key ? null : key);

  // Derive modal escalation from live props so status stays current
  const selectedEsc = escalations.find(e => e.id === selectedEscId) ?? null;

  return (
    <>
    <div className="unified-feed">
      <div className="unified-feed__header">
        <span className="unified-feed__title">
          Escalations
          {escalations.filter(e => e.status === 'unacknowledged').length > 0 && (
            <span className="unified-feed__unacked-count">
              {escalations.filter(e => e.status === 'unacknowledged').length} unacknowledged
            </span>
          )}
          {(activeFilter !== 'all' || statusFilter || sevFilter) && (
            <button className="unified-feed__clear-filters" onClick={() => {
              if (onClearFilters) { onClearFilters(); } else { setStatusFilter(null); onFilterChange('all'); }
              setSevFilter(null);
            }}>
              clear filters
            </button>
          )}
        </span>
        <div className="unified-feed__filter-rows">
          <div className="filter-pills" data-testid="pid-feed-filter-bar">
            {TYPE_FILTERS.map(f => (
              <button
                key={f.key}
                className={`filter-pill ${activeFilter === f.key ? 'filter-pill--active' : ''}`}
                onClick={() => onFilterChange(f.key)}
              >{f.label}</button>
            ))}
            <span className="filter-sep" />
            {STATUS_FILTERS.map(f => (
              <button
                key={f.key}
                className={`filter-pill ${statusFilter === f.key ? 'filter-pill--active' : ''}`}
                onClick={() => toggleStatus(f.key)}
              >{f.label}</button>
            ))}
            <span className="filter-sep" />
            {SEV_FILTERS.map(f => (
              <button
                key={f.key}
                className={`filter-pill filter-pill--sev filter-pill--sev-${f.key} ${sevFilter === f.key ? 'filter-pill--active' : ''}`}
                onClick={() => toggleSev(f.key)}
              >{f.label}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="unified-feed__list">
        {filtered.length === 0 && (
          <div className="unified-feed__empty">No escalations matching this filter.</div>
        )}

        {filtered.map(esc => (
          <div
            key={esc.id}
            className={`feed-item ${esc.status === 'unacknowledged' ? 'feed-item--unack' : ''} ${esc.type === 'roland' ? 'feed-item--muted' : ''} ${selectedEscId === esc.id ? 'feed-item--selected' : ''}`}
            onClick={() => setSelectedEscId(selectedEscId === esc.id ? null : esc.id)}
          >
            <div className="feed-item__header">
              <span className={`badge ${SEV_CLASS[esc.severity]}`}>{SOURCE_LABEL[esc.type]}</span>
              <span className="feed-item__title">{esc.title}</span>
              <span className="feed-item__time">{esc.timestamp}</span>
            </div>
            <div className="feed-item__detail">{esc.detail}</div>
            <div className="feed-item__meta">
              <button className="feed-item__train-link" onClick={(e) => { e.stopPropagation(); onTrainSelect(esc.trainId); }}>
                {esc.trainId}{esc.coachId ? ` · ${esc.coachId}` : ''}
              </button>
              <span className={`feed-item__status feed-item__status--${esc.status}`}>{esc.status}</span>
            </div>

            {esc.status === 'unacknowledged' && (
              <div className="feed-item__actions" onClick={e => e.stopPropagation()}>
                <button className="btn btn--primary" onClick={() => onAcknowledge(esc.id)}>Acknowledge</button>
              </div>
            )}

            {esc.status === 'acknowledged' && esc.type !== 'roland' && (
              <div className="feed-item__actions">
                <span className="feed-item__resolve-hint">Open to resolve</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>

    {selectedEsc && (
      <EscalationDetail
        escalation={selectedEsc}
        onClose={() => setSelectedEscId(null)}
        onAcknowledge={(id) => { onAcknowledge(id); }}
        onResolve={(id, outcome, tags) => { onResolve(id, outcome); setSelectedEscId(null); }}
      />
    )}
    </>
  );
}
