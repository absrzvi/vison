import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { acknowledgeEscalation, resolveEscalation, getTrainAlerts } from '../escalations';

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

describe('getTrainAlerts', () => {
  it('GETs /api/v1/trains/{id}/alerts?status=active and returns parsed array', async () => {
    const alerts = [{ alert_id: 'a1', type: 'occupancy', coach_id: 'C1', title: 'High occupancy', confidence: 92, camera_id: 'cam-1', raised_at: '10:00', status: 'active' }];
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(alerts) });
    const result = await getTrainAlerts('train-99');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/trains\/train-99\/alerts\?status=active$/);
    expect(opts.method).toBe('GET');
    expect(opts.headers['X-API-Key']).toBeDefined();
    expect(result).toEqual(alerts);
  });

  it('throws an Error with .status on non-2xx', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });
    await expect(getTrainAlerts('train-99')).rejects.toMatchObject({ status: 404 });
  });

  it('propagates network errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network failure'));
    await expect(getTrainAlerts('train-99')).rejects.toThrow('Network failure');
  });
});
