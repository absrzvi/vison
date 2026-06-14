import '@testing-library/jest-dom/vitest';
import { beforeEach } from 'vitest';
import { setToken } from './lib/auth/tokenStore';

// E11-S1: api calls now send a JWT Bearer header via the token store. Seed a
// token before each test so the existing api tests (which assert the auth
// header) and components that fetch on mount have one. Tests that specifically
// exercise the unauthenticated path clear it themselves.
beforeEach(() => {
  setToken('test-jwt-token');
});
