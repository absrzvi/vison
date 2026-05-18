import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getCapacityExceptions,
  reviewException,
  dismissException,
  reopenException,
  exportCapacityReviewCsv,
} from '../analytics';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function okJson(body = {}) {
  return { ok: true, status: 200, json: () => Promise.resolve(body) };
}

function okBlob(blob) {
  return { ok: true, status: 200, blob: () => Promise.resolve(blob) };
}

function noContent() {
  return { ok: true, status: 204, json: () => Promise.resolve({}) };
}

function errResponse(status) {
  return { ok: false, status };
}

beforeEach(() => { mockFetch.mockReset(); });
afterEach(() => { vi.restoreAllMocks(); });

// ── getCapacityExceptions ─────────────────────────────────────────────────────

describe('getCapacityExceptions', () => {
  it('GETs /api/v1/analytics/exceptions?range=7d by default', async () => {
    const records = [
      { exception_id: 'ex1', route: 'Vienna-Salzburg', train_id: 'VH-001',
        departure: '08:00', date: '2026-05-18', status: 'unreviewed',
        severity: 'critical', coach_peaks: [], trend: [] },
    ];
    mockFetch.mockResolvedValueOnce(okJson(records));
    const result = await getCapacityExceptions();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/analytics\/exceptions\?range=7d$/);
    expect(opts.method).toBe('GET');
    expect(opts.headers['X-API-Key']).toBeDefined();
    expect(result).toEqual(records);
  });

  it('encodes custom range parameter', async () => {
    mockFetch.mockResolvedValueOnce(okJson([]));
    await getCapacityExceptions('30d');
    const [url] = mockFetch.mock.calls[0];
    expect(url).toMatch(/range=30d/);
  });

  it('throws with .status on non-2xx', async () => {
    mockFetch.mockResolvedValueOnce(errResponse(422));
    await expect(getCapacityExceptions()).rejects.toMatchObject({ status: 422 });
  });

  it('propagates network errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Network failure'));
    await expect(getCapacityExceptions()).rejects.toThrow('Network failure');
  });
});

// ── reviewException ───────────────────────────────────────────────────────────

describe('reviewException', () => {
  it('POSTs to /analytics/exceptions/{id}/review with note and priority', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ status: 'in_review' }));
    const result = await reviewException('ex-1', 'Looks fine', 'high');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/analytics\/exceptions\/ex-1\/review$/);
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.note).toBe('Looks fine');
    expect(body.priority).toBe('high');
    expect(result).toEqual({ status: 'in_review' });
  });

  it('throws with .status on 403', async () => {
    mockFetch.mockResolvedValueOnce(errResponse(403));
    await expect(reviewException('ex-2', '', 'low')).rejects.toMatchObject({ status: 403 });
  });
});

// ── dismissException ──────────────────────────────────────────────────────────

describe('dismissException', () => {
  it('POSTs to /analytics/exceptions/{id}/dismiss', async () => {
    mockFetch.mockResolvedValueOnce(noContent());
    await dismissException('ex-3');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/analytics\/exceptions\/ex-3\/dismiss$/);
    expect(opts.method).toBe('POST');
  });

  it('throws with .status on non-2xx', async () => {
    mockFetch.mockResolvedValueOnce(errResponse(404));
    await expect(dismissException('ex-4')).rejects.toMatchObject({ status: 404 });
  });
});

// ── reopenException ───────────────────────────────────────────────────────────

describe('reopenException', () => {
  it('POSTs to /analytics/exceptions/{id}/reopen', async () => {
    mockFetch.mockResolvedValueOnce(okJson({ status: 'unreviewed' }));
    await reopenException('ex-5');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/analytics\/exceptions\/ex-5\/reopen$/);
    expect(opts.method).toBe('POST');
  });

  it('throws with .status on non-2xx', async () => {
    mockFetch.mockResolvedValueOnce(errResponse(500));
    await expect(reopenException('ex-6')).rejects.toMatchObject({ status: 500 });
  });
});

// ── exportCapacityReviewCsv ───────────────────────────────────────────────────

describe('exportCapacityReviewCsv', () => {
  it('GETs /api/v1/capacity-review-queue/export?format=csv and triggers download', async () => {
    const blob = new Blob(['csv,data'], { type: 'text/csv' });
    mockFetch.mockResolvedValueOnce(okBlob(blob));
    // Stub browser APIs absent in Node test environment
    const mockA = { href: '', download: '', click: vi.fn() };
    const createObjectURL = vi.fn(() => 'blob:mock');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });
    vi.stubGlobal('document', { createElement: vi.fn(() => mockA) });

    vi.useFakeTimers();
    await exportCapacityReviewCsv();
    vi.runAllTimers();
    vi.useRealTimers();

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/capacity-review-queue\/export\?format=csv$/);
    expect(opts.method).toBe('GET');
    expect(mockA.download).toMatch(/^capacity-review-\d{4}-\d{2}-\d{2}\.csv$/);
    expect(mockA.click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock');
  });

  it('throws with .status on non-2xx', async () => {
    mockFetch.mockResolvedValueOnce(errResponse(401));
    await expect(exportCapacityReviewCsv()).rejects.toMatchObject({ status: 401 });
  });
});
