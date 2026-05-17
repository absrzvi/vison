import { useState } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import { UnifiedFeed } from '../live/UnifiedFeed';
import './EscalationsDashboard.css';

function TriageStrip({ escalations }) {
  const unacked  = escalations.filter(e => e.status === 'unacknowledged').length;
  const open     = escalations.filter(e => e.status === 'acknowledged').length;
  const resolved = escalations.filter(e => e.status === 'resolved').length;
  const total    = escalations.filter(e => e.status !== 'resolved').length;

  return (
    <div className="esc-triage-strip">
      <div className="esc-triage-tile">
        <span className={`esc-triage-tile__value ${unacked > 0 ? 'esc-triage-tile__value--red' : ''}`}>{unacked}</span>
        <span className="esc-triage-tile__label">Unacknowledged</span>
      </div>
      <div className="esc-triage-tile">
        <span className={`esc-triage-tile__value ${open > 0 ? 'esc-triage-tile__value--amber' : ''}`}>{open}</span>
        <span className="esc-triage-tile__label">Acknowledged / open</span>
      </div>
      <div className="esc-triage-tile">
        <span className="esc-triage-tile__value esc-triage-tile__value--green">{resolved}</span>
        <span className="esc-triage-tile__label">Resolved this session</span>
      </div>
      <div className="esc-triage-tile">
        <span className="esc-triage-tile__value">{total}</span>
        <span className="esc-triage-tile__label">Total active</span>
      </div>
    </div>
  );
}

export function EscalationsDashboard() {
  const { escalations, connected, acknowledge, resolve } = useFleetData();
  const [activeFilter, setActiveFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState(null);

  if (!connected) {
    return (
      <div className="esc-dashboard esc-dashboard--loading">
        <div className="esc-dashboard__loading-msg">Connecting to escalation feed…</div>
      </div>
    );
  }

  return (
    <div className="esc-dashboard">
      <TriageStrip escalations={escalations} />
      <div className="esc-dashboard__feed">
        <UnifiedFeed
          escalations={escalations}
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          onAcknowledge={acknowledge}
          onResolve={resolve}
          onTrainSelect={() => {}}
        />
      </div>
    </div>
  );
}
