import { useState, useMemo } from 'react';
import { getLuggageSummaryByTrain, getLuggageKPIs } from '../../mock/luggage';
import { useFleetData } from '../../context/FleetContext';
import { LuggageKpiStrip } from './LuggageKpiStrip';
import { LuggageFeed } from './LuggageFeed';
import { LuggageTrainDetail } from './LuggageTrainDetail';
import './LuggageMonitoring.css';

// Coach counts per train (mirrors websocket.js TRAINS)
const TRAIN_COACHES = {
  'R5001C-031': 8, 'R5001C-022': 8, 'R5001C-017': 6,
  'R5001C-008': 6, 'R5001C-044': 8, 'R5001C-055': 8,
  'R5001C-012': 6, 'R5001C-003': 6,
};

function LuggageMonitoringSkeleton() {
  return (
    <div className="luggage-monitoring luggage-monitoring--loading">
      <div className="luggage-kpi-strip luggage-kpi-strip--skeleton">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="lkpi">
            <div className="skeleton-pulse" style={{ width: 48, height: 28, borderRadius: 4 }} />
            <div className="skeleton-pulse" style={{ width: 80, height: 11, borderRadius: 3, marginTop: 4 }} />
          </div>
        ))}
      </div>
      <div className="luggage-monitoring__body">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="skeleton-pulse" style={{ height: 64, margin: '6px 16px', borderRadius: 6 }} />
        ))}
      </div>
    </div>
  );
}

export function LuggageMonitoring() {
  const [selectedTrainId, setSelectedTrainId] = useState(null);
  const { luggageEvents: events, wsReady } = useFleetData();
  const summary = useMemo(() => getLuggageSummaryByTrain(events), [events]);
  const kpis = useMemo(() => getLuggageKPIs(events), [events]);

  const handleTrainSelect = (id) => setSelectedTrainId(prev => prev === id ? null : id);

  if (!wsReady) {
    return <LuggageMonitoringSkeleton />;
  }

  if (events.length === 0) {
    return (
      <div className="luggage-monitoring luggage-monitoring--empty">
        <div className="luggage-monitoring__empty-msg">No luggage events received yet.</div>
      </div>
    );
  }

  const coachIds = selectedTrainId
    ? Array.from({ length: TRAIN_COACHES[selectedTrainId] ?? 6 }, (_, i) => `C${i + 1}`)
    : [];

  return (
    <div className="luggage-monitoring">
      <LuggageKpiStrip kpis={kpis} />

      <div className="luggage-monitoring__body">
        {selectedTrainId ? (
          <LuggageTrainDetail
            trainId={selectedTrainId}
            trainSummary={summary[selectedTrainId]}
            allCoachIds={coachIds}
            onClose={() => setSelectedTrainId(null)}
          />
        ) : (
          <LuggageFeed
            events={events}
            onTrainSelect={handleTrainSelect}
          />
        )}
      </div>
    </div>
  );
}
