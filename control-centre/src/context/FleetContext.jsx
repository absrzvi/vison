import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { MockWebSocketClient } from '../mock/websocket';
import { LUGGAGE_EVENTS, luggageEventsToEscalations } from '../mock/luggage';

const LUGGAGE_ESCALATIONS = luggageEventsToEscalations(LUGGAGE_EVENTS);

const FleetContext = createContext(null);

export function FleetProvider({ children }) {
  const [fleet, setFleet] = useState([]);
  const [kpis, setKpis] = useState({});
  const [escalations, setEscalations] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const client = new MockWebSocketClient((msg) => {
      if (msg.type === 'FLEET_STATE') {
        setFleet(msg.payload.fleet);
        setKpis(msg.payload.kpis);
        // Merge luggage escalations with AI/staff/roland escalations
        setEscalations([...msg.payload.escalations, ...LUGGAGE_ESCALATIONS]);
        setLastUpdate(new Date());
        setConnected(true);
      }
      if (msg.type === 'ESCALATION_UPDATED') {
        setEscalations(prev =>
          prev.map(e => e.id === msg.payload.id ? { ...e, ...msg.payload } : e)
        );
      }
    });
    wsRef.current = client;
    client.connect();
    return () => client.disconnect();
  }, []);

  const acknowledge = useCallback((id) => wsRef.current?.acknowledge(id), []);
  const resolve = useCallback((id, outcome) => wsRef.current?.resolve(id, outcome), []);

  return (
    <FleetContext.Provider value={{ fleet, kpis, escalations, lastUpdate, connected, acknowledge, resolve }}>
      {children}
    </FleetContext.Provider>
  );
}

export function useFleetData() {
  const ctx = useContext(FleetContext);
  if (!ctx) throw new Error('useFleetData must be used inside FleetProvider');
  return ctx;
}
