// E11-S2 — admin Users screen. Lists users; create (modal), toggle role,
// deactivate/reactivate, reset password. Admin-only: the route guard blocks
// operators, and the server enforces require_role on every call.
//
// Handles the three required states: loading, error, populated (control-centre
// CLAUDE.md). Mutations refetch the list so the UI reflects server truth.
import { useState, useEffect, useCallback } from 'react';
import { listUsers, createUser, patchUser, resetPassword } from '../../api/users';
import './Users.css';

function CreateUserModal({ onClose, onCreated }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('operator');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createUser({ username, password, role });
      onCreated();
    } catch (err) {
      setError(err.message || 'Could not create user');
      setSubmitting(false);
    }
  };

  return (
    <div className="users-modal__backdrop" role="dialog" aria-modal="true" aria-label="Create user">
      <form className="users-modal" onSubmit={submit}>
        <h3 className="users-modal__title">Create user</h3>
        <label className="users-field">
          <span>Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            required
            data-testid="users-create-username"
          />
        </label>
        <label className="users-field">
          <span>Password (min 12)</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={12}
            required
            data-testid="users-create-password"
          />
        </label>
        <label className="users-field">
          <span>Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} data-testid="users-create-role">
            <option value="operator">operator</option>
            <option value="admin">admin</option>
          </select>
        </label>
        {error && <p className="users-error" role="alert">{error}</p>}
        <div className="users-modal__actions">
          <button type="button" className="users-btn" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="users-btn users-btn--primary" disabled={submitting} data-testid="users-create-submit">
            {submitting ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  );
}

export function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await listUsers());
    } catch (err) {
      setError(err.message || 'Could not load users');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch-on-mount; load() is a stable useCallback. The synchronous setLoading
  // inside load is the intended initial-load transition, not a render cascade.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);

  const runAction = useCallback(async (fn) => {
    setActionError(null);
    try {
      await fn();
      await load();
    } catch (err) {
      setActionError(err.message || 'Action failed');
    }
  }, [load]);

  const toggleRole = (u) =>
    runAction(() => patchUser(u.user_id, { role: u.role === 'admin' ? 'operator' : 'admin' }));
  const toggleActive = (u) =>
    runAction(() => patchUser(u.user_id, { is_active: !u.is_active }));
  const doReset = (u) => {
    const pw = window.prompt(`New password for ${u.username} (min 12 chars):`);
    if (pw) runAction(() => resetPassword(u.user_id, pw));
  };

  if (loading) {
    return <div className="users" data-testid="users-loading"><p className="users-muted">Loading users…</p></div>;
  }
  if (error) {
    return (
      <div className="users" data-testid="users-error">
        <p className="users-error" role="alert">{error}</p>
        <button className="users-btn" onClick={load}>Retry</button>
      </div>
    );
  }

  return (
    <div className="users" data-testid="users-screen">
      <div className="users__header">
        <h2 className="users__title">Users</h2>
        <button className="users-btn users-btn--primary" onClick={() => setShowCreate(true)} data-testid="users-new">
          + New user
        </button>
      </div>
      {actionError && <p className="users-error" role="alert">{actionError}</p>}
      <table className="users-table">
        <thead>
          <tr><th>Username</th><th>Role</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id} className={u.is_active ? '' : 'users-row--inactive'}>
              <td className="users-mono">{u.username}</td>
              <td>{u.role}</td>
              <td>{u.is_active ? 'active' : 'inactive'}</td>
              <td className="users-actions">
                <button className="users-btn" onClick={() => toggleRole(u)}>
                  Make {u.role === 'admin' ? 'operator' : 'admin'}
                </button>
                <button className="users-btn" onClick={() => toggleActive(u)}>
                  {u.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
                <button className="users-btn" onClick={() => doReset(u)}>Reset password</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {users.length === 0 && <p className="users-muted">No users yet.</p>}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); }}
        />
      )}
    </div>
  );
}
