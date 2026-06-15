import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useFleetData } from '../../hooks/useFleetData';
import { useAuth } from '../../context/AuthContext';
import { OperatorPreferences } from './OperatorPreferences';
import './AppShell.css';

function secsElapsed(timestamp) {
  const [h, m] = timestamp.split(':').map(Number);
  const now = new Date();
  let diffSecs =
    (now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()) -
    (h * 3600 + m * 60);
  if (diffSecs < 0) diffSecs += 86400;
  return diffSecs;
}

export function AppShell() {
  const { escalations, wsStatus, alertThresholdSeconds } = useFleetData();
  const { role } = useAuth();
  const navigate = useNavigate();
  const [, setTick] = useState(0);
  const [showPrefs, setShowPrefs] = useState(false);

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 15000);
    return () => clearInterval(id);
  }, []);

  const unackedCount = escalations.filter(e => e.status === 'unacknowledged').length;

  // Critical hook: oldest unacknowledged red escalation beyond operator's configured threshold (AC5)
  const criticalUnacked = escalations.filter(
    e => e.status === 'unacknowledged' && e.severity === 'red' && secsElapsed(e.timestamp) >= alertThresholdSeconds
  );
  const showAlertHook = criticalUnacked.length > 0;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__logo">ÖBB</span>
          <span className="app-header__title">Passenger Intelligence</span>
        </div>
        <div className="app-header__meta">
          {showAlertHook && (
            <button
              className="app-header__alert-hook"
              data-testid="pid-app-shell-alert-hook"
              onClick={() => navigate('/dashboard/live')}
              aria-label={`${criticalUnacked.length} critical unacknowledged`}
            >
              {criticalUnacked.length} critical
            </button>
          )}
          <button
            className="app-header__settings"
            onClick={() => setShowPrefs(p => !p)}
            aria-label="Open operator preferences"
            aria-expanded={showPrefs}
          >
            ⚙
          </button>
          <span className="app-header__env">Control Centre</span>
        </div>
      </header>

      <nav className="tab-bar">
        <NavLink to="/dashboard/live" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`}>
          Live
          {unackedCount > 0 && <span className="tab-bar__badge">{unackedCount}</span>}
        </NavLink>
        <NavLink to="/dashboard/escalations" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`}>Escalations</NavLink>
        <NavLink to="/dashboard/occupancy" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`}>Occupancy</NavLink>
        <NavLink to="/dashboard/luggage"   className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`}>Luggage</NavLink>
        <NavLink to="/dashboard/health"    className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`}>System Health</NavLink>
        <NavLink to="/dashboard/analytics" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`}>Analytics</NavLink>
        {role === 'admin' && (
          <NavLink to="/dashboard/users" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`} data-testid="nav-users">Users</NavLink>
        )}
        {role === 'admin' && (
          <NavLink to="/dashboard/alert-classes" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`} data-testid="nav-alert-classes">Alert Classes</NavLink>
        )}
        <NavLink to="/dashboard/profile" className={({ isActive }) => `tab-bar__tab ${isActive ? 'tab-bar__tab--active' : ''}`} data-testid="nav-profile">Profile</NavLink>
      </nav>

      {wsStatus === 'reconnecting' && (
        <div className="app-reconnecting-banner" role="status" aria-live="polite">
          Reconnecting…
        </div>
      )}

      <main className="app-main">
        <Outlet />
      </main>

      {showPrefs && <OperatorPreferences onClose={() => setShowPrefs(false)} />}
    </div>
  );
}
