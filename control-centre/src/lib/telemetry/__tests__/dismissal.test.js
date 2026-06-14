import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { emitSilentlyDismissed } from '../dismissal';

// dismissal.js reads import.meta.env at module load — mock fetch instead.
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
  mockFetch.mockResolvedValue({ ok: true, status: 204 });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('emitSilentlyDismissed', () => {
  it('POSTs a keepalive request to the silently-dismissed endpoint with the Authorization header', () => {
    emitSilentlyDismissed({
      escalationId: 'esc-1',
      operatorId: 'op-9',
      tViewed: '2026-06-13T10:00:00.000Z',
      tDismissed: '2026-06-13T10:00:08.000Z',
      dwellFocusMs: 4200,
    });
    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/escalations\/esc-1\/silently-dismissed$/);
    expect(opts.method).toBe('POST');
    // keepalive is what lets the request survive page unload (sendBeacon successor).
    expect(opts.keepalive).toBe(true);
    expect(opts.headers.Authorization).toBe('Bearer test-jwt-token');
    expect(opts.headers['Content-Type']).toBe('application/json');
  });

  it('serialises the dismissal body with snake_case fields', () => {
    emitSilentlyDismissed({
      escalationId: 'esc-2',
      operatorId: 'op-9',
      tViewed: '2026-06-13T10:00:00.000Z',
      tDismissed: '2026-06-13T10:00:08.000Z',
      dwellFocusMs: 1500,
    });
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({
      operator_id: 'op-9',
      t_viewed: '2026-06-13T10:00:00.000Z',
      t_dismissed: '2026-06-13T10:00:08.000Z',
      dwell_focus_ms: 1500,
    });
  });

  it('url-encodes the escalation id', () => {
    emitSilentlyDismissed({
      escalationId: 'esc/with space',
      operatorId: 'op-9',
      tViewed: 't1',
      tDismissed: 't2',
      dwellFocusMs: 0,
    });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('esc%2Fwith%20space');
  });

  it('never throws and swallows a rejected fetch (fire-and-forget)', () => {
    mockFetch.mockReturnValueOnce(Promise.reject(new Error('network down')));
    expect(() =>
      emitSilentlyDismissed({
        escalationId: 'esc-3',
        operatorId: 'op-9',
        tViewed: 't1',
        tDismissed: 't2',
        dwellFocusMs: 0,
      })
    ).not.toThrow();
  });
});
