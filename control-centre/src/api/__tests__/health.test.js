import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getSystemHealth } from '../health';

const MOCK_RESPONSE = {
  trains: [
    {
      id: 'R5001C-031',
      cctvStatus: 'red',
      deviceStatus: 'red',
      appStatus: 'red',
      last_healthy: '2026-05-18T09:43:00Z',
      connectivity: { status: 'connected', lastSeen: '2026-05-18T11:35:00Z' },
      appDetail: [{ name: 'inference', status: 'red', note: 'exited·OOM' }],
      deviceDetail: { total: 6, unreachable: 2, coaches: ['C3', 'C5'], reason: 'VLAN 5 unreachable' },
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  vi.stubGlobal('import', { meta: { env: { VITE_API_URL: '', VITE_API_KEY: 'test-key' } } });
});

describe('getSystemHealth', () => {
  it('resolves with parsed JSON on 200', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => MOCK_RESPONSE,
    });
    const result = await getSystemHealth();
    expect(result).toEqual(MOCK_RESPONSE);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/analytics/system-health'),
      expect.objectContaining({ headers: expect.any(Object) })
    );
  });

  it('rejects with err.status on non-200', async () => {
    fetch.mockResolvedValue({ ok: false, status: 503 });
    await expect(getSystemHealth()).rejects.toMatchObject({ status: 503 });
  });

  it('rejects with err.status 404', async () => {
    fetch.mockResolvedValue({ ok: false, status: 404 });
    await expect(getSystemHealth()).rejects.toMatchObject({ status: 404 });
  });
});
