// E11-S1 — minimal functional login (full WDS UX pass is a tracked Epic-11
// exit step). Dark-ops theme via --obb-* tokens. Three states: idle, submitting,
// error. On success, AuthContext flips isAuthenticated and the route guard sends
// the user to the dashboard.
import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import './Login.css';

export function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      // No navigate() here — AuthProvider flips isAuthenticated and the guard
      // in App.jsx renders the dashboard.
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit} aria-label="Sign in">
        <h1 className="login-title">ÖBB Control Centre</h1>
        <p className="login-subtitle">Sign in to continue</p>

        <label className="login-field">
          <span>Username</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </label>

        <label className="login-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}

        <button className="login-submit" type="submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
