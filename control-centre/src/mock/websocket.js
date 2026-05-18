/**
 * Mock WebSocket server — emits realistic event payloads matching ADR-9 subscription contract.
 * Drop-in: replace MockWebSocketClient with real WebSocket when cloud backend is ready.
 */

const TRAINS = [
  { id: 'R5001C-031', route: 'Wien Hbf → Salzburg', coaches: 8 },
  { id: 'R5001C-022', route: 'Salzburg → Wien Hbf', coaches: 8 },
  { id: 'R5001C-017', route: 'Wien Hbf → Linz Hbf', coaches: 6 },
  { id: 'R5001C-008', route: 'Linz Hbf → Graz Hbf', coaches: 6 },
  { id: 'R5001C-044', route: 'Graz Hbf → Wien Hbf', coaches: 8 },
  { id: 'R5001C-055', route: 'Wien Hbf → Innsbruck Hbf', coaches: 8 },
  { id: 'R5001C-012', route: 'Innsbruck Hbf → Wien Hbf', coaches: 6 },
  { id: 'R5001C-003', route: 'Wien Hbf → Klagenfurt', coaches: 6 },
];

function randomOccupancy(base, variance = 15) {
  return Math.min(100, Math.max(0, base + Math.floor((Math.random() - 0.5) * variance * 2)));
}

function generateCoachMetrics(occupancy, isDwell) {
  const headCount = Math.round(occupancy * 0.8);
  const seated = Math.round(
    headCount * (occupancy < 70 ? 0.85 : occupancy < 85 ? 0.65 : 0.45)
  );
  const standing = headCount - seated;
  const doorCongestion = Math.min(
    100,
    Math.max(
      0,
      occupancy >= 80
        ? randomOccupancy(occupancy - 20, 15)
        : randomOccupancy(15, 10)
    )
  );
  const tempC = parseFloat(
    (20 + (occupancy / 100) * 6 + (Math.random() - 0.5) * 1.5).toFixed(1)
  );
  const rackUtil = Math.min(100, Math.round(occupancy * 0.6 + Math.random() * 20));
  return { headCount, seated, standing, doorCongestion, tempC, rackUtil, hasFall: false };
}

// R5001C-044 is dwelling at Bruck an der Mur — stopped 4 min behind schedule
const DWELL_TRAIN = 'R5001C-044';
const DWELL_STATUS = {
  station: 'Bruck an der Mur',
  scheduledDep: '11:14',
  actualDep: null,       // null = still stopped
  delayMin: 4,
  dwellingSince: '11:10',
  platformCrowding: 'high',
};

function generateFleetState() {
  return TRAINS.map((train, i) => {
    const isDwell = train.id === DWELL_TRAIN;

    const coaches = Array.from({ length: train.coaches }, (_, j) => {
      const occupancy = isDwell
        ? randomOccupancy([91, 88, 62, 74, 71, 58, 86, 93][j], 4)
        : randomOccupancy(30 + i * 5 + j * 3);
      const metrics = generateCoachMetrics(occupancy, isDwell);
      if (i === 0 && j === 3) metrics.hasFall = true;
      return {
        id: `C${j + 1}`,
        // Dwell train: passengers boarding at Bruck an der Mur.
        // C1/C2 and C7/C8 are door-adjacent — highest boarding.
        // C4/C5 middle get some direct boarders. C3/C6 lowest.
        occupancy,
        hasAlert: i === 0 && j === 3,
        ...metrics,
      };
    });

    const maxOcc = Math.max(...coaches.map(c => c.occupancy));
    const severity =
      i === 0 ? 'red' :
      i === 1 ? 'amber' :
      isDwell ? 'amber' :
      maxOcc >= 85 ? 'amber' :
      'green';

    // R5001C-008 (i=3): 2 CCTV devices unreachable — power/network failure in C3 & C5
    const deviceStatus =
      i === 3 ? 'red' :
      i === 1 ? 'amber' :
      'green';

    const deviceDetail =
      i === 3 ? { total: 6, unreachable: 2, coaches: ['C3', 'C5'], reason: 'No response — power or network failure suspected' } :
      i === 1 ? { total: 8, unreachable: 1, coaches: ['C6'], reason: 'Intermittent — packet loss on VLAN 5' } :
      null;

    // Per-container app detail — R5001C-031 (i=0): inference exited; R5001C-022 (i=1): fusion degraded
    const APP_CONTAINERS = ['rtsp-ingest', 'vlan-pollers', 'inference', 'fusion', 'event-store'];
    const appDetail =
      i === 0 ? APP_CONTAINERS.map(name => ({
        name,
        status: name === 'inference' ? 'red' : 'green',
        note: name === 'inference' ? 'exited · OOM at 09:43' : 'healthy',
      })) :
      i === 1 ? APP_CONTAINERS.map(name => ({
        name,
        status: name === 'fusion' ? 'amber' : 'green',
        note: name === 'fusion' ? 'high latency · 420ms avg' : 'healthy',
      })) :
      null;

    // Connectivity status per train — models cellular/WiFi link to landside
    const connectivity =
      i === 3 ? { status: 'degraded', transport: 'LTE',  signalDbm: -98, lastSeen: '11:29', latencyMs: 840,  note: 'Intermittent LTE — signal weak in Semmering tunnel section' } :
      i === 1 ? { status: 'degraded', transport: 'LTE',  signalDbm: -91, lastSeen: '11:33', latencyMs: 310,  note: 'Elevated latency — approaching Bruck an der Mur coverage gap' } :
      i === 0 ? { status: 'ok',       transport: 'LTE',  signalDbm: -72, lastSeen: '11:35', latencyMs:  88,  note: null } :
               { status: 'ok',       transport: 'LTE',  signalDbm: -68, lastSeen: '11:35', latencyMs:  65,  note: null };

    return {
      id: train.id,
      route: train.route,
      severity: i === 3 ? 'red' : severity,
      avgOccupancy: Math.round(coaches.reduce((s, c) => s + c.occupancy, 0) / coaches.length),
      coaches,
      cctvStatus: i === 1 ? 'amber' : 'green',
      appStatus: i === 0 ? 'red' : i === 1 ? 'amber' : 'green',
      deviceStatus,
      deviceDetail,
      appDetail,
      connectivity,
      lastHealthy: i === 0 ? '09:43' : i === 3 ? '10:51' : null,
      dwellStatus: isDwell ? DWELL_STATUS : null,
    };
  });
}

