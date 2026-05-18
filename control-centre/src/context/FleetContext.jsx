import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { MockWebSocketClient } from '../mock/websocket';
import { RealWebSocketClient } from '../ws/RealWebSocketClient';
import { LUGGAGE_EVENTS, luggageEventsToEscalations } from '../mock/luggage';
import { acknowledgeEscalation, resolveEscalation, getTrainAlerts } from '../api/escalations';
import { getPreferences, patchPreferences } from '../api/preferences';
import {
  DEFAULT_ALERT_THRESHOLD_SECONDS,
  DEFAULT_STALENESS_THRESHOLD_SECONDS,
  LS_KEY_ALERT_THRESHOLD,
  LS_KEY_STALENESS_THRESHOLD,
} from '../constants/preferences';

const LUGGAGE_ESCALATIONS = luggageEventsToEscalations(LUGGAGE_EVENTS);
const OPERATOR_ID = import.meta.env.VITE_OPERATOR_ID ?? 'operator-unknown';

// Statuses that represent a terminal WS truth — safe to clear pending action state.
const TERMINAL_STATUSES = new Set(['acknowledged', 'resolved']);

const FleetContext = createContext(null);

function makeClient(onMessage, onStatusChange) {
  const wsUrl = import.meta.env.VITE_WS_URL;
  if (wsUrl) {
    return new RealWebSocketClient(onMessage, onStatusChange);
  }
  console.warn('[FleetContext] VITE_WS_URL not set — falling back to MockWebSocketClient');
  return new MockWebSocketClient(onMessage, onStatusChange);
}

