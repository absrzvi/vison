import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useFleetData } from '../../hooks/useFleetData';
import './AppShell.css';

function minsElapsed(timestamp) {
  const [h, m] = timestamp.split(':').map(Number);
  const now = new Date();
  let diff = (now.getHours() * 60 + now.getMinutes()) - (h * 60 + m);
  if (diff < 0) diff += 1440;
  return diff;
}

export function AppShell() {
  const { escalations } = useFleetData();
  const navigate = useNavigate();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 15000);
    return () => clearInterval(id);
  }, []);

  const unackedCount = escalations.filter(e => e.status === 'unacknowledged').length;

  // Critical hook: oldest unacknowledged escalation that has been waiting >60s
  const criticalUnacked = escalations.filter(
    e => e.status === 'unacknowledged' && e.severity === 'red' && minsElapsed(e.timestamp) >= 1
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
              onClick={() => navigate('/dashboard/live')}
              aria-label={`${criticalUnacked.length} critical unacknowledged`}
            >
              {criticalUnacked.length} critical
            </button>
          )}
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
      </nav>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
