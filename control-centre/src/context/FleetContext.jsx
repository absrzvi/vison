import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { MockWebSocketClient } from '../mock/websocket';
import { RealWebSocketClient } from '../ws/RealWebSocketClient';
import { LUGGAGE_EVENTS, luggageEventsToEscalations } from '../mock/luggage';

const LUGGAGE_ESCALATIONS = luggageEventsToEscalations(LUGGAGE_EVENTS);

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
  const [feedTypeFilter, setFeedTypeFilter] = useState('all');
  const [feedStatusFilter, setFeedStatusFilter] = useState(null);
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
        // FLEET_STATE is mock-only; real WS delivers individual events.
        setFleet(msg.payload.fleet);
        setKpis(msg.payload.kpis);
        setEscalations([...msg.payload.escalations, ...LUGGAGE_ESCALATIONS]);
        setLastUpdate(new Date());
      }
      if (msg.type === 'ESCALATION_UPDATED') {
        setEscalations(prev =>
          prev.map(e => e.id === msg.payload.id ? { ...e, ...msg.payload } : e)
        );
      }
      if (msg.type === 'ESCALATION_NEW') {
        setEscalations(prev => {
          if (prev.some(e => e.id === msg.payload.id)) return prev;
          return [msg.payload, ...prev];
        });
        setLastUpdate(new Date());
      }
      if (msg.type === 'TRAIN_UPDATE') {
        setFleet(prev => prev.map(t => {
          if (t.id !== msg.payload.trainId) return t;
          return { ...t, severity: msg.payload.severity ?? t.severity };
        }));
        setLastUpdate(new Date());
      }
    };

    const client = makeClient(onMessage, onStatusChange);
    wsRef.current = client;
    client.connect();
    return () => client.disconnect();
  }, []);

  const acknowledge = useCallback((id) => wsRef.current?.acknowledge(id), []);
  const resolve = useCallback((id, outcome) => wsRef.current?.resolve(id, outcome), []);

  return (
    <FleetContext.Provider value={{ fleet, kpis, escalations, lastUpdate, connected, wsStatus, acknowledge, resolve, feedTypeFilter, setFeedTypeFilter, feedStatusFilter, setFeedStatusFilter, clearFeedFilters }}>
      {children}
    </FleetContext.Provider>
  );
}

export function useFleetData() {
  const ctx = useContext(FleetContext);
  if (!ctx) throw new Error('useFleetData must be used inside FleetProvider');
  return ctx;
}
