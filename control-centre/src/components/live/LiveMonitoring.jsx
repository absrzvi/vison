import { useState, useMemo, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useFleetData } from '../../hooks/useFleetData';
import { KpiStrip } from './KpiStrip';
import { FleetList } from './FleetList';
import { FleetMap } from './FleetMap';
import { TrainDetail } from '../train-detail/TrainDetail';
import { LUGGAGE_EVENTS, getLuggageKPIs } from '../../mock/luggage';
import './LiveMonitoring.css';

export function LiveMonitoring() {
  const { fleet, kpis, escalations, lastUpdate, connected, acknowledge, resolve } = useFleetData();
  const location = useLocation();
  const [selectedTrainId, setSelectedTrainId] = useState(location.state?.selectTrainId ?? null);
  const [fleetSort, setFleetSort] = useState('occupancy');

  useEffect(() => {
    if (location.state?.selectTrainId) {
      setSelectedTrainId(location.state.selectTrainId);
    }
  }, [location.state?.selectTrainId]);

  // Auto-select on first load: prefer red > amber > highest occupancy
  useEffect(() => {
    if (fleet.length > 0 && !selectedTrainId && !location.state?.selectTrainId) {
      const sevOrder = { red: 0, amber: 1, green: 2 };
      const sorted = [...fleet].sort((a, b) =>
        sevOrder[a.severity] !== sevOrder[b.severity]
          ? sevOrder[a.severity] - sevOrder[b.severity]
          : b.avgOccupancy - a.avgOccupancy
      );
      setSelectedTrainId(sorted[0].id);
    }
  }, [fleet.length]);
  // TODO: wire to live luggage WebSocket when backend delivers luggage events dynamically
  const luggageKpis = useMemo(() => getLuggageKPIs(LUGGAGE_EVENTS), []);

  const selectedTrain = fleet.find(t => t.id === selectedTrainId) ?? null;
  const isStale = lastUpdate && (Date.now() - lastUpdate.getTime()) > 60000;

  const sortedFleet = useMemo(() => [...fleet].sort((a, b) => {
    if (fleetSort === 'severity') {
      const order = { red: 0, amber: 1, green: 2 };
      return order[a.severity] - order[b.severity];
    }
    return b.avgOccupancy - a.avgOccupancy;
  }), [fleet, fleetSort]);

  if (!connected) {
    return (
      <div className="live-monitoring live-monitoring--loading">
        <div className="live-monitoring__loading-msg">Connecting to fleet data…</div>
      </div>
    );
  }

  return (
    <div className="live-monitoring">
      <KpiStrip kpis={kpis} lastUpdate={lastUpdate} luggageAlerts={luggageKpis.totalActive} onTileClick={(type) => {
        // Navigate to escalations tab filtered by type
        if (type === 'escalations' || type === 'incidents' || type === 'capacity' || type === 'luggage') {
          window.location.href = '/dashboard/escalations';
        }
      }} />
      {isStale && (
        <div className="live-monitoring__stale-banner">
          Data may be stale — last update over 60 seconds ago. Attempting to reconnect…
        </div>
      )}

      <div className="live-monitoring__body">
        <div className={`live-monitoring__left ${selectedTrain ? 'live-monitoring__left--narrow' : ''}`}>
          <FleetList
            trains={sortedFleet}
            selectedTrainId={selectedTrainId}
            onSelect={setSelectedTrainId}
            sortBy={fleetSort}
            onSortChange={setFleetSort}
          />
        </div>

        <div className="live-monitoring__right">
          <FleetMap
            fleet={fleet}
            selectedTrainId={selectedTrainId}
            onTrainSelect={setSelectedTrainId}
          />

          <div className="live-monitoring__feed-row">
            {selectedTrain && (
              <TrainDetail
                train={selectedTrain}
                escalations={escalations.filter(e => e.trainId === selectedTrain.id && e.status !== 'resolved')}
                onClose={() => setSelectedTrainId(null)}
                onAcknowledge={acknowledge}
                onResolve={resolve}
              />
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
