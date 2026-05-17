import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { acknowledgeEscalation, resolveEscalation } from '../escalations';

// escalations.js reads import.meta.env at module load time — mock fetch instead.
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function okResponse(body = {}) {
  return {
    ok: true,
    json: () => Promise.resolve(body),
  };
}

function errorResponse(status) {
  return { ok: false, status };
}

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('acknowledgeEscalation', () => {
  it('POSTs to /api/v1/escalations/{id}/acknowledge and resolves on 200', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ status: 'acknowledged' }));
    const result = await acknowledgeEscalation('esc-1');
    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/escalations\/esc-1\/acknowledge$/);
    expect(opts.method).toBe('POST');
    expect(opts.headers['X-API-Key']).toBeDefined();
    expect(result).toEqual({ status: 'acknowledged' });
  });

  it('throws an Error with .status on non-2xx response', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(403));
    await expect(acknowledgeEscalation('esc-2')).rejects.toMatchObject({ status: 403 });
  });

  it('propagates network errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network failure'));
    await expect(acknowledgeEscalation('esc-3')).rejects.toThrow('Network failure');
  });
});

describe('resolveEscalation', () => {
  it('POSTs with outcome, action_tags, operator_id on 200', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ status: 'resolved' }));
    const result = await resolveEscalation('esc-4', 'Passenger assisted', ['Passenger assisted'], 'op-1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/escalations\/esc-4\/resolve$/);
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.outcome).toBe('Passenger assisted');
    expect(body.action_tags).toEqual(['Passenger assisted']);
    expect(body.operator_id).toBe('op-1');
    expect(result).toEqual({ status: 'resolved' });
  });

  it('throws an Error with .status on 500', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(500));
    await expect(resolveEscalation('esc-5', 'text', ['Other'], 'op-1')).rejects.toMatchObject({ status: 500 });
  });

  it('propagates network errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network failure'));
    await expect(resolveEscalation('esc-6', 'text', [], 'op-1')).rejects.toThrow('Network failure');
  });
});
