import './LuggageKpiStrip.css';

export function LuggageKpiStrip({ kpis }) {
  return (
    <div className="luggage-kpi-strip">
      <div className={`lkpi ${kpis.longestUnattended ? 'lkpi--red' : ''}`}>
        <span className="lkpi__value">{kpis.longestUnattended ?? '—'}</span>
        <span className="lkpi__label">Longest Unattended</span>
      </div>
      <div className="lkpi-divider" />
      <div className={`lkpi ${kpis.longestActive ? 'lkpi--amber' : ''}`}>
        <span className="lkpi__value">{kpis.longestActive ?? '—'}</span>
        <span className="lkpi__label">Longest Active</span>
      </div>
      <div className="lkpi-divider" />
      <div className={`lkpi ${(kpis.unattendedAlerts ?? kpis.unattended) > 0 ? 'lkpi--red' : ''}`}>
        <span className="lkpi__value">{kpis.unattendedAlerts ?? kpis.unattended}</span>
        <span className="lkpi__label">Unattended Alerts</span>
      </div>
      <div className="lkpi-divider" />
      <div className={`lkpi ${kpis.overcrowded > 0 ? 'lkpi--amber' : ''}`}>
        <span className="lkpi__value">{kpis.overcrowded}</span>
        <span className="lkpi__label">Overcrowded Areas</span>
      </div>
      <div className="lkpi-divider" />
      <div className={`lkpi ${kpis.oversized > 0 ? 'lkpi--amber' : ''}`}>
        <span className="lkpi__value">{kpis.oversized}</span>
        <span className="lkpi__label">Oversized Items</span>
      </div>
      <div className="lkpi-divider" />
      <div className="lkpi lkpi--green">
        <span className="lkpi__value">{kpis.clearedLastHour}</span>
        <span className="lkpi__label">Cleared / Resolved</span>
      </div>
    </div>
  );
}
