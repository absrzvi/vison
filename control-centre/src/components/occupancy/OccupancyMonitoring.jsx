import { useState, useMemo, useEffect } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import './OccupancyMonitoring.css';

// ─── Colour helpers ──────────────────────────────────────────────────────────

const OCC_COLOR = (pct) =>
  pct >= 90 ? '#FF3B3B' : pct >= 75 ? '#FF6B00' : pct >= 50 ? '#F5A623' : '#22C55E';

const SEV_COLOR = { red: '#FF3B3B', amber: '#F5A623', green: '#22C55E' };

// ─── KPI strip ───────────────────────────────────────────────────────────────

function OccKpiStrip({ fleet, overThreshold, threshold, lastUpdate }) {
  const fleetAvg =
    fleet.length > 0
      ? Math.round(fleet.reduce((s, t) => s + t.avgOccupancy, 0) / fleet.length)
      : null;

  const peakTrain = fleet.length > 0
    ? fleet.reduce((best, t) => (t.avgOccupancy > best.avgOccupancy ? t : best), fleet[0])
    : null;

  const stale = lastUpdate && Date.now() - lastUpdate.getTime() > 60000;

  return (
    <div className="occ-kpi-strip">
      <KpiCell label="Active Trains" value={fleet.length || '—'} />
      <div className="occ-kpi-divider" />
      <KpiCell
        label="Fleet Avg Occupancy"
        value={fleetAvg != null ? `${fleetAvg}%` : '—'}
        valueColor={fleetAvg != null ? OCC_COLOR(fleetAvg) : undefined}
      />
      <div className="occ-kpi-divider" />
      <KpiCell
        label={`Over ${threshold}% Threshold`}
        value={overThreshold}
        valueColor={overThreshold > 0 ? 'var(--obb-sev-warning)' : undefined}
      />
      <div className="occ-kpi-divider" />
      <KpiCell
        label="Peak Train"
        value={peakTrain ? `${peakTrain.avgOccupancy}%` : '—'}
        sub={peakTrain?.id}
        valueColor={peakTrain ? OCC_COLOR(peakTrain.avgOccupancy) : undefined}
      />
      <div className="occ-kpi-divider" />
      <KpiCell
        label="Last Update"
        value={stale ? 'Stale' : 'Live'}
        valueColor={stale ? 'var(--obb-sev-warning)' : '#22C55E'}
        small
      />
    </div>
  );
}

function KpiCell({ label, value, sub, valueColor, small }) {
  return (
    <div className="occ-kpi">
      <span
        className={`occ-kpi__value${small ? ' occ-kpi__value--sm' : ''}`}
        style={valueColor ? { color: valueColor } : undefined}
      >
        {value}
      </span>
      {sub && <span className="occ-kpi__sub">{sub}</span>}
      <span className="occ-kpi__label">{label}</span>
    </div>
  );
}

// ─── Left panel — train list ──────────────────────────────────────────────────

function TrainListItem({ train, threshold, escalationCount, isSelected, onSelect }) {
  const overCount = train.coaches.filter(c => c.occupancy >= threshold).length;
  const isDwelling = !!train.dwellStatus;

  return (
    <button
      className={[
        'occ-list-item',
        isSelected ? 'occ-list-item--selected' : '',
        train.severity === 'red' ? 'occ-list-item--critical' : '',
      ].filter(Boolean).join(' ')}
      onClick={() => onSelect(train.id)}
      type="button"
    >
      {/* Row 1: dot + ID + avg */}
      <div className="occ-list-item__top">
        <span
          className="occ-list-item__dot"
          style={{ background: SEV_COLOR[train.severity] }}
        />
        <span className="occ-list-item__id">{train.id}</span>
        <span
          className="occ-list-item__avg"
          style={{ color: OCC_COLOR(train.avgOccupancy) }}
        >
          {train.avgOccupancy}%
        </span>
      </div>

      {/* Row 2: route + pills */}
      <div className="occ-list-item__bottom">
        <span className="occ-list-item__route">{train.route}</span>
        <div className="occ-list-item__pills">
          {overCount > 0 && (
            <span className="occ-pill occ-pill--warn">
              {overCount}/{train.coaches.length}
            </span>
          )}
          {isDwelling && (
            <span className="occ-pill occ-pill--dwell">Dwell</span>
          )}
          {escalationCount > 0 && (
            <span className="occ-pill occ-pill--esc">{escalationCount}</span>
          )}
        </div>
      </div>
    </button>
  );
}

