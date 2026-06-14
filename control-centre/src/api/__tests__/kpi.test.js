import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getDelayMinutesAvoided } from '../kpi';

const MOCK_RESPONSE = { delay_minutes_avoided: 12.0, window_hours: 24 };

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
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

  it('sends the X-API-Key header to the KPI endpoint', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => MOCK_RESPONSE });
    await getDelayMinutesAvoided();
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain('/api/v1/kpi/delay-minutes-avoided');
    expect(opts.headers).toHaveProperty('X-API-Key');
  });

  it('throws with status on a non-ok response', async () => {
    fetch.mockResolvedValue({ ok: false, status: 403 });
    await expect(getDelayMinutesAvoided()).rejects.toMatchObject({ status: 403 });
  });
});
