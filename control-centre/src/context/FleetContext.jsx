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
  return new MockWebSocketClient(onMessage);
}

export function FleetProvider({ children }) {
  const [fleet, setFleet] = useState([]);
  const [kpis, setKpis] = useState({});
  const [escalations, setEscalations] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connected, setConnected] = useState(false);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const wsRef = useRef(null);

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
        setConnected(true);
        setWsStatus('connected');
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
    <FleetContext.Provider value={{ fleet, kpis, escalations, lastUpdate, connected, wsStatus, acknowledge, resolve }}>
      {children}
    </FleetContext.Provider>
  );
}

export function useFleetData() {
  const ctx = useContext(FleetContext);
  if (!ctx) throw new Error('useFleetData must be used inside FleetProvider');
  return ctx;
}
