import './KpiStrip.css';

function freshnessLabel(date) {
  if (!date) return '—';
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 60) return 'Live';
  return `${Math.floor(s / 60)}m ago`;
}

export function KpiStrip({ kpis, lastUpdate, luggageAlerts, onTileClick }) {
  const stale = lastUpdate && (Date.now() - lastUpdate.getTime()) > 60000;

  return (
    <div className="kpi-strip">
      <div className="kpi-tile">
        <span className="kpi-tile__value">{kpis.activeTrains ?? '—'}</span>
        <span className="kpi-tile__label">active trains</span>
      </div>
      <button
        className={`kpi-tile kpi-tile--interactive ${kpis.openEscalations > 0 ? 'kpi-tile--alert' : ''}`}
        onClick={() => onTileClick?.('escalations')}
        title="Filter feed to escalations"
      >
        <span className={`kpi-tile__value ${kpis.openEscalations > 0 ? 'kpi-tile__value--amber' : ''}`}>
          {kpis.openEscalations ?? '—'}
        </span>
        <span className="kpi-tile__label">open escalations</span>
      </button>
      <button
        className={`kpi-tile kpi-tile--interactive ${kpis.openIncidents > 0 ? 'kpi-tile--alert' : ''}`}
        onClick={() => onTileClick?.('incidents')}
        title="Filter feed to incidents"
      >
        <span className={`kpi-tile__value ${kpis.openIncidents > 0 ? 'kpi-tile__value--red' : ''}`}>
          {kpis.openIncidents ?? '—'}
        </span>
        <span className="kpi-tile__label">active incidents</span>
      </button>
      <button
        className={`kpi-tile kpi-tile--interactive ${kpis.capacityAlerts > 0 ? 'kpi-tile--alert' : ''}`}
        onClick={() => onTileClick?.('capacity')}
        title="Filter feed to capacity alerts"
      >
        <span className={`kpi-tile__value ${kpis.capacityAlerts > 0 ? 'kpi-tile__value--amber' : ''}`}>
          {kpis.capacityAlerts ?? 0}
        </span>
        <span className="kpi-tile__label">capacity alerts</span>
      </button>
      <button
        className={`kpi-tile kpi-tile--interactive ${luggageAlerts > 0 ? 'kpi-tile--alert' : ''}`}
        onClick={() => onTileClick?.('luggage')}
        title="Filter feed to luggage alerts"
      >
        <span className={`kpi-tile__value ${luggageAlerts > 0 ? 'kpi-tile__value--amber' : ''}`}>
          {luggageAlerts ?? 0}
        </span>
        <span className="kpi-tile__label">luggage alerts</span>
      </button>
      <div className={`kpi-tile kpi-tile--refresh ${stale ? 'kpi-tile--stale' : ''}`}>
        <span className="kpi-tile__value kpi-tile__value--sm">{freshnessLabel(lastUpdate)}</span>
        <span className="kpi-tile__label">{stale ? 'reconnecting…' : 'last update'}</span>
      </div>
    </div>
  );
}
