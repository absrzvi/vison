import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setToken, clearToken, getToken } from '../tokenStore';
import { authHeaders, handle401, onUnauthorized } from '../authFetch';

beforeEach(() => {
  setToken('jwt-abc');
});

afterEach(() => {
  clearToken();
  vi.restoreAllMocks();
});

describe('tokenStore', () => {
  it('stores and clears the token', () => {
    expect(getToken()).toBe('jwt-abc');
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe('authHeaders', () => {
  it('adds the Bearer header when a token is present', () => {
    expect(authHeaders()).toEqual({ Authorization: 'Bearer jwt-abc' });
  });

  it('merges extra headers', () => {
    expect(authHeaders({ 'Content-Type': 'application/json' })).toEqual({
      'Content-Type': 'application/json',
      Authorization: 'Bearer jwt-abc',
    });
  });

  it('omits the header when no token (request will 401)', () => {
    clearToken();
    expect(authHeaders()).toEqual({});
  });
});

describe('handle401', () => {
  it('clears the token and notifies listeners on 401', () => {
    const listener = vi.fn();
    const unsub = onUnauthorized(listener);
    const res = handle401({ status: 401 });
    expect(res).toEqual({ status: 401 }); // returned unchanged
    expect(getToken()).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    unsub();
  });

  it('does nothing on a non-401 response', () => {
    const listener = vi.fn();
    const unsub = onUnauthorized(listener);
    handle401({ status: 200 });
    expect(getToken()).toBe('jwt-abc');
    expect(listener).not.toHaveBeenCalled();
    unsub();
  });
});