function generateEscalations() {
  return [
    // AI — door obstruction (replaces duplicate unattended bag; luggage events cover unattended bags)
    {
      id: 'esc-001',
      type: 'ai',
      trainId: 'R5001C-031',
      coachId: 'C3',
      title: 'Door obstruction — Coach C3',
      detail: 'Passenger detected blocking door during closing sequence. Confidence: 96%.',
      severity: 'red',
      status: 'unacknowledged',
      timestamp: '11:24',
      stillFrame: {
        url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C3+door+cam+%E2%80%94+11%3A24%3A07',
        capturedAt: '11:24:07',
        camera: 'C3-door-L1',
        confidence: 96,
      },
    },
    // Occupancy — overcrowding escalation R5001C-003 C5
    {
      id: 'esc-005',
      type: 'occupancy',
      trainId: 'R5001C-003',
      coachId: 'C5',
      title: 'Overcrowding — Coach C5',
      detail: 'Occupancy exceeded 90% for over 5 minutes. Standing passengers in vestibule. Confidence: 91%.',
      severity: 'red',
      status: 'unacknowledged',
      timestamp: '11:09',
      stillFrame: {
        url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C5+overhead+%E2%80%94+11%3A09%3A14',
        capturedAt: '11:09:14',
        camera: 'C5-overhead',
        confidence: 91,
      },
    },
    // Occupancy — overcrowding escalation R5001C-044 (dwell train boarding surge)
    {
      id: 'esc-006',
      type: 'occupancy',
      trainId: 'R5001C-044',
      coachId: 'C1',
      title: 'Overcrowding — Coach C1',
      detail: 'Boarding surge at Bruck an der Mur. Coach C1 at 93% and rising. Confidence: 88%.',
      severity: 'red',
      status: 'unacknowledged',
      timestamp: '11:12',
      stillFrame: {
        url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C1+overhead+%E2%80%94+11%3A12%3A00',
        capturedAt: '11:12:00',
        camera: 'C1-overhead',
        confidence: 88,
      },
    },
    // Conrad — capacity flag
    {
      id: 'esc-002',
      type: 'conductor',
      trainId: 'R5001C-017',
      coachId: null,
      title: 'Capacity flag · Conrad',
      detail: 'Coaches 3–4 consistently overcrowded. Third consecutive Friday.',
      severity: 'amber',
      status: 'acknowledged',
      timestamp: '10:47',
      stillFrame: {
        url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=R5001C-017+C3+%E2%80%94+10%3A47%3A11',
        capturedAt: '10:47:11',
        camera: 'C3-overhead',
        confidence: 81,
      },
    },
    // Roland — CCTV degraded
    {
      id: 'esc-003',
      type: 'roland',
      trainId: 'R5001C-022',
      coachId: null,
      title: 'Technical note · Roland',
      detail: 'CCTV stream degraded — investigating VLAN 5 packet loss.',
      severity: 'amber',
      status: 'acknowledged',
      timestamp: '09:58',
      stillFrame: {
        url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=R5001C-022+cam+%E2%80%94+09%3A58%3A33',
        capturedAt: '09:58:33',
        camera: 'C1-forward',
        confidence: 76,
      },
    },
    // Conrad — extended dwell
    {
      id: 'esc-004',
      type: 'conductor',
      trainId: 'R5001C-044',
      coachId: null,
      title: 'Extended dwell · Bruck an der Mur',
      detail: 'Stopped at Bruck an der Mur since 11:10 — now 4 min behind schedule. High platform crowding, all coaches boarding. Requesting dispatch guidance.',
      severity: 'amber',
      status: 'unacknowledged',
      timestamp: '11:14',
      stillFrame: {
        url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=R5001C-044+platform+%E2%80%94+11%3A14%3A00',
        capturedAt: '11:14:00',
        camera: 'C1-door-cam',
        confidence: 79,
      },
    },
  ];
}