export function FleetProvider({ children }) {
  const [fleet, setFleet] = useState([]);
  const [kpis, setKpis] = useState({});
  const [escalations, setEscalations] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connected, setConnected] = useState(false);
  const [wsStatus, setWsStatus] = useState('disconnected');
  // true after the first FLEET_STATE message — distinguishes "initial load" from "empty fleet"
  const [wsReady, setWsReady] = useState(false);
  const [feedTypeFilter, setFeedTypeFilter] = useState('all');
  const [feedStatusFilter, setFeedStatusFilter] = useState(null);

  // ── Alert threshold (AC2/AC3/AC5) ───────────────────────────────────────
  // Initialise from localStorage for instant value; background GET reconciles.
  const [alertThresholdSeconds, setAlertThresholdSeconds] = useState(() => {
    const parsed = parseInt(localStorage.getItem(LS_KEY_ALERT_THRESHOLD), 10);
    return Number.isFinite(parsed) ? parsed : DEFAULT_ALERT_THRESHOLD_SECONDS;
  });
  const [stalenessThresholdSeconds, setStalenessThresholdSeconds] = useState(() => {
    const parsed = parseInt(localStorage.getItem(LS_KEY_STALENESS_THRESHOLD), 10);
    return Number.isFinite(parsed) ? parsed : DEFAULT_STALENESS_THRESHOLD_SECONDS;
  });
  // Map<id, 'pending' | Error> — per-escalation action state
  const [escalationActionState, setEscalationActionState] = useState({});
  // { [trainId]: alert[] } — fetched from REST, updated by WS events
  const [trainAlerts, setTrainAlerts] = useState({});
  const [trainAlertsLoading, setTrainAlertsLoading] = useState({});
  const [trainAlertsError, setTrainAlertsError] = useState({});
  const wsRef = useRef(null);

  const clearFeedFilters = useCallback(() => {
    setFeedTypeFilter('all');
    setFeedStatusFilter(null);
  }, []);

  useEffect(() => {
    const onStatusChange = (status) => {
      setWsStatus(status);
      setConnected(status === 'connected');
    };

    const onMessage = (msg) => {
      if (msg.type === 'FLEET_STATE') {
        setFleet(msg.payload.fleet);
        setKpis(msg.payload.kpis);
        setEscalations([...msg.payload.escalations, ...LUGGAGE_ESCALATIONS]);
        setLastUpdate(new Date());
        setWsReady(true);
      }
      if (msg.type === 'ESCALATION_UPDATED') {
        setEscalations(prev =>
          prev.map(e => e.id === msg.payload.id ? { ...e, ...msg.payload } : e)
        );
        // Only clear pending action state when the WS tick carries a terminal status
        // (AC4). Clearing on any field update would race with in-flight REST calls.
        if (TERMINAL_STATUSES.has(msg.payload.status)) {
          setEscalationActionState(prev => {
            if (!(msg.payload.id in prev)) return prev;
            const next = { ...prev };
            delete next[msg.payload.id];
            return next;
          });
        }
      }
      if (msg.type === 'ESCALATION_NEW') {
        setEscalations(prev => {
          if (prev.some(e => e.id === msg.payload.id)) return prev;
          return [msg.payload, ...prev];
        });
        setLastUpdate(new Date());
      }
      if (msg.type === 'ALERT_RAISED') {
        const { train_id, alert_id } = msg.payload ?? {};
        if (train_id && alert_id) {
          setTrainAlerts(prev => {
            // Only update trains that have already been fetched — avoids seeding a
            // partial list that later REST responses would treat as authoritative.
            if (!(train_id in prev)) return prev;
            const existing = prev[train_id];
            if (existing.some(a => a.alert_id === alert_id)) return prev;
            return { ...prev, [train_id]: [msg.payload, ...existing] };
          });
        }
      }
      if (msg.type === 'ALERT_RESOLVED') {
        const { train_id, alert_id } = msg.payload ?? {};
        if (train_id && alert_id) {
          setTrainAlerts(prev => {
            const existing = prev[train_id];
            if (!existing) return prev;
            return { ...prev, [train_id]: existing.filter(a => a.alert_id !== alert_id) };
          });
        }
      }
      if (msg.type === 'TRAIN_UPDATE') {
        setFleet(prev => prev.map(t => {
          if (t.id !== msg.payload.trainId) return t;
          return { ...t, severity: msg.payload.severity ?? t.severity };
        }));
        setLastUpdate(new Date());
      }
      if (msg.type === 'CAMERA_DEGRADED' || msg.type === 'CAMERA_RECOVERED') {
        const { trainId, cctvStatus } = msg.payload ?? {};
        if (trainId) {
          setFleet(prev => prev.map(t =>
            t.id === trainId ? { ...t, cctvStatus } : t
          ));
          setLastUpdate(new Date());
        }
      }
    };

    const client = makeClient(onMessage, onStatusChange);
    wsRef.current = client;
    client.connect();
    return () => client.disconnect();
  }, []);

  // Background GET /api/v1/operators/me/preferences — server value wins (AC3)
  useEffect(() => {
    getPreferences().then(prefs => {
      const serverThreshold = prefs.threshold_sec;
      const serverStaleness = prefs.staleness_threshold_sec;
      setAlertThresholdSeconds(prev => {
        if (prev !== serverThreshold) {
          localStorage.setItem(LS_KEY_ALERT_THRESHOLD, String(serverThreshold));
          return serverThreshold;
        }
        return prev;
      });
      setStalenessThresholdSeconds(prev => {
        if (prev !== serverStaleness) {
          localStorage.setItem(LS_KEY_STALENESS_THRESHOLD, String(serverStaleness));
          return serverStaleness;
        }
        return prev;
      });
    }).catch(() => {
      // Network error — localStorage value stands; no-op
    });
  }, []);

  // updateAlertThreshold — PATCH + update state/localStorage; returns Error on failure (AC4)
  // Uses setter callback to capture prev so the revert isn't a stale closure.
  const updateAlertThreshold = useCallback(async (value) => {
    let prevValue;
    setAlertThresholdSeconds(prev => { prevValue = prev; return value; });
    try {
      await patchPreferences({ threshold_sec: value });
      localStorage.setItem(LS_KEY_ALERT_THRESHOLD, String(value));
      return null;
    } catch (err) {
      setAlertThresholdSeconds(prevValue);
      return err;
    }
  }, []);

  // updateStalenessThreshold — same pattern
  const updateStalenessThreshold = useCallback(async (value) => {
    let prevValue;
    setStalenessThresholdSeconds(prev => { prevValue = prev; return value; });
    try {
      await patchPreferences({ staleness_threshold_sec: value });
      localStorage.setItem(LS_KEY_STALENESS_THRESHOLD, String(value));
      return null;
    } catch (err) {
      setStalenessThresholdSeconds(prevValue);
      return err;
    }
  }, []);

  // generation counter per trainId — incremented on each fetch so a stale response
  // that resolves after a newer one is silently discarded.
  const fetchGenRef = useRef({});

  const fetchTrainAlerts = useCallback(async (trainId) => {
    const gen = (fetchGenRef.current[trainId] ?? 0) + 1;
    fetchGenRef.current = { ...fetchGenRef.current, [trainId]: gen };
    setTrainAlertsLoading(prev => ({ ...prev, [trainId]: true }));
    setTrainAlertsError(prev => { const n = { ...prev }; delete n[trainId]; return n; });
    try {
      const alerts = await getTrainAlerts(trainId);
      // Discard if a newer fetch for this trainId has already completed.
      if (fetchGenRef.current[trainId] !== gen) return;
      setTrainAlerts(prev => ({ ...prev, [trainId]: alerts }));
    } catch (err) {
      if (fetchGenRef.current[trainId] !== gen) return;
      console.error('[FleetContext] fetchTrainAlerts error', err);
      setTrainAlertsError(prev => ({ ...prev, [trainId]: err }));
    } finally {
      if (fetchGenRef.current[trainId] === gen) {
        setTrainAlertsLoading(prev => { const n = { ...prev }; delete n[trainId]; return n; });
      }
    }
  }, []);

  const acknowledge = useCallback(async (id) => {
    setEscalationActionState(prev => ({ ...prev, [id]: 'pending' }));
    try {
      await acknowledgeEscalation(id);
      // Only apply optimistic update if escalation hasn't already moved past 'acknowledged'
      // (guards against a WS 'resolved' arriving before this REST response).
      setEscalations(prev =>
        prev.map(e =>
          e.id === id && e.status === 'unacknowledged'
            ? { ...e, status: 'acknowledged' }
            : e
        )
      );
      setEscalationActionState(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setEscalationActionState(prev => ({ ...prev, [id]: err }));
    }
  }, []);

  const resolve = useCallback(async (id, outcome, actionTags) => {
    setEscalationActionState(prev => ({ ...prev, [id]: 'pending' }));
    try {
      await resolveEscalation(id, outcome, actionTags, OPERATOR_ID);
      // Only apply if not already resolved by a concurrent WS update.
      setEscalations(prev =>
        prev.map(e =>
          e.id === id && e.status !== 'resolved'
            ? { ...e, status: 'resolved' }
            : e
        )
      );
      setEscalationActionState(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      setEscalationActionState(prev => ({ ...prev, [id]: err }));
    }
  }, []);

  return (
    <FleetContext.Provider value={{
      fleet, kpis, escalations, lastUpdate, connected, wsStatus, wsReady,
      acknowledge, resolve, escalationActionState,
      trainAlerts, trainAlertsLoading, trainAlertsError, fetchTrainAlerts,
      feedTypeFilter, setFeedTypeFilter,
      feedStatusFilter, setFeedStatusFilter,
      clearFeedFilters,
      alertThresholdSeconds, stalenessThresholdSeconds,
      updateAlertThreshold, updateStalenessThreshold,
    }}>
      {children}
    </FleetContext.Provider>
  );
}

export function useFleetData() {
  const ctx = useContext(FleetContext);
  if (!ctx) throw new Error('useFleetData must be used inside FleetProvider');
  return ctx;
}
