import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import { getSystemHealth } from '../../api/health';
import './SystemHealth.css';

const SEV_CLASS = { green: 'badge--green', amber: 'badge--amber', red: 'badge--red' };
const SEV_ORDER = { red: 0, amber: 1, green: 2 };

const worstOf = t => {
  const statuses = [t.cctvStatus, t.appStatus, t.deviceStatus ?? 'green'];
  if (statuses.includes('red')) return 'red';
  if (statuses.includes('amber')) return 'amber';
  return 'green';
};

const VALID_CCTV_STATUS = new Set(['green', 'amber', 'red']);

function elapsedLabel(isoString) {
  if (!isoString) return null;
  const diffMs = Date.now() - Date.parse(isoString);
  if (Number.isNaN(diffMs) || diffMs < 0) return 'just now';
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

function formatTime(isoString) {
  if (!isoString) return null;
  const ts = Date.parse(isoString);
  if (Number.isNaN(ts)) return isoString; // already formatted (e.g. "11:35")
  return new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}

function SystemHealthSkeleton() {
  return (
    <div className="system-health" data-testid="system-health-skeleton">
      <div className="sh-summary-strip">
        <div className="sh-summary-tile">
          <span className="skeleton-pulse" style={{ display: 'block', width: '60px', height: '16px' }} />
          <span className="skeleton-pulse" style={{ display: 'block', width: '100px', height: '10px', marginTop: '4px' }} />
        </div>
        <div className="sh-summary-tile">
          <span className="skeleton-pulse" style={{ display: 'block', width: '140px', height: '16px' }} />
          <span className="skeleton-pulse" style={{ display: 'block', width: '80px', height: '10px', marginTop: '4px' }} />
        </div>
      </div>
      <div className="sh-grid">
        <div className="sh-grid__header">
          <span className="sh-grid__col sh-grid__col--sev" />
          <span className="sh-grid__col sh-grid__col--train">Train</span>
          <span className="sh-grid__col">CCTV Streams</span>
          <span className="sh-grid__col">CCTV Devices</span>
          <span className="sh-grid__col">Applications</span>
          <span className="sh-grid__col sh-grid__col--since">Since</span>
        </div>
        {[0, 1, 2].map(i => (
          <div key={i} className="sh-grid__row" style={{ cursor: 'default' }}>
            <span className="sh-grid__col sh-grid__col--sev">
              <span className="skeleton-pulse" style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%' }} />
            </span>
            <span className="sh-grid__col sh-grid__col--train">
              <span className="skeleton-pulse" style={{ display: 'inline-block', width: '100px', height: '13px' }} />
            </span>
            <span className="sh-grid__col">
              <span className="skeleton-pulse" style={{ display: 'inline-block', width: '70px', height: '13px' }} />
            </span>
            <span className="sh-grid__col">
              <span className="skeleton-pulse" style={{ display: 'inline-block', width: '70px', height: '13px' }} />
            </span>
            <span className="sh-grid__col">
              <span className="skeleton-pulse" style={{ display: 'inline-block', width: '70px', height: '13px' }} />
            </span>
            <span className="sh-grid__col sh-grid__col--since">
              <span className="skeleton-pulse" style={{ display: 'inline-block', width: '30px', height: '13px' }} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SystemHealth() {
  const { fleet, lastUpdate, stalenessThresholdSeconds } = useFleetData();
  const [healthData, setHealthData] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(null);
  const [selectedTrainId, setSelectedTrainId] = useState(null);
  const [ticketRaisedIds, setTicketRaisedIds] = useState(new Set());
  const [ticketRefs, setTicketRefs] = useState({});
  const [ticketPending, setTicketPending] = useState(null);
  const [ticketToast, setTicketToast] = useState(null);
  const [tick, setTick] = useState(0);
  const firstIssueRef = useRef(null);
  const toastTimerRef = useRef(null);

  const fetchGenRef = useRef(0);

  const fetchHealth = useCallback(() => {
    const gen = ++fetchGenRef.current;
    setHealthLoading(true);
    setHealthError(null);
    setSelectedTrainId(null);
    const ctrl = new AbortController();
    getSystemHealth(ctrl.signal)
      .then(data => {
        if (fetchGenRef.current !== gen) return;
        setHealthData(data);
        setHealthLoading(false);
      })
      .catch(err => {
        if (fetchGenRef.current !== gen || err.name === 'AbortError') return;
        setHealthError(err);
        setHealthLoading(false);
      });
    return ctrl;
  }, []);

  useEffect(() => {
    const ctrl = fetchHealth();
    return () => ctrl?.abort();
  }, [fetchHealth]);

  // Live-tick every second — drives elapsed labels + staleness detection
  useEffect(() => {
    const id = setInterval(() => setTick(v => v + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // ESC — cancel pending ticket confirm first, then close panel
  useEffect(() => {
    const handler = (e) => {
      if (e.key !== 'Escape') return;
      if (ticketPending) { setTicketPending(null); return; }
      setSelectedTrainId(null);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [ticketPending]);

  // Merge WS cctvStatus patches into healthData.
  // Runs on every fleet reference change (CAMERA_DEGRADED/RECOVERED sets a new array).
  // Uses setter form so it always operates on current state, not a stale closure.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!fleet.length) return;
    setHealthData(prev => {
      if (!prev || !Array.isArray(prev.trains)) return prev;
      const patchedTrains = prev.trains.map(ht => {
        const wsEntry = fleet.find(t => t.id === ht.id);
        const incoming = wsEntry?.cctvStatus;
        if (!incoming || !VALID_CCTV_STATUS.has(incoming) || incoming === ht.cctvStatus) return ht;
        return { ...ht, cctvStatus: incoming };
      });
      const changed = patchedTrains.some((t, i) => t !== prev.trains[i]);
      return changed ? { ...prev, trains: patchedTrains } : prev;
    });
  }, [fleet]);

  const confirmRaiseTicket = useCallback((trainId) => {
    const ref = `REF#${Math.floor(10000 + Math.random() * 90000)}`;
    setTicketRaisedIds(prev => new Set([...prev, trainId]));
    setTicketRefs(prev => ({ ...prev, [trainId]: ref }));
    setTicketPending(null);
    setTicketToast({ trainId, ref });
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setTicketToast(null), 4000);
  }, []);

  useEffect(() => () => clearTimeout(toastTimerRef.current), []);

  const lastUpdateLabel = useMemo(() => {
    if (!lastUpdate) return '—';
    const s = Math.floor((Date.now() - lastUpdate.getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ${s % 60}s ago`;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastUpdate, tick]);

  const isStale = useMemo(() => {
    if (!lastUpdate) return false;
    return (Date.now() - lastUpdate.getTime()) > stalenessThresholdSeconds * 1000;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastUpdate, stalenessThresholdSeconds, tick]);

  if (healthLoading) return <SystemHealthSkeleton />;

  if (healthError) {
    return (
      <div className="system-health">
        <div className="sh-summary-strip">
          <div className="sh-summary-tile">
            <span className="sh-summary-tile__value">—</span>
            <span className="sh-summary-tile__label">trains monitored</span>
          </div>
          <div className="sh-summary-tile">
            <span className="sh-summary-tile__value">—</span>
            <span className="sh-summary-tile__label">fleet status</span>
          </div>
        </div>
        <div className="sh-error-state">
          <p>System health data unavailable</p>
          <button className="btn btn--secondary" onClick={fetchHealth}>Retry</button>
        </div>
      </div>
    );
  }

  const trains = healthData?.trains ?? [];
  const sorted = [...trains].sort((a, b) => SEV_ORDER[worstOf(a)] - SEV_ORDER[worstOf(b)]);
  const issueTrains = sorted.filter(t => worstOf(t) !== 'green');
  const issueCount = issueTrains.length;
  const worstFleet = issueTrains.length > 0 ? worstOf(issueTrains[0]) : 'green';
  const selectedTrain = trains.find(t => t.id === selectedTrainId) ?? null;

  const handleIssueTileClick = () => {
    if (issueCount === 0) return;
    const first = issueTrains[0];
    setSelectedTrainId(first.id);
    requestAnimationFrame(() => {
      firstIssueRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  };

  const renderAppContainers = (train) => {
    if (!train.appDetail || train.appStatus === 'green') return null;
    return (
      <div className="sh-panel__container-list">
        {train.appDetail.map(c => (
          <div key={c.name} className={`sh-panel__container-row${c.status !== 'green' ? ' sh-panel__container-row--unhealthy' : ''}`}>
            <span className="sh-panel__container-name">{c.name}</span>
            <span className={`badge ${SEV_CLASS[c.status]}`}>{c.note}</span>
          </div>
        ))}
      </div>
    );
  };

  const appHealthyCount = (train) =>
    (train.appDetail ?? []).filter(c => c.status === 'green').length;
  const appTotal = (train) => train.appDetail?.length ?? 5;

  const renderFooter = (train) => {
    if (worstOf(train) === 'green') return null;
    const trainId = train.id;
    const raised = ticketRaisedIds.has(trainId);
    const ref = ticketRefs[trainId];
    const isPending = ticketPending === trainId;

    if (raised) {
      return (
        <div className="sh-panel__footer">
          <div className="sh-panel__ticket-raised">
            <span className="sh-panel__ticket-icon">✓</span>
            Ticket raised
            <span className="sh-panel__ticket-ref">{ref}</span>
          </div>
        </div>
      );
    }

    if (isPending) {
      return (
        <div className="sh-panel__footer sh-panel__footer--confirm">
          <span className="sh-panel__confirm-label">Raise a maintenance ticket for {trainId}?</span>
          <div className="sh-panel__confirm-actions">
            <button
              className="btn btn--primary sh-panel__confirm-yes"
              onClick={() => confirmRaiseTicket(trainId)}
            >
              Confirm
            </button>
            <button
              className="btn btn--ghost"
              onClick={() => setTicketPending(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="sh-panel__footer">
        <button
          className="btn btn--secondary sh-panel__ticket-btn"
          onClick={() => setTicketPending(trainId)}
        >
          Raise Maintenance Ticket
        </button>
      </div>
    );
  };

  return (
    <div className="system-health">
      {/* Summary strip */}
      <div className="sh-summary-strip">
        <div className="sh-summary-tile">
          <span className="sh-summary-tile__value">{trains.length}</span>
          <span className="sh-summary-tile__label">trains monitored</span>
        </div>
        <div
          className={`sh-summary-tile ${issueCount > 0 ? `sh-summary-tile--issues sh-summary-tile--issues-${worstFleet} sh-summary-tile--clickable` : ''}`}
          onClick={handleIssueTileClick}
          title={issueCount > 0 ? 'Click to jump to first issue' : ''}
        >
          <span className="sh-summary-tile__value">
            {issueCount > 0 ? `${issueCount} train${issueCount !== 1 ? 's' : ''} with issues` : 'All systems healthy'}
          </span>
          <span className="sh-summary-tile__label sh-summary-tile__label--fixed">
            {issueCount > 0 ? 'click to jump' : 'fleet status'}
          </span>
        </div>
        <div className={`sh-summary-tile sh-summary-tile--refresh${isStale ? ' sh-summary-tile--stale' : ''}`}>
          <span className={`sh-summary-tile__value sh-summary-tile__value--sm${isStale ? ' sh-summary-tile__value--stale' : ''}`}>
            {lastUpdateLabel}{isStale ? ' — reconnecting…' : ''}
          </span>
          <span className="sh-summary-tile__label">last update</span>
        </div>
      </div>

      {/* Body: grid + inline side-panel */}
      <div className="sh-body">
        <div className="sh-grid">
          <div className="sh-grid__header">
            <span className="sh-grid__col sh-grid__col--sev" />
            <span className="sh-grid__col sh-grid__col--train">Train</span>
            <span className="sh-grid__col">CCTV Streams</span>
            <span className="sh-grid__col">CCTV Devices</span>
            <span className="sh-grid__col">Applications</span>
            <span className="sh-grid__col sh-grid__col--since">Since</span>
          </div>
          {sorted.map((train, idx) => {
            const sev = worstOf(train);
            const elapsed = elapsedLabel(train.last_healthy);
            const isFirst = idx === 0 && sev !== 'green';
            const ticketRaised = ticketRaisedIds.has(train.id);
            return (
              <button
                key={train.id}
                ref={isFirst ? firstIssueRef : null}
                className={[
                  'sh-grid__row',
                  `sh-grid__row--sev-${sev}`,
                  selectedTrainId === train.id ? 'sh-grid__row--selected' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => setSelectedTrainId(selectedTrainId === train.id ? null : train.id)}
              >
                <span className="sh-grid__col sh-grid__col--sev">
                  <span className={`sh-sev-dot sh-sev-dot--${sev}`} />
                </span>
                <span className="sh-grid__col sh-grid__col--train">
                  {train.id}
                  {ticketRaised && (
                    <span className="sh-ticket-chip" title={`Ticket: ${ticketRefs[train.id]}`}>
                      Ticket raised
                    </span>
                  )}
                </span>
                <span className="sh-grid__col">
                  <span className={`badge ${SEV_CLASS[train.cctvStatus]}`}>
                    {train.cctvStatus === 'green' ? '● Healthy' : train.cctvStatus === 'amber' ? '● Degraded' : '● Failed'}
                  </span>
                </span>
                <span className="sh-grid__col">
                  <span className={`badge ${SEV_CLASS[train.deviceStatus ?? 'green']}`}>
                    {train.deviceStatus === 'red' ? '● Device not found' : train.deviceStatus === 'amber' ? '● Intermittent' : '● All reachable'}
                  </span>
                </span>
                <span className="sh-grid__col">
                  <span className={`badge ${SEV_CLASS[train.appStatus]}`}>
                    {train.appStatus === 'green' ? '● Healthy' : train.appStatus === 'amber' ? '● Degraded' : '● Unhealthy'}
                  </span>
                </span>
                <span className="sh-grid__col sh-grid__col--since">
                  {train.last_healthy
                    ? <span className={`sh-since sh-since--${sev}`} title={`Since ${train.last_healthy}`}>
                        {elapsed ? `${elapsed} ago` : `since ${formatTime(train.last_healthy)}`}
                      </span>
                    : <span className="sh-since sh-since--ok" title="No fault recorded this session">—</span>}
                </span>
              </button>
            );
          })}
        </div>

        {/* Inline side panel */}
        {selectedTrain && (
          <div className="sh-panel">
            <div className="sh-panel__header">
              <div className="sh-panel__header-left">
                <span className={`sh-sev-dot sh-sev-dot--${worstOf(selectedTrain)}`} />
                <h2 className="sh-panel__train-id">{selectedTrain.id}</h2>
              </div>
              <button className="sh-panel__close" onClick={() => setSelectedTrainId(null)} aria-label="Close detail panel">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>

            <div className="sh-panel__body">

              {/* Train Link — always rendered */}
              <div className="sh-panel__row">
                <span className="sh-panel__label">Train Link</span>
                {selectedTrain.connectivity ? (() => {
                  const c = selectedTrain.connectivity;
                  const isDegraded = c.status === 'degraded';
                  const lastSeenFormatted = formatTime(c.lastSeen);
                  const lastSeenElapsed = elapsedLabel(c.lastSeen);
                  return (
                    <div className="sh-conn__inline">
                      <span className={`sh-conn__status-badge${isDegraded ? ' sh-conn__status-badge--degraded' : ''}`}>
                        {isDegraded ? '⚠ Degraded' : '● Connected'}
                      </span>
                      <span className="sh-conn__lastseen">
                        {lastSeenFormatted}{lastSeenElapsed ? ` · ${lastSeenElapsed} ago` : ''}
                      </span>
                    </div>
                  );
                })() : (
                  <span className="sh-conn__unknown">No data</span>
                )}
              </div>

              {/* CCTV Streams */}
              <div className="sh-panel__row">
                <span className="sh-panel__label">CCTV Streams</span>
                <span className={`badge ${SEV_CLASS[selectedTrain.cctvStatus]}`}>
                  {selectedTrain.cctvStatus === 'green' ? 'All streams reachable'
                   : selectedTrain.cctvStatus === 'amber' ? 'Degraded · packet loss'
                   : 'Unreachable'}
                </span>
              </div>

              {/* CCTV Devices */}
              <div className="sh-panel__row">
                <span className="sh-panel__label">CCTV Devices</span>
                <span className={`badge ${SEV_CLASS[selectedTrain.deviceStatus ?? 'green']}`}>
                  {selectedTrain.deviceStatus === 'red'
                    ? `${selectedTrain.deviceDetail?.unreachable} of ${selectedTrain.deviceDetail?.total} not found`
                    : selectedTrain.deviceStatus === 'amber'
                    ? `${selectedTrain.deviceDetail?.unreachable} of ${selectedTrain.deviceDetail?.total} intermittent`
                    : 'All devices reachable'}
                </span>
              </div>
              {selectedTrain.deviceStatus !== 'green' && selectedTrain.deviceDetail && (
                <div className="sh-panel__container-list">
                  {selectedTrain.deviceDetail.coaches.map(coach => (
                    <div key={coach} className="sh-panel__container-row sh-panel__container-row--unhealthy">
                      <span className="sh-panel__container-name">Camera · {coach}</span>
                      <span className={`badge ${selectedTrain.deviceStatus === 'red' ? 'badge--red' : 'badge--amber'}`}>
                        {selectedTrain.deviceStatus === 'red' ? 'Not found' : 'Intermittent'}
                      </span>
                    </div>
                  ))}
                  <div className="sh-panel__device-reason">{selectedTrain.deviceDetail.reason}</div>
                </div>
              )}

              {/* Applications */}
              <div className="sh-panel__row">
                <span className="sh-panel__label">Applications</span>
                <span className={`badge ${SEV_CLASS[selectedTrain.appStatus]}`}>
                  {selectedTrain.appStatus === 'green'
                    ? `${appTotal(selectedTrain)} of ${appTotal(selectedTrain)} healthy`
                    : selectedTrain.appStatus === 'red'
                    ? `${appHealthyCount(selectedTrain)} of ${appTotal(selectedTrain)} healthy`
                    : `Degraded · ${appTotal(selectedTrain) - appHealthyCount(selectedTrain)} container${appTotal(selectedTrain) - appHealthyCount(selectedTrain) !== 1 ? 's' : ''}`}
                </span>
              </div>
              {renderAppContainers(selectedTrain)}

              {/* Fault timestamp */}
              {selectedTrain.last_healthy && (
                <div className="sh-panel__timestamp">
                  Last fully healthy: {formatTime(selectedTrain.last_healthy)} today
                  {elapsedLabel(selectedTrain.last_healthy) && (
                    <span className="sh-panel__elapsed"> · {elapsedLabel(selectedTrain.last_healthy)} ago</span>
                  )}
                </div>
              )}

            </div>

            {renderFooter(selectedTrain)}
          </div>
        )}
      </div>

      {ticketToast && (
        <div className="sh-toast">
          Ticket raised — {ticketToast.ref} · {ticketToast.trainId}
        </div>
      )}
    </div>
  );
}
