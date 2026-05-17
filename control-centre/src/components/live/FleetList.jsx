import { useState } from 'react';
import './FleetList.css';

const SEVERITY_DOT = { red: '#FF3B3B', amber: '#F5A623', green: '#22C55E' };
// 4-band occupancy scale: gives operators finer granularity than the 3-band severity model
const OCCUPANCY_COLOR = (pct) =>
  pct >= 90 ? '#FF3B3B' : pct >= 75 ? '#FF6B00' : pct >= 50 ? '#F5A623' : '#22C55E';

function TrainCard({ train, selectedTrainId, onSelect }) {
  return (
    <button
      className={`train-card ${train.severity === 'red' ? 'train-card--alert' : ''} ${selectedTrainId === train.id ? 'train-card--selected' : ''}`}
      onClick={() => onSelect(train.id)}
    >
      <div className="train-card__header">
        <span className="train-card__id">{train.id}</span>
        <span className="train-card__dot" style={{ background: SEVERITY_DOT[train.severity] }} />
      </div>
      <div className="train-card__route">{train.route}</div>
      {train.dwellStatus && (
        <div className="train-card__dwell">
          <span className="dwell-pill">
            Dwelling · {train.dwellStatus.station} · +{train.dwellStatus.delayMin} min
          </span>
        </div>
      )}
      <div className="train-card__coach-bar">
        {train.coaches.map(coach => {
          const isCritical = coach.occupancy >= 90;
          return (
            <div
              key={coach.id}
              className="coach-bar__track"
              title={`${coach.id}: ${coach.occupancy}%`}
            >
              <div
                className={`coach-bar__fill${isCritical ? ' coach-bar__fill--critical' : ''}`}
                style={{
                  height: `${Math.max(8, coach.occupancy)}%`,
                  background: OCCUPANCY_COLOR(coach.occupancy),
                }}
              />
              {coach.hasAlert && <span className="coach-bar__alert-dot" />}
            </div>
          );
        })}
      </div>
      <div className="train-card__meta">
        <span>{train.avgOccupancy}% avg</span>
      </div>
    </button>
  );
}

export function FleetList({ trains, selectedTrainId, onSelect, sortBy, onSortChange }) {
  const [showNormal, setShowNormal] = useState(false);

  const nonNormal = trains.filter(t => t.severity !== 'green');
  const normal    = trains.filter(t => t.severity === 'green');

  const handleSortChange = (sort) => {
    localStorage.setItem('fleet-sort-pref', sort);
    onSortChange(sort);
  };

  return (
    <div className="fleet-list">
      <div className="fleet-list__header">
        <span className="fleet-list__heading">Fleet</span>
        <div className="fleet-sort-toggle" data-testid="fleet-sort-toggle">
          <button
            className={`fleet-sort-btn ${sortBy === 'passengers' ? 'fleet-sort-btn--active' : ''}`}
            onClick={() => handleSortChange('passengers')}
          >Passengers</button>
          <button
            className={`fleet-sort-btn ${sortBy === 'severity' ? 'fleet-sort-btn--active' : ''}`}
            onClick={() => handleSortChange('severity')}
          >Severity</button>
        </div>
      </div>

      {nonNormal.map(train => (
        <TrainCard key={train.id} train={train} selectedTrainId={selectedTrainId} onSelect={onSelect} />
      ))}

      {normal.length > 0 && (
        <button className="fleet-list__normal-toggle" onClick={() => setShowNormal(v => !v)}>
          {showNormal ? `Hide normal trains` : `Show ${normal.length} normal train${normal.length !== 1 ? 's' : ''}`}
        </button>
      )}

      {showNormal && normal.map(train => (
        <TrainCard key={train.id} train={train} selectedTrainId={selectedTrainId} onSelect={onSelect} />
      ))}
    </div>
  );
}
