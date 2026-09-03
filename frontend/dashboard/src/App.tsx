import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { StudioHomePage } from './pages/StudioHomePage';
import DashboardLayout from './components/Layout/DashboardLayout';
import TrafficMapPage from './pages/TrafficMapPage';
import JunctionsPage from './pages/JunctionsPage';
import JunctionDetailPage from './pages/JunctionDetailPage';
import SignalControlPage from './pages/SignalControlPage';
import ForecastingPage from './pages/ForecastingPage';
import RoutingPage from './pages/RoutingPage';
import AlertsPage from './pages/AlertsPage';
import EmergencyPage from './pages/EmergencyPage';
import AnalyticsPage from './pages/AnalyticsPage';
import EmissionsPage from './pages/EmissionsPage';
import EdgeDevicesPage from './pages/EdgeDevicesPage';
import SimulationPage from './pages/SimulationPage';
import UserManagementPage from './pages/UserManagementPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import { CommandCenterPage } from './pages/CommandCenterPage';

function App() {
  return (
    <>
      <Toaster 
        position="top-right" 
        toastOptions={{
          style: {
            borderRadius: '0.75rem',
            background: '#FFFFFF',
            color: '#1E1B1B',
            border: '1px solid #E2E8F0',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.08)',
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: '13px',
          },
        }} 
      />
      <Routes>
        {/* Primary route: Operations Dashboard */}
        <Route path="/" element={<Navigate to="/app" replace />} />

        {/* Main application with sidebar + header layout */}
        <Route path="/app" element={<DashboardLayout />}>
          <Route index element={<TrafficMapPage />} />
          <Route path="dashboard" element={<TrafficMapPage />} />
          <Route path="junctions" element={<JunctionsPage />} />
          <Route path="junctions/:id" element={<JunctionDetailPage />} />
          <Route path="signals" element={<SignalControlPage />} />
          <Route path="forecasting" element={<ForecastingPage />} />
          <Route path="emergency" element={<EmergencyPage />} />
          <Route path="routing" element={<RoutingPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="emissions" element={<EmissionsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="edge-devices" element={<EdgeDevicesPage />} />
          <Route path="simulation" element={<SimulationPage />} />
          <Route path="users" element={<UserManagementPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        {/* Studio Innovation Showcase (moved from /) */}
        <Route path="/studio" element={<StudioHomePage />} />

        {/* Shorthand routes */}
        <Route path="/dashboard" element={<Navigate to="/app" replace />} />
        <Route path="/command" element={<CommandCenterPage />} />
        <Route path="/login" element={<LoginPage />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </>
  );
}

export default App;
