import { useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './FleetMap.css';

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

const SEV_COLOR = { red: '#CC0022', amber: '#E8A020', green: '#22AA66' };

function makeIcon(severity, selected) {
  const color = SEV_COLOR[severity] ?? '#22AA66';
  const size = selected ? 14 : 10;
  const ringCircle = selected
    ? `<circle cx="16" cy="16" r="14" fill="none" stroke="${color}" stroke-width="3" stroke-opacity="0.4"/>`
    : '';
  const pulseClass = severity === 'red' && !selected ? 'fleet-marker--pulse' : '';
  return L.divIcon({
    className: pulseClass,
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      ${ringCircle}
      <circle cx="16" cy="16" r="${size}" fill="${color}" fill-opacity="0.95"/>
      <circle cx="16" cy="16" r="${size - 3}" fill="white" fill-opacity="0.25"/>
    </svg>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -16],
  });
}

export function FleetMap({ fleet, selectedTrainId, onTrainSelect }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef({});
  const fleetRef = useRef(fleet);
  const selectedRef = useRef(selectedTrainId);
  const onSelectRef = useRef(onTrainSelect);
  // eslint-disable-next-line react-hooks/refs
  fleetRef.current = fleet;
  // eslint-disable-next-line react-hooks/refs
  selectedRef.current = selectedTrainId;
  // eslint-disable-next-line react-hooks/refs
  onSelectRef.current = onTrainSelect;

  const placeMarkers = useCallback((map) => {
    fleetRef.current.forEach(train => {
      const pos = TRAIN_POSITIONS[train.id];
      if (!pos) return;
      const icon = makeIcon(train.severity, train.id === selectedRef.current);
      if (markersRef.current[train.id]) {
        markersRef.current[train.id].setIcon(icon);
      } else {
        const marker = L.marker([pos.lat, pos.lng], { icon })
          .addTo(map)
          .bindTooltip(train.id, {
            permanent: false,
            className: 'fleet-map-tooltip',
            direction: 'top',
            offset: [0, -16],
          });
        marker.on('click', () => onSelectRef.current(train.id));
        markersRef.current[train.id] = marker;
      }
    });
  }, []);

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

  useEffect(() => {
    if (!mapInstance.current) return;
    placeMarkers(mapInstance.current);
  }, [fleet, selectedTrainId, placeMarkers]);

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
    <div className="fleet-map">
      <div ref={mapRef} className="fleet-map__leaflet" />
      <div className="fleet-map__legend">
        <span className="fleet-map__legend-item fleet-map__legend-item--red">Critical</span>
        <span className="fleet-map__legend-item fleet-map__legend-item--amber">Warning</span>
        <span className="fleet-map__legend-item fleet-map__legend-item--green">Normal</span>
      </div>
    </div>
  );
}
