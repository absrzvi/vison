import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listUsers, createUser, patchUser, resetPassword } from '../users';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function okResponse(body = {}, status = 200) {
  return { ok: true, status, json: () => Promise.resolve(body) };
}
function errorResponse(status, detail) {
  return { ok: false, status, json: () => Promise.resolve(detail ? { detail: { detail } } : {}) };
}

beforeEach(() => mockFetch.mockReset());
afterEach(() => vi.restoreAllMocks());

describe('users api client', () => {
  it('listUsers GETs /api/v1/admin/users with Bearer', async () => {
    mockFetch.mockResolvedValueOnce(okResponse([{ user_id: '1', username: 'a', role: 'operator', is_active: true }]));
    const users = await listUsers();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/admin\/users$/);
    expect(opts.method).toBe('GET');
    expect(opts.headers.Authorization).toBe('Bearer test-jwt-token');
    expect(users).toHaveLength(1);
  });

  it('createUser POSTs the body', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ user_id: '2', username: 'op', role: 'operator', is_active: true }, 201));
    await createUser({ username: 'op', password: 'abcdefghijkl', role: 'operator' });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/admin\/users$/);
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body).toEqual({ username: 'op', password: 'abcdefghijkl', role: 'operator' });
  });

  it('patchUser PATCHes /{id}', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({ user_id: '2', username: 'op', role: 'admin', is_active: true }));
    await patchUser('2', { role: 'admin' });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/admin\/users\/2$/);
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body)).toEqual({ role: 'admin' });
  });

  it('resetPassword POSTs /{id}/reset-password and tolerates 204', async () => {
    mockFetch.mockResolvedValueOnce(okResponse({}, 204));
    const res = await resetPassword('2', 'brand-new-pw-9');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toMatch(/\/api\/v1\/admin\/users\/2\/reset-password$/);
    expect(opts.method).toBe('POST');
    expect(res).toBeNull();
  });

  it('surfaces the server detail message on conflict (409)', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(409, 'Username is not available'));
    await expect(createUser({ username: 'dup', password: 'abcdefghijkl', role: 'operator' }))
      .rejects.toMatchObject({ status: 409, message: 'Username is not available' });
  });

  it('throws with .status on 403 (operator blocked)', async () => {
    mockFetch.mockResolvedValueOnce(errorResponse(403));
    await expect(listUsers()).rejects.toMatchObject({ status: 403 });
  });
});
