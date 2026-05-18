// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { luggageEventsToEscalations } from '../../mock/luggage';

// Pure helper: luggage event prepend with dedup — mirrors FleetContext LUGGAGE_EVENT handler
function applyLuggageEvent(prev, incoming) {
  const { id } = incoming ?? {};
  if (!id) return prev;
  if (prev.some(e => e.id === id)) return prev;
  return [incoming, ...prev];
}

describe('FleetContext LUGGAGE_EVENT — state logic', () => {
  it('prepends new event to empty array', () => {
    const next = applyLuggageEvent([], { id: 'lug-001', state: 'unattended', trainId: 'R5001C-031' });
    expect(next).toHaveLength(1);
    expect(next[0].id).toBe('lug-001');
  });

  it('prepends new event before existing events', () => {
    const existing = [{ id: 'lug-001', state: 'overcrowded' }];
    const next = applyLuggageEvent(existing, { id: 'lug-002', state: 'unattended' });
    expect(next[0].id).toBe('lug-002');
    expect(next[1].id).toBe('lug-001');
  });

  it('deduplicates on id — returns same reference when duplicate', () => {
    const existing = [{ id: 'lug-001', state: 'unattended' }];
    const next = applyLuggageEvent(existing, { id: 'lug-001', state: 'unattended' });
    expect(next).toBe(existing); // same reference
  });

  it('ignores event with missing id', () => {
    const existing = [{ id: 'lug-001' }];
    const next = applyLuggageEvent(existing, { state: 'unattended' });
    expect(next).toBe(existing);
  });
});

describe('luggageEventsToEscalations — live event shape', () => {
  const liveEvent = {
    id: 'evt-abc',
    trainId: 'R5001C-031',
    coachId: 'car-4',
    state: 'unattended',
    title: 'Unattended bag — car-4 seating-mid',
    detail: 'No owner detected for 3 min. Track: bag-0042.',
    confidence: 0.94,
    timestamp: '2026-05-19T11:23:04Z',
    stillFrame: null,
  };

  it('converts unattended live event to escalation with type luggage', () => {
    const escalations = luggageEventsToEscalations([liveEvent]);
    expect(escalations).toHaveLength(1);
    expect(escalations[0].type).toBe('luggage');
    expect(escalations[0].severity).toBe('red');
    expect(escalations[0].status).toBe('unacknowledged');
    expect(escalations[0].trainId).toBe('R5001C-031');
    expect(escalations[0].id).toBe('lug-esc-evt-abc');
  });

  it('converts overcrowded live event to escalation with amber severity', () => {
    const overcrowded = { ...liveEvent, id: 'evt-xyz', state: 'overcrowded' };
    const escalations = luggageEventsToEscalations([overcrowded]);
    expect(escalations[0].severity).toBe('amber');
  });

  it('filters out cleared and owner_returned events', () => {
    const cleared = { ...liveEvent, id: 'evt-c1', state: 'cleared' };
    const returned = { ...liveEvent, id: 'evt-c2', state: 'owner_returned' };
    expect(luggageEventsToEscalations([cleared])).toHaveLength(0);
    expect(luggageEventsToEscalations([returned])).toHaveLength(0);
  });

  it('returns empty array for empty events', () => {
    expect(luggageEventsToEscalations([])).toEqual([]);
  });

  it('mixed array: only active states become escalations', () => {
    const events = [
      { ...liveEvent, id: 'e1', state: 'unattended' },
      { ...liveEvent, id: 'e2', state: 'cleared' },
      { ...liveEvent, id: 'e3', state: 'overcrowded' },
    ];
    const result = luggageEventsToEscalations(events);
    expect(result).toHaveLength(2);
    expect(result.map(e => e.id)).toEqual(['lug-esc-e1', 'lug-esc-e3']);
  });
});
