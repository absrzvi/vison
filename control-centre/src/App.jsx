import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/shell/AppShell';
import { ErrorBoundary } from './components/shell/ErrorBoundary';
import { LiveMonitoring } from './components/live/LiveMonitoring';
import { OccupancyMonitoring } from './components/occupancy/OccupancyMonitoring';
import { LuggageMonitoring } from './components/luggage/LuggageMonitoring';
import { SystemHealth } from './components/health/SystemHealth';
import { Analytics } from './components/analytics/Analytics';
import { EscalationsDashboard } from './components/escalations/EscalationsDashboard';
import './styles/global.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard/live" replace />} />
        <Route path="/dashboard" element={<AppShell />}>
          <Route index element={<Navigate to="live" replace />} />
          <Route path="live"         element={<ErrorBoundary><LiveMonitoring /></ErrorBoundary>} />
          <Route path="occupancy"    element={<ErrorBoundary><OccupancyMonitoring /></ErrorBoundary>} />
          <Route path="luggage"      element={<ErrorBoundary><LuggageMonitoring /></ErrorBoundary>} />
          <Route path="health"       element={<ErrorBoundary><SystemHealth /></ErrorBoundary>} />
          <Route path="analytics"    element={<ErrorBoundary><Analytics /></ErrorBoundary>} />
          <Route path="escalations"  element={<ErrorBoundary><EscalationsDashboard /></ErrorBoundary>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