// ─── Right panel — detail view ────────────────────────────────────────────────

/**
 * Compute flow direction between two adjacent coaches.
 * Returns 'left' | 'right' | 'both' | 'none'
 * Passengers flow FROM higher occupancy TO lower occupancy.
 * If both are very full (≥80) we show bidirectional (pressure from platform).
 * If difference is small (< 8 pts) we show nothing.
 */
function getFlowDirection(leftOcc, rightOcc) {
  const diff = leftOcc - rightOcc;
  if (leftOcc >= 80 && rightOcc >= 80) return 'both';
  if (Math.abs(diff) < 8) return 'none';
  // flow toward the less-full side
  return diff > 0 ? 'right' : 'left';
}

function FlowLane({ leftOcc, rightOcc }) {
  const direction = getFlowDirection(leftOcc, rightOcc);
  if (direction === 'none') return <div className="occ-flow-lane occ-flow-lane--none" />;

  const showLeft  = direction === 'left'  || direction === 'both';
  const showRight = direction === 'right' || direction === 'both';
  // Intensity: stronger difference = faster/more dots
  const diff = Math.abs(leftOcc - rightOcc);
  const intensity = diff >= 30 ? 'high' : diff >= 15 ? 'mid' : 'low';

  return (
    <div className={`occ-flow-lane occ-flow-lane--${intensity}`}>
      {showRight && (
        <div className="occ-flow-track occ-flow-track--right">
          <span className="occ-flow-dot" style={{ '--delay': '0s' }} />
          <span className="occ-flow-dot" style={{ '--delay': '0.4s' }} />
          {intensity !== 'low' && <span className="occ-flow-dot" style={{ '--delay': '0.8s' }} />}
          {intensity === 'high' && <span className="occ-flow-dot" style={{ '--delay': '1.2s' }} />}
        </div>
      )}
      {showLeft && (
        <div className="occ-flow-track occ-flow-track--left">
          <span className="occ-flow-dot" style={{ '--delay': '0.2s' }} />
          <span className="occ-flow-dot" style={{ '--delay': '0.6s' }} />
          {intensity !== 'low' && <span className="occ-flow-dot" style={{ '--delay': '1.0s' }} />}
          {intensity === 'high' && <span className="occ-flow-dot" style={{ '--delay': '1.4s' }} />}
        </div>
      )}
    </div>
  );
}

function MetricCell({ icon, value, label, warnClass }) {
  return (
    <div className="occ-metric">
      <span className={`occ-metric__value${warnClass ? ` ${warnClass}` : ''}`}>
        {icon}{value}
      </span>
      <span className="occ-metric__label">{label}</span>
    </div>
  );
}

function CoachCard({ coach, isSelected, onClick }) {
  const color = OCC_COLOR(coach.occupancy);

  const doorClass =
    coach.doorCongestion > 75 ? 'occ-metric--crit' :
    coach.doorCongestion > 50 ? 'occ-metric--warn' : '';

  const tempClass =
    coach.tempC > 26 ? 'occ-metric--crit' :
    coach.tempC > 24 ? 'occ-metric--warn' : '';

  return (
    <div
      className={[
        'occ-coach-card',
        coach.hasAlert ? 'occ-coach-card--alert' : '',
        isSelected   ? 'occ-coach-card--selected' : '',
      ].filter(Boolean).join(' ')}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onClick?.()}
      style={{ cursor: 'pointer' }}
    >
      {/* Bar track */}
      <div className="occ-coach-card__bar-track">
        <div
          className="occ-coach-card__bar-fill"
          style={{ height: `${Math.max(4, coach.occupancy)}%`, background: color }}
        />
      </div>

      {/* Meta row */}
      <div className="occ-coach-card__meta">
        <span className="occ-coach-card__id">{coach.id}</span>
        <span className="occ-coach-card__pct" style={{ color }}>{coach.occupancy}%</span>
        {coach.hasAlert && <span className="occ-coach-card__alert-dot" title="Alert active" />}
      </div>

      {/* Incident dot — only shown if fall detected, keeps card compact */}
      {coach.hasFall && (
        <div className="occ-coach-card__incident">⚠ INCIDENT</div>
      )}
    </div>
  );
}

