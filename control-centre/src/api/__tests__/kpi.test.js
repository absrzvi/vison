import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getDelayMinutesAvoided } from '../kpi';
import { setToken, clearToken } from '../../lib/auth/tokenStore';

const MOCK_RESPONSE = { delay_minutes_avoided: 12.0, window_hours: 24 };

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  setToken('test-jwt-token');
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe('getDelayMinutesAvoided', () => {
  it('resolves with parsed JSON on 200', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => MOCK_RESPONSE,
    });
    const data = await getDelayMinutesAvoided();
    expect(data).toEqual(MOCK_RESPONSE);
  });

  it('sends the Authorization Bearer header to the KPI endpoint', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => MOCK_RESPONSE });
    await getDelayMinutesAvoided();
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain('/api/v1/kpi/delay-minutes-avoided');
    expect(opts.headers.Authorization).toBe('Bearer test-jwt-token');
  });

  it('throws with status on a non-ok response', async () => {
    fetch.mockResolvedValue({ ok: false, status: 403 });
    await expect(getDelayMinutesAvoided()).rejects.toMatchObject({ status: 403 });
  });
});
