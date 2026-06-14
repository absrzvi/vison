import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getPreferences, patchPreferences } from '../preferences';
import { DEFAULT_ALERT_THRESHOLD_SECONDS, DEFAULT_STALENESS_THRESHOLD_SECONDS } from '../../constants/preferences';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function okResponse(body) {
  return { ok: true, json: () => Promise.resolve(body) };
}
function errorResponse(status, body = null) {
  return {
    ok: false,
    status,
    json: body ? () => Promise.resolve(body) : () => Promise.reject(new Error('no body')),
  };
}

beforeEach(() => mockFetch.mockReset());

// ── T7.1: getPreferences returns defaults on 404 ─────────────────────────

describe('getPreferences', () => {
  it('returns defaults when server responds 404', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(404));
    const prefs = await getPreferences();
    expect(prefs.threshold_sec).toBe(DEFAULT_ALERT_THRESHOLD_SECONDS);
    expect(prefs.staleness_threshold_sec).toBe(DEFAULT_STALENESS_THRESHOLD_SECONDS);
  });

  it('returns server values on 200', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({
      operator_id: 'dev-key',
      threshold_sec: 90,
      staleness_threshold_sec: 180,
    }));
    const prefs = await getPreferences();
    expect(prefs.threshold_sec).toBe(90);
    expect(prefs.staleness_threshold_sec).toBe(180);
  });

  it('throws on unexpected 5xx', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(500));
    await expect(getPreferences()).rejects.toMatchObject({ status: 500 });
  });

  it('GETs /api/v1/operators/me/preferences with Authorization header', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ threshold_sec: 60, staleness_threshold_sec: 120 }));
    await getPreferences();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/operators\/me\/preferences$/);
    expect(opts.method).toBe('GET');
    expect(opts.headers.Authorization).toBe('Bearer test-jwt-token');
  });
});

// ── T7.2: patchPreferences propagates error on 4xx ───────────────────────

describe('patchPreferences', () => {
  it('throws on 422', async () => {
    const detail = { error: 'INVALID_PREFERENCE', detail: 'bad value', recoverable: true };
    mockFetch.mockResolvedValueOnce(errorResponse(422, detail));
    const err = await patchPreferences({ threshold_sec: 999 }).catch(e => e);
    expect(err.status).toBe(422);
    expect(err.detail).toMatchObject({ error: 'INVALID_PREFERENCE' });
  });

  it('throws on 500', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(500));
    await expect(patchPreferences({ threshold_sec: 60 })).rejects.toMatchObject({ status: 500 });
  });

  it('PATCHes /api/v1/operators/me/preferences with correct body', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ threshold_sec: 30, staleness_threshold_sec: 120, operator_id: 'key', updated_at: 'now' }));
    await patchPreferences({ threshold_sec: 30 });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/operators\/me\/preferences$/);
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body)).toEqual({ threshold_sec: 30 });
    expect(opts.headers.Authorization).toBe('Bearer test-jwt-token');
  });

  it('returns parsed body on 200', async () => {
    const body = { threshold_sec: 30, staleness_threshold_sec: 120, operator_id: 'key', updated_at: '2026-05-18T10:00:00Z' };
    mockFetch.mockResolvedValueOnce(okResponse(body));
    const result = await patchPreferences({ threshold_sec: 30 });
    expect(result).toEqual(body);
  });
});