// ─── Coach detail sub-components ─────────────────────────────────────────────

/**
 * Derive a seat colour from occupancy %.
 * We spread seats across the coach and colour proportionally.
 * Seats up to occupied count get coloured; the rest use a neutral fill.
 */
function seatColor(occupied, total, index) {
  const occupiedCount = Math.round((occupied / 100) * total);
  if (index < occupiedCount) {
    if (occupied >= 85) return '#FF3B3B';
    if (occupied >= 70) return '#F5A623';
    return '#22C55E';
  }
  return 'rgba(255,255,255,0.08)';
}

function CoachSeatMap({ occupancy }) {
  // 2+2 layout, 5 rows = 20 seats
  const ROWS = 5;
  const SEATS_PER_ROW = 4; // two pairs
  const total = ROWS * SEATS_PER_ROW;

  const seats = Array.from({ length: total }, (_, i) => ({
    id: i,
    color: seatColor(occupancy, total, i),
  }));

  return (
    <div>
      <div className="occ-seat-map">
        {Array.from({ length: ROWS }, (_, row) => (
          <div key={row} className="occ-seat-map__row">
            {/* Left pair */}
            <div className="occ-seat-map__pair">
              {[0, 1].map(col => {
                const idx = row * SEATS_PER_ROW + col;
                return (
                  <div
                    key={col}
                    className="occ-seat"
                    style={{ background: seats[idx].color }}
                  />
                );
              })}
            </div>
            {/* Aisle */}
            <div className="occ-seat-map__aisle" />
            {/* Right pair */}
            <div className="occ-seat-map__pair">
              {[2, 3].map(col => {
                const idx = row * SEATS_PER_ROW + col;
                return (
                  <div
                    key={col}
                    className="occ-seat"
                    style={{ background: seats[idx].color }}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {/* Legend */}
      <div className="occ-seat-map__legend">
        <span className="occ-seat-map__legend-item">
          <span className="occ-seat-map__legend-dot" style={{ background: '#22C55E' }} /> Free
        </span>
        <span className="occ-seat-map__legend-item">
          <span className="occ-seat-map__legend-dot" style={{ background: '#F5A623' }} /> Limited
        </span>
        <span className="occ-seat-map__legend-item">
          <span className="occ-seat-map__legend-dot" style={{ background: '#FF3B3B' }} /> Full
        </span>
      </div>
    </div>
  );
}

function DoorCongestionBar({ doorCongestion }) {
  const barColor =
    doorCongestion > 75 ? '#FF3B3B' :
    doorCongestion > 50 ? '#F5A623' : '#22C55E';

  return (
    <div>
      <div className="occ-coach-detail__section-label">Door Congestion</div>
      <div className="occ-door-bar">
        <span className="occ-door-bar__marker occ-door-bar__marker--left" title="Left door">⬛</span>
        <div className="occ-door-bar__track">
          <div
            className="occ-door-bar__fill"
            style={{ width: `${doorCongestion}%`, background: barColor }}
          />
          <span className="occ-door-bar__label">{doorCongestion}%</span>
        </div>
        <span className="occ-door-bar__marker occ-door-bar__marker--right" title="Right door">⬛</span>
      </div>
    </div>
  );
}

/** Generate 8 mock historical occupancy readings walking backwards from current */
function mockHistory(currentOcc) {
  const readings = [currentOcc];
  for (let i = 1; i < 8; i++) {
    const prev = readings[readings.length - 1];
    const delta = (Math.random() - 0.5) * 16; // ±8%
    readings.push(Math.min(100, Math.max(0, Math.round(prev + delta))));
  }
  return readings.reverse(); // oldest first
}

function CoachSparkline({ occupancy }) {
  const W = 200;
  const H = 40;
  const THRESHOLD_Y = H - H * 0.75; // y position for 75% line

  // Stable mock history keyed to occupancy value (changes only when coach changes)
  const history = useMemo(() => mockHistory(occupancy), [occupancy]);

  const maxVal = 100;
  const points = history.map((v, i) => {
    const x = (i / (history.length - 1)) * W;
    const y = H - (v / maxVal) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <div>
      <div className="occ-coach-detail__section-label">Last 8 Readings</div>
      <svg
        className="occ-sparkline"
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        aria-label="Occupancy history sparkline"
      >
        {/* Grid line at 75% */}
        <line
          x1="0" y1={THRESHOLD_Y}
          x2={W} y2={THRESHOLD_Y}
          stroke="rgba(245,166,35,0.3)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        {/* Threshold label */}
        <text
          x={W - 2} y={THRESHOLD_Y - 2}
          fontSize="8"
          fill="rgba(245,166,35,0.6)"
          textAnchor="end"
        >75%</text>
        {/* Area fill under line */}
        <defs>
          <linearGradient id="spark-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--obb-blue-accent)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--obb-blue-accent)" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polyline
          points={points + ` ${W},${H} 0,${H}`}
          fill="url(#spark-grad)"
          stroke="none"
        />
        {/* Line */}
        <polyline
          points={points}
          fill="none"
          stroke="var(--obb-blue-accent)"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* Last point dot */}
        {(() => {
          const last = history[history.length - 1];
          const x = W;
          const y = H - (last / maxVal) * H;
          return (
            <circle cx={W} cy={y} r="2.5" fill="var(--obb-blue-accent)" />
          );
        })()}
      </svg>
    </div>
  );
}

function CoachDetailPanel({ coach, isDwellTrain }) {
  const dwellContrib = isDwellTrain && coach.doorCongestion > 40;

  return (
    <div className="occ-coach-detail">
      {/* Left column — spatial */}
      <div className="occ-coach-detail__left">
        <div className="occ-coach-detail__col-label">{coach.id} — Seat Map</div>
        <CoachSeatMap occupancy={coach.occupancy} />
        <DoorCongestionBar doorCongestion={coach.doorCongestion} />
      </div>

      {/* Right column — metrics + history */}
      <div className="occ-coach-detail__right">
        <div className="occ-coach-detail__col-label">Metrics</div>
        <div className="occ-coach-detail__stats">
          {/* Row 1 */}
          <div className="occ-coach-detail__stat">
            <span className="occ-coach-detail__stat-label">Head Count</span>
            <span className="occ-coach-detail__stat-value">{coach.headCount}</span>
          </div>
          <div className="occ-coach-detail__stat-divider occ-coach-detail__stat-divider--v" />
          <div className="occ-coach-detail__stat">
            <span className="occ-coach-detail__stat-label">Seated</span>
            <span className="occ-coach-detail__stat-value">{coach.seated}</span>
          </div>
          <div className="occ-coach-detail__stat-divider occ-coach-detail__stat-divider--v" />
          <div className="occ-coach-detail__stat">
            <span className="occ-coach-detail__stat-label">Standing</span>
            <span
              className="occ-coach-detail__stat-value"
              style={coach.standing > 0.4 * coach.headCount ? { color: 'var(--obb-sev-warning)' } : undefined}
            >{coach.standing}</span>
          </div>
          {/* Horizontal divider between rows */}
          <div className="occ-coach-detail__stat-divider occ-coach-detail__stat-divider--h" />
          {/* Row 2 */}
          <div className="occ-coach-detail__stat">
            <span className="occ-coach-detail__stat-label">Temperature</span>
            <span
              className="occ-coach-detail__stat-value"
              style={
                coach.tempC > 26 ? { color: 'var(--obb-sev-critical)' } :
                coach.tempC > 24 ? { color: 'var(--obb-sev-warning)' } : undefined
              }
            >{coach.tempC}°C</span>
          </div>
          <div className="occ-coach-detail__stat-divider occ-coach-detail__stat-divider--v" />
          <div className="occ-coach-detail__stat">
            <span className="occ-coach-detail__stat-label">Rack Util</span>
            <span className="occ-coach-detail__stat-value">{coach.rackUtil}%</span>
          </div>
          <div className="occ-coach-detail__stat-divider occ-coach-detail__stat-divider--v" />
          <div className="occ-coach-detail__stat">
            <span className="occ-coach-detail__stat-label">Dwell Contrib</span>
            <span
              className="occ-coach-detail__stat-value"
              style={{ color: dwellContrib ? 'var(--obb-sev-warning)' : 'var(--obb-sev-normal)' }}
            >{dwellContrib ? 'Active' : 'Normal'}</span>
          </div>
        </div>

      </div>
    </div>
  );
}

function DwellAlert({ dwell }) {
  return (
    <div className="occ-dwell-alert">
      <div className="occ-dwell-alert__icon">⏱</div>
      <div className="occ-dwell-alert__body">
        <div className="occ-dwell-alert__title">
          Dwelling at {dwell.station}
          {dwell.delayMin > 0 && (
            <span className="occ-dwell-alert__delay">+{dwell.delayMin} min delay</span>
          )}
        </div>
        <div className="occ-dwell-alert__meta">
          Sched dep {dwell.scheduledDep} · Dwelling since {dwell.dwellingSince}
          {dwell.platformCrowding && (
            <span className="occ-dwell-alert__crowding"> · Platform: {dwell.platformCrowding}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryStats({ train, threshold, fleetRank }) {
  const overCoaches = train.coaches.filter(c => c.occupancy >= threshold);
  const peakCoach = train.coaches.reduce(
    (best, c) => (c.occupancy > best.occupancy ? c : best),
    train.coaches[0]
  );

  const ordinal = (n) => {
    if (n === 1) return '1st';
    if (n === 2) return '2nd';
    if (n === 3) return '3rd';
    return `${n}th`;
  };

  return (
    <div className="occ-summary-stats">
      <div className="occ-stat">
        <span className="occ-stat__value" style={{ color: OCC_COLOR(peakCoach.occupancy) }}>
          {peakCoach.id}
        </span>
        <span className="occ-stat__label">Peak Coach ({peakCoach.occupancy}%)</span>
      </div>
      <div className="occ-stat-divider" />
      <div className="occ-stat">
        <span
          className="occ-stat__value"
          style={{ color: overCoaches.length > 0 ? 'var(--obb-sev-warning)' : '#22C55E' }}
        >
          {overCoaches.length}/{train.coaches.length}
        </span>
        <span className="occ-stat__label">Over {threshold}% Threshold</span>
      </div>
      <div className="occ-stat-divider" />
      <div className="occ-stat">
        <span className="occ-stat__value" style={{ color: 'var(--obb-text-on-dark-2)' }}>
          {ordinal(fleetRank)}
        </span>
        <span className="occ-stat__label">Fleet Rank by Occupancy</span>
      </div>
    </div>
  );
}

function DetailPanel({ train, threshold, fleetRank, escalationCount }) {
  const [selectedCoachId, setSelectedCoachId] = useState(
    () => train.coaches[0]?.id ?? null
  );

  // Reset to first coach whenever the train changes
  useEffect(() => {
    setSelectedCoachId(train.coaches[0]?.id ?? null);
  }, [train.id]);

  const selectedCoach = train.coaches.find(c => c.id === selectedCoachId) ?? null;
  const isDwellTrain = !!train.dwellStatus;

  function handleCoachClick(coachId) {
    setSelectedCoachId(prev => (prev === coachId ? null : coachId));
  }

  return (
    <div className="occ-detail">
      {/* Header */}
      <div className="occ-detail__header">
        <div className="occ-detail__header-left">
          <span
            className="occ-detail__sev-dot"
            style={{ background: SEV_COLOR[train.severity] }}
          />
          <span className="occ-detail__train-id">{train.id}</span>
          <span className="occ-detail__route">{train.route}</span>
        </div>
        <div className="occ-detail__header-badges">
          {escalationCount > 0 && (
            <span className="occ-badge occ-badge--esc">{escalationCount} escalation{escalationCount > 1 ? 's' : ''}</span>
          )}
          <span className={`occ-badge occ-badge--sev occ-badge--sev-${train.severity}`}>
            {train.severity.toUpperCase()}
          </span>
          <span className="occ-badge occ-badge--status" title="CCTV">
            CCTV <span className="occ-badge__dot" style={{ background: SEV_COLOR[train.cctvStatus] }} />
          </span>
          <span className="occ-badge occ-badge--status" title="App">
            App <span className="occ-badge__dot" style={{ background: SEV_COLOR[train.appStatus] }} />
          </span>
        </div>
      </div>

      {/* Dwell alert */}
      {train.dwellStatus && <DwellAlert dwell={train.dwellStatus} />}

      {/* Coach grid with flow lanes */}
      <div className="occ-detail__section-label">Coach Occupancy</div>
      <div className="occ-coach-grid">
        {train.coaches.map((c, i) => (
          <div key={c.id} className="occ-coach-col">
            <CoachCard
              coach={c}
              isSelected={selectedCoachId === c.id}
              onClick={() => handleCoachClick(c.id)}
            />
            {i < train.coaches.length - 1 && (
              <FlowLane
                leftOcc={c.occupancy}
                rightOcc={train.coaches[i + 1].occupancy}
              />
            )}
          </div>
        ))}
      </div>

      {/* Summary stats */}
      <SummaryStats train={train} threshold={threshold} fleetRank={fleetRank} />

      {/* Coach detail area */}
      {selectedCoach ? (
        <CoachDetailPanel
          key={selectedCoach.id}
          coach={selectedCoach}
          isDwellTrain={isDwellTrain}
        />
      ) : (
        <div className="occ-coach-detail__empty">
          Select a coach for details
        </div>
      )}
    </div>
  );
}

function EmptyDetail() {
  return (
    <div className="occ-detail occ-detail--empty">
      <span className="occ-detail__empty-msg">Select a train to view details</span>
    </div>
  );
}

// ─── Root component ───────────────────────────────────────────────────────────

export function OccupancyMonitoring() {
  const { fleet, kpis, escalations, lastUpdate, connected } = useFleetData();
  const [selectedTrainId, setSelectedTrainId] = useState(null);
  const [threshold, setThreshold] = useState(75);

  const sortedFleet = useMemo(
    () => [...fleet].sort((a, b) => b.avgOccupancy - a.avgOccupancy),
    [fleet]
  );

  // Auto-select highest-occupancy train on first load
  useEffect(() => {
    if (sortedFleet.length > 0 && !selectedTrainId) {
      setSelectedTrainId(sortedFleet[0].id);
    }
  }, [sortedFleet.length]);

  const overThreshold = useMemo(
    () => fleet.filter(t => t.avgOccupancy >= threshold).length,
    [fleet, threshold]
  );

  const escalationsByTrain = useMemo(() => {
    const map = {};
    for (const e of escalations) {
      if (e.status !== 'resolved') {
        map[e.trainId] = (map[e.trainId] ?? 0) + 1;
      }
    }
    return map;
  }, [escalations]);

  const selectedTrain = fleet.find(t => t.id === selectedTrainId) ?? null;
  const fleetRank = selectedTrain
    ? sortedFleet.findIndex(t => t.id === selectedTrainId) + 1
    : 1;

  if (!connected) {
    return (
      <div className="occ-monitoring occ-monitoring--loading">
        <div className="occ-monitoring__loading-msg">Connecting to fleet data…</div>
      </div>
    );
  }

  return (
    <div className="occ-monitoring">
      {/* KPI strip */}
      <OccKpiStrip
        fleet={fleet}
        overThreshold={overThreshold}
        threshold={threshold}
        lastUpdate={lastUpdate}
      />

      {/* Body: left list + right detail */}
      <div className="occ-body">
        {/* Left panel */}
        <div className="occ-left">
          <div className="occ-left__header">
            <span className="occ-left__title">Fleet</span>
            <span className="occ-left__count">{fleet.length}</span>
          </div>
          <div className="occ-left__list">
            {sortedFleet.map(train => (
              <TrainListItem
                key={train.id}
                train={train}
                threshold={threshold}
                escalationCount={escalationsByTrain[train.id] ?? 0}
                isSelected={selectedTrainId === train.id}
                onSelect={setSelectedTrainId}
              />
            ))}
          </div>
        </div>

        {/* Right panel */}
        <div className="occ-right">
          {selectedTrain ? (
            <DetailPanel
              train={selectedTrain}
              threshold={threshold}
              fleetRank={fleetRank}
              escalationCount={escalationsByTrain[selectedTrain.id] ?? 0}
            />
          ) : (
            <EmptyDetail />
          )}

          {/* Threshold control — anchored to bottom of right panel */}
          <div className="occ-threshold-bar">
            <label className="occ-threshold-bar__label" htmlFor="occ-threshold-slider">
              Alert Threshold
            </label>
            <input
              id="occ-threshold-slider"
              type="range"
              min={50} max={95} step={5}
              value={threshold}
              onChange={e => setThreshold(Number(e.target.value))}
              className="occ-threshold-bar__slider"
            />
            <span
              className="occ-threshold-bar__value"
              style={{ color: OCC_COLOR(threshold) }}
            >
              {threshold}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
