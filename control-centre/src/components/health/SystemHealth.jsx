import { useState, useEffect, useCallback, useRef } from 'react';
import { useFleetData } from '../../hooks/useFleetData';
import './SystemHealth.css';

const SEV_CLASS = { green: 'badge--green', amber: 'badge--amber', red: 'badge--red' };
const SEV_ORDER = { red: 0, amber: 1, green: 2 };

const worstOf = t => {
  const statuses = [t.cctvStatus, t.appStatus, t.deviceStatus ?? 'green'];
  if (statuses.includes('red')) return 'red';
  if (statuses.includes('amber')) return 'amber';
  return 'green';
};

// Parse "HH:MM" → minutes since midnight
function toMin(ts) {
  if (!ts) return null;
  const [h, m] = ts.split(':').map(Number);
  return h * 60 + m;
}

// Current wall-clock as "HH:MM"
// TODO: in production this comes from the server time or Date.now() directly —
// mock timestamps in the data are anchored to ~11:35 scenario time.
// For the demo we derive "now" from actual wall-clock so elapsed is always correct.
function nowHHMM() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function elapsedLabel(ts) {
  const ref = toMin(nowHHMM());
  const t = toMin(ts);
  if (ref == null || t == null) return null;
  // Handle overnight wrap (e.g. now=00:05, ts=23:55)
  let diff = ref - t;
  if (diff < 0) diff += 24 * 60;
  if (diff < 1) return 'just now';
  if (diff < 60) return `${diff}m`;
  return `${Math.floor(diff / 60)}h ${diff % 60}m`;
}

export function SystemHealth() {
  const { fleet, lastUpdate } = useFleetData();
  const [selectedTrainId, setSelectedTrainId] = useState(null);
  const [ticketRaisedIds, setTicketRaisedIds] = useState(new Set());
  const [ticketRefs, setTicketRefs] = useState({});       // trainId → ref string
  const [ticketPending, setTicketPending] = useState(null); // trainId awaiting confirm
  const [ticketToast, setTicketToast] = useState(null);
  const [tick, setTick] = useState(0);
  const firstIssueRef = useRef(null);

  // Live-tick every second — drives last-update counter + elapsed labels
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

  const confirmRaiseTicket = useCallback((trainId) => {
    const ref = `REF#${Math.floor(10000 + Math.random() * 90000)}`;
    setTicketRaisedIds(prev => new Set([...prev, trainId]));
    setTicketRefs(prev => ({ ...prev, [trainId]: ref }));
    setTicketPending(null);
    setTicketToast({ trainId, ref });
    setTimeout(() => setTicketToast(null), 4000);
  }, []);

  const sorted = [...fleet].sort((a, b) => SEV_ORDER[worstOf(a)] - SEV_ORDER[worstOf(b)]);
  const issueTrains = sorted.filter(t => worstOf(t) !== 'green');
  const issueCount = issueTrains.length;
  const worstFleet = issueTrains.length > 0 ? worstOf(issueTrains[0]) : 'green';
  const selectedTrain = fleet.find(t => t.id === selectedTrainId) ?? null;

  // Force re-read of lastUpdate every tick
  void tick;
  const lastUpdateLabel = lastUpdate
    ? (() => {
        const s = Math.floor((Date.now() - lastUpdate.getTime()) / 1000);
        if (s < 60) return `${s}s ago`;
        return `${Math.floor(s / 60)}m ${s % 60}s ago`;
      })()
    : '—';

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

  // P2 fix: count green-only as healthy
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
          <span className="sh-summary-tile__value">{fleet.length}</span>
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
          {/* P3 fix: always render label slot to prevent layout shift */}
          <span className="sh-summary-tile__label sh-summary-tile__label--fixed">
            {issueCount > 0 ? 'click to jump' : 'fleet status'}
          </span>
        </div>
        <div className="sh-summary-tile sh-summary-tile--refresh">
          <span className="sh-summary-tile__value sh-summary-tile__value--sm">{lastUpdateLabel}</span>
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
            const elapsed = elapsedLabel(train.lastHealthy);
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
                  // P2 fix: no row-level opacity — only chip indicates ticketed state
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
                  {train.lastHealthy
                    ? <span className={`sh-since sh-since--${sev}`} title={`Since ${train.lastHealthy}`}>
                        {elapsed ? `${elapsed} ago` : `since ${train.lastHealthy}`}
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

              {/* Train Link — P2 fix: always render, show Unknown if no data */}
              <div className="sh-panel__row">
                <span className="sh-panel__label">Train Link</span>
                {selectedTrain.connectivity ? (() => {
                  const c = selectedTrain.connectivity;
                  const isDegraded = c.status === 'degraded';
                  const elapsed = elapsedLabel(c.lastSeen);
                  return (
                    <div className="sh-conn__inline">
                      <span className={`sh-conn__status-badge${isDegraded ? ' sh-conn__status-badge--degraded' : ''}`}>
                        {isDegraded ? '⚠ Degraded' : '● Connected'}
                      </span>
                      <span className="sh-conn__lastseen">
                        {c.lastSeen}{elapsed ? ` · ${elapsed} ago` : ''}
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

              {/* Applications — P2 fix: green-only count */}
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
              {selectedTrain.lastHealthy && (
                <div className="sh-panel__timestamp">
                  Last fully healthy: {selectedTrain.lastHealthy} today
                  {elapsedLabel(selectedTrain.lastHealthy) && (
                    <span className="sh-panel__elapsed"> · {elapsedLabel(selectedTrain.lastHealthy)} ago</span>
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
