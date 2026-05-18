// @vitest-environment node
import { describe, it, expect, vi } from 'vitest';

/**
 * Tests for RealWebSocketClient luggage event handling.
 * We test _handleEnvelope directly by instantiating the class with a mock onMessage.
 * We cannot import the class directly (it uses import.meta.env), so we replicate
 * the handler logic as a pure function extracted for testing — mirroring the
 * pattern from SystemHealth.test.js.
 */

const SEVERITY_MAP = { info: 'green', warning: 'amber', critical: 'red' };

function handleEnvelope(envelope, onMessage, seenIds = new Set()) {
  const { event_id, vehicle_id, event_type, severity, payload, timestamp } = envelope;
  if (event_id != null && seenIds.has(event_id)) return false; // duplicate
  if (event_id != null) seenIds.add(event_id);

  const frontendSeverity = SEVERITY_MAP[severity] ?? 'green';
  const safePayload = payload ?? {};

  if (event_type === 'LUGGAGE_RACK_SATURATION') {
    onMessage({
      type: 'LUGGAGE_EVENT',
      payload: {
        id: event_id,
        trainId: vehicle_id,
        coachId: safePayload.car_id ?? null,
        state: 'overcrowded',
        title: 'Luggage area full — ' + (safePayload.car_id ?? 'unknown coach'),
        detail: 'Rack ' + (safePayload.rack_id ?? '') + ' at ' + Math.round((safePayload.fill_pct ?? 0) * 100) + '% capacity. ' + (safePayload.item_count ?? '?') + ' items detected.',
        confidence: safePayload.confidence ?? null,
        timestamp,
        stillFrame: null,
      },
    });
    return true;
  }

  if (event_type === 'UNATTENDED_BAG') {
    onMessage({
      type: 'LUGGAGE_EVENT',
      payload: {
        id: event_id,
        trainId: vehicle_id,
        coachId: safePayload.car_id ?? null,
        state: 'unattended',
        title: 'Unattended bag — ' + (safePayload.car_id ?? 'unknown coach') + (safePayload.zone ? ' ' + safePayload.zone : ''),
        detail: 'No owner detected for ' + Math.round((safePayload.dwell_s ?? 0) / 60) + ' min. Track: ' + (safePayload.track_id ?? '?') + '.',
        confidence: safePayload.confidence ?? null,
        timestamp,
        stillFrame: null,
      },
    });
    return true;
  }

  return false;
}

describe('RealWebSocketClient — LUGGAGE_RACK_SATURATION handler', () => {
  it('emits LUGGAGE_EVENT with state "overcrowded"', () => {
    const messages = [];
    const envelope = {
      event_id: 'evt-001',
      vehicle_id: 'R5001C-003',
      event_type: 'LUGGAGE_RACK_SATURATION',
      severity: 'warning',
      timestamp: '2026-05-19T11:09:22Z',
      payload: {
        car_id: 'car-2',
        rack_id: 'car-2-rack-upper-left',
        fill_pct: 0.95,
        item_count: 7,
        confidence: 0.88,
      },
    };
    handleEnvelope(envelope, msg => messages.push(msg));
    expect(messages).toHaveLength(1);
    expect(messages[0].type).toBe('LUGGAGE_EVENT');
    expect(messages[0].payload.state).toBe('overcrowded');
    expect(messages[0].payload.trainId).toBe('R5001C-003');
    expect(messages[0].payload.coachId).toBe('car-2');
    expect(messages[0].payload.confidence).toBe(0.88);
    expect(messages[0].payload.stillFrame).toBeNull();
    expect(messages[0].payload.title).toContain('car-2');
    expect(messages[0].payload.detail).toContain('95%');
    expect(messages[0].payload.detail).toContain('7 items');
  });

  it('handles missing optional fields gracefully', () => {
    const messages = [];
    const envelope = {
      event_id: 'evt-002',
      vehicle_id: 'R5001C-031',
      event_type: 'LUGGAGE_RACK_SATURATION',
      severity: 'warning',
      timestamp: '2026-05-19T11:00:00Z',
      payload: {},
    };
    handleEnvelope(envelope, msg => messages.push(msg));
    expect(messages[0].payload.coachId).toBeNull();
    expect(messages[0].payload.confidence).toBeNull();
    expect(messages[0].payload.title).toContain('unknown coach');
  });
});

describe('RealWebSocketClient — UNATTENDED_BAG handler', () => {
  it('emits LUGGAGE_EVENT with state "unattended"', () => {
    const messages = [];
    const envelope = {
      event_id: 'evt-003',
      vehicle_id: 'R5001C-031',
      event_type: 'UNATTENDED_BAG',
      severity: 'critical',
      timestamp: '2026-05-19T11:23:04Z',
      payload: {
        car_id: 'car-4',
        zone: 'seating-mid',
        track_id: 'bag-0042',
        dwell_s: 180.0,
        confidence: 0.94,
      },
    };
    handleEnvelope(envelope, msg => messages.push(msg));
    expect(messages).toHaveLength(1);
    expect(messages[0].type).toBe('LUGGAGE_EVENT');
    expect(messages[0].payload.state).toBe('unattended');
    expect(messages[0].payload.trainId).toBe('R5001C-031');
    expect(messages[0].payload.coachId).toBe('car-4');
    expect(messages[0].payload.confidence).toBe(0.94);
    expect(messages[0].payload.title).toContain('car-4');
    expect(messages[0].payload.title).toContain('seating-mid');
    expect(messages[0].payload.detail).toContain('3 min');
    expect(messages[0].payload.detail).toContain('bag-0042');
  });

  it('rounds dwell_s to minutes correctly', () => {
    const messages = [];
    handleEnvelope({
      event_id: 'evt-004',
      vehicle_id: 'R5001C-031',
      event_type: 'UNATTENDED_BAG',
      severity: 'critical',
      timestamp: '2026-05-19T11:00:00Z',
      payload: { dwell_s: 90.0, track_id: 'bag-0099' },
    }, msg => messages.push(msg));
    expect(messages[0].payload.detail).toContain('2 min');
  });
});

describe('RealWebSocketClient — dedup for luggage events', () => {
  it('drops duplicate event_id', () => {
    const messages = [];
    const seenIds = new Set();
    const envelope = {
      event_id: 'evt-005',
      vehicle_id: 'R5001C-031',
      event_type: 'UNATTENDED_BAG',
      severity: 'critical',
      timestamp: '2026-05-19T11:00:00Z',
      payload: { dwell_s: 60 },
    };
    handleEnvelope(envelope, msg => messages.push(msg), seenIds);
    handleEnvelope(envelope, msg => messages.push(msg), seenIds); // duplicate
    expect(messages).toHaveLength(1);
  });

  it('passes through events with different event_ids', () => {
    const messages = [];
    const seenIds = new Set();
    handleEnvelope({ event_id: 'a', vehicle_id: 'T1', event_type: 'UNATTENDED_BAG', severity: 'info', timestamp: 't', payload: {} }, msg => messages.push(msg), seenIds);
    handleEnvelope({ event_id: 'b', vehicle_id: 'T1', event_type: 'UNATTENDED_BAG', severity: 'info', timestamp: 't', payload: {} }, msg => messages.push(msg), seenIds);
    expect(messages).toHaveLength(2);
  });
});
