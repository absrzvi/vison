import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/shell/AppShell';
import { ErrorBoundary } from './components/shell/ErrorBoundary';
import { LiveMonitoring } from './components/live/LiveMonitoring';
import { OccupancyMonitoring } from './components/occupancy/OccupancyMonitoring';
import { LuggageMonitoring } from './components/luggage/LuggageMonitoring';
import { SystemHealth } from './components/health/SystemHealth';
import { Analytics } from './components/analytics/Analytics';
import { EscalationsDashboard } from './components/escalations/EscalationsDashboard';
import { Users } from './components/admin/Users';
import { Login } from './components/auth/Login';
import { useAuth } from './context/AuthContext';
import './styles/global.css';
import './styles/skeletons.css';

// E11-S1 — unauthenticated users are sent to /login; the dashboard is gated.
function RequireAuth({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

// E11-S2 — admin-only screens. A non-admin who reaches the route directly is
// bounced to the dashboard (the nav entry is also hidden). Server still enforces.
function RequireAdmin({ children }) {
  const { role } = useAuth();
  return role === 'admin' ? children : <Navigate to="/dashboard/live" replace />;
}

export default function App() {
  const { isAuthenticated } = useAuth();
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/dashboard/live" replace /> : <Login />}
        />
        <Route path="/" element={<Navigate to="/dashboard/live" replace />} />
        <Route
          path="/dashboard"
          element={<RequireAuth><AppShell /></RequireAuth>}
        >
          <Route index element={<Navigate to="live" replace />} />
          <Route path="live"         element={<ErrorBoundary><LiveMonitoring /></ErrorBoundary>} />
          <Route path="occupancy"    element={<ErrorBoundary><OccupancyMonitoring /></ErrorBoundary>} />
          <Route path="luggage"      element={<ErrorBoundary><LuggageMonitoring /></ErrorBoundary>} />
          <Route path="health"       element={<ErrorBoundary><SystemHealth /></ErrorBoundary>} />
          <Route path="analytics"    element={<ErrorBoundary><Analytics /></ErrorBoundary>} />
          <Route path="escalations"  element={<ErrorBoundary><EscalationsDashboard /></ErrorBoundary>} />
          <Route path="users"        element={<RequireAdmin><ErrorBoundary><Users /></ErrorBoundary></RequireAdmin>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
