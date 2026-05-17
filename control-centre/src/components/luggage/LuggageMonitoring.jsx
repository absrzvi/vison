import { useState, useMemo } from 'react';
import { LUGGAGE_EVENTS, getLuggageSummaryByTrain, getLuggageKPIs } from '../../mock/luggage';
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

export function LuggageMonitoring() {
  const [selectedTrainId, setSelectedTrainId] = useState(null);

  const events = LUGGAGE_EVENTS;
  const summary = useMemo(() => getLuggageSummaryByTrain(events), [events]);
  const kpis = useMemo(() => getLuggageKPIs(events), [events]);

  const handleTrainSelect = (id) => setSelectedTrainId(prev => prev === id ? null : id);

  if (!events || events.length === 0) {
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
