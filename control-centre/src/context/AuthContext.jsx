// E11-S1 — auth state for the SPA. Tracks whether a token is present, exposes
// login/logout, and wires the global 401 signal (from authFetch) to a logout so
// any expired-token response redirects to /login.
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getToken } from '../lib/auth/tokenStore';
import { onUnauthorized } from '../lib/auth/authFetch';
import { login as apiLogin, logout as apiLogout } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getToken()));

  const login = useCallback(async (username, password) => {
    await apiLogin(username, password);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setIsAuthenticated(false);
  }, []);

  // A 401 from any API call clears the token (in authFetch) and flips us to
  // unauthenticated → the route guard redirects to /login.
  useEffect(() => onUnauthorized(() => setIsAuthenticated(false)), []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
