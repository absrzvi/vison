import { useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { LUGGAGE_STATES } from '../../mock/luggage';
import './LuggageMap.css';

const TRAIN_POSITIONS = {
  'R5001C-031': { lat: 47.82, lng: 13.45 },
  'R5001C-022': { lat: 47.68, lng: 14.12 },
  'R5001C-017': { lat: 48.12, lng: 14.78 },
  'R5001C-008': { lat: 47.64, lng: 14.58 },
  'R5001C-044': { lat: 47.18, lng: 15.28 },
  'R5001C-055': { lat: 47.42, lng: 13.02 },
  'R5001C-012': { lat: 47.58, lng: 13.82 },
  'R5001C-003': { lat: 47.28, lng: 14.42 },
};

const STATE_PRIORITY = ['unattended', 'oversized', 'overcrowded', 'owner_returned', 'cleared'];

function makeIcon(worstState, count, selected) {
  const color = worstState ? (LUGGAGE_STATES[worstState]?.color ?? '#22AA66') : '#22AA66';
  const size = selected ? 15 : 11;
  const ring = selected
    ? `<circle cx="16" cy="16" r="14" fill="none" stroke="${color}" stroke-width="3" stroke-opacity="0.4"/>`
    : '';
  const label = count > 1
    ? `<text x="16" y="20" text-anchor="middle" font-size="9" font-weight="700" fill="white" font-family="monospace">${count}</text>`
    : '';
  return L.divIcon({
    className: '',
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      ${ring}
      <circle cx="16" cy="16" r="${size}" fill="${color}" fill-opacity="0.95"/>
      <circle cx="16" cy="16" r="${size - 3}" fill="white" fill-opacity="0.2"/>
      ${label}
    </svg>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16],
  });
}

export function LuggageMap({ summary, selectedTrainId, onTrainSelect }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef({});
  // Store latest props so the init callback can access them without a dep cycle
  const summaryRef = useRef(summary);
  const selectedRef = useRef(selectedTrainId);
  const onSelectRef = useRef(onTrainSelect);
  summaryRef.current = summary;
  selectedRef.current = selectedTrainId;
  onSelectRef.current = onTrainSelect;

  const placeMarkers = useCallback((map) => {
    Object.entries(TRAIN_POSITIONS).forEach(([trainId, pos]) => {
      const events = summaryRef.current[trainId]?.events ?? [];
      const count = events.filter(e => e.state !== 'cleared' && e.state !== 'owner_returned').length;
      const worstState = STATE_PRIORITY.find(s => events.some(e => e.state === s)) ?? null;
      const icon = makeIcon(worstState, count, trainId === selectedRef.current);

      if (markersRef.current[trainId]) {
        markersRef.current[trainId].setIcon(icon);
      } else {
        const marker = L.marker([pos.lat, pos.lng], { icon })
          .addTo(map)
          .bindTooltip(trainId, {
            permanent: false,
            className: 'fleet-map-tooltip',
            direction: 'top',
            offset: [0, -16],
          });
        marker.on('click', () => onSelectRef.current(trainId));
        markersRef.current[trainId] = marker;
      }
    });
  }, []);

  // Init map once — place markers immediately after tile layer is added
  useEffect(() => {
    if (mapInstance.current) return;
    const map = L.map(mapRef.current, {
      center: [47.6, 13.8],
      zoom: 7,
      zoomControl: false,
      attributionControl: false,
    });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 14 }).addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.control.attribution({ position: 'bottomright', prefix: '© CartoDB' }).addTo(map);
    mapInstance.current = map;
    placeMarkers(map);

    return () => {
      map.remove();
      mapInstance.current = null;
      markersRef.current = {};
    };
  }, [placeMarkers]);

  // Update marker icons when summary or selection changes
  useEffect(() => {
    if (!mapInstance.current) return;
    placeMarkers(mapInstance.current);
  }, [summary, selectedTrainId, placeMarkers]);

  // Fly to selected train
  useEffect(() => {
    if (!mapInstance.current) return;
    if (selectedTrainId) {
      const pos = TRAIN_POSITIONS[selectedTrainId];
      if (pos) mapInstance.current.flyTo([pos.lat, pos.lng], 9, { duration: 0.8 });
    } else {
      mapInstance.current.flyTo([47.6, 13.8], 7, { duration: 0.8 });
    }
  }, [selectedTrainId]);

  return (
    <div className="luggage-map">
      <div ref={mapRef} className="luggage-map__leaflet" />
      <div className="luggage-map__legend">
        <span className="luggage-map__legend-item luggage-map__legend-item--red">Unattended</span>
        <span className="luggage-map__legend-item luggage-map__legend-item--amber">Overcrowded / Oversized</span>
        <span className="luggage-map__legend-item luggage-map__legend-item--green">Cleared</span>
      </div>
    </div>
  );
}
