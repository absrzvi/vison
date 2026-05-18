import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { raiseMaintenanceTicket } from '../maintenance';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function okResponse(body = {}) {
  return {
    ok: true,
    status: 201,
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

describe('raiseMaintenanceTicket', () => {
  it('POSTs to /api/v1/maintenance/tickets and resolves with ticket data', async () => {
    const ticketData = { ticket_id: 'REF#AB123', created_at: '2026-05-19T10:00:00Z' };
    mockFetch.mockResolvedValueOnce(okResponse(ticketData));
    const result = await raiseMaintenanceTicket('4011', 'CCTV degraded', 'op-1');
    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/maintenance\/tickets$/);
    expect(opts.method).toBe('POST');
    expect(result).toEqual(ticketData);
  });

  it('sends correct request body', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ ticket_id: 'REF#00001', created_at: '2026-05-19T10:00:00Z' }));
    await raiseMaintenanceTicket('4011', 'CCTV degraded', 'op-1');
    const [, opts] = mockFetch.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body.train_id).toBe('4011');
    expect(body.issue_summary).toBe('CCTV degraded');
    expect(body.raised_by).toBe('op-1');
  });

  it('sends X-API-Key header', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ ticket_id: 'REF#00001', created_at: '2026-05-19T10:00:00Z' }));
    await raiseMaintenanceTicket('4011', 'issue', 'op-1');
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers['X-API-Key']).toBeDefined();
  });

  it('sends Content-Type: application/json header', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ ticket_id: 'REF#00001', created_at: '2026-05-19T10:00:00Z' }));
    await raiseMaintenanceTicket('4011', 'issue', 'op-1');
    const [, opts] = mockFetch.mock.calls[0];
    expect(opts.headers['Content-Type']).toBe('application/json');
  });

  it('throws Error with .status on 4xx response', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(400));
    await expect(raiseMaintenanceTicket('4011', 'issue', 'op-1')).rejects.toMatchObject({ status: 400 });
  });

  it('throws Error with .status on 5xx response', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(500));
    await expect(raiseMaintenanceTicket('4011', 'issue', 'op-1')).rejects.toMatchObject({ status: 500 });
  });

  it('propagates network errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network failure'));
    await expect(raiseMaintenanceTicket('4011', 'issue', 'op-1')).rejects.toThrow('Network failure');
  });
});