function generateKPIs(fleet) {
  const escalations = generateEscalations();
  return {
    activeTrains: fleet.length,
    avgOccupancy: Math.round(fleet.reduce((s, t) => s + t.avgOccupancy, 0) / fleet.length),
    openIncidents: fleet.filter(t => t.severity === 'red').length,
    openEscalations: escalations.filter(e => e.status !== 'resolved').length,
    // capacityAlerts: trains currently exceeding configured occupancy threshold (85%)
    capacityAlerts: fleet.filter(t => t.avgOccupancy >= 85).length,
  };
}

export class MockWebSocketClient {
  constructor(onMessage, onStatusChange) {
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange ?? (() => {});
    this.interval = null;
    this.connected = false;
  }

  connect() {
    this.connected = true;
    // VITE_MOCK_WS_DELAY_MS overrides the default 300ms — used by E2E tests to hold
    // the skeleton state long enough for assertions to run.
    const delay = parseInt(import.meta.env.VITE_MOCK_WS_DELAY_MS || '300', 10);
    setTimeout(() => {
      if (this.connected) {
        this.onStatusChange('connected');
        this._emit();
      }
    }, delay);
  }

  disconnect() {
    this.connected = false;
    if (this.interval) clearInterval(this.interval);
    this.onStatusChange('disconnected');
  }

  _emit() {
    const fleet = generateFleetState();
    this.onMessage({
      type: 'FLEET_STATE',
      payload: {
        fleet,
        kpis: generateKPIs(fleet),
        escalations: generateEscalations(),
        timestamp: new Date().toISOString(),
      },
    });

    // Emit mock luggage events so the Luggage tab is testable in dev mode
    setTimeout(() => {
      if (this.connected) {
        this.onMessage({
          type: 'LUGGAGE_EVENT',
          payload: {
            id: 'mock-lug-001',
            trainId: 'R5001C-031',
            coachId: 'car-4',
            state: 'unattended',
            title: 'Unattended bag — car-4 seating-mid',
            detail: 'No owner detected for 3 min. Track: bag-0042.',
            confidence: 0.94,
            timestamp: new Date().toISOString(),
            stillFrame: null,
          },
        });
      }
    }, 500);

    setTimeout(() => {
      if (this.connected) {
        this.onMessage({
          type: 'LUGGAGE_EVENT',
          payload: {
            id: 'mock-lug-002',
            trainId: 'R5001C-003',
            coachId: 'car-2',
            state: 'overcrowded',
            title: 'Luggage area full — car-2',
            detail: 'Rack car-2-rack-upper-left at 95% capacity. 7 items detected.',
            confidence: 0.88,
            timestamp: new Date().toISOString(),
            stillFrame: null,
          },
        });
      }
    }, 1200);
  }

  // Simulate acknowledging an escalation
  acknowledge(escalationId) {
    this.onMessage({
      type: 'ESCALATION_UPDATED',
      payload: { id: escalationId, status: 'acknowledged', acknowledgedAt: new Date().toISOString() },
    });
  }

  // Simulate resolving an escalation
  resolve(escalationId, outcome) {
    this.onMessage({
      type: 'ESCALATION_UPDATED',
      payload: { id: escalationId, status: 'resolved', outcome, resolvedAt: new Date().toISOString() },
    });
  }
}
