import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import DashboardLayout from './components/Layout/DashboardLayout';
import ErrorBoundary from './components/ErrorBoundary';

// Route-level code splitting using React.lazy
const TrafficMapPage = lazy(() => import('./pages/TrafficMapPage'));
const JunctionsPage = lazy(() => import('./pages/JunctionsPage'));
const JunctionDetailPage = lazy(() => import('./pages/JunctionDetailPage'));
const SignalControlPage = lazy(() => import('./pages/SignalControlPage'));
const ForecastingPage = lazy(() => import('./pages/ForecastingPage'));
const RoutingPage = lazy(() => import('./pages/RoutingPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const EmergencyPage = lazy(() => import('./pages/EmergencyPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const EmissionsPage = lazy(() => import('./pages/EmissionsPage'));
const EdgeDevicesPage = lazy(() => import('./pages/EdgeDevicesPage'));
const SimulationPage = lazy(() => import('./pages/SimulationPage'));
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const EventsPage = lazy(() => import('./pages/EventsPage'));
const PublicAdvisoryPage = lazy(() => import('./pages/PublicAdvisoryPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const StudioHomePage = lazy(() => import('./pages/StudioHomePage').then(m => ({ default: m.StudioHomePage })));
const CommandCenterPage = lazy(() => import('./pages/CommandCenterPage').then(m => ({ default: m.CommandCenterPage })));

const PageLoader = () => (
  <div className="flex h-[calc(100vh-120px)] w-full items-center justify-center">
    <div className="flex flex-col items-center gap-3">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
      <span className="text-xs font-medium text-neutral-500 font-mono tracking-wider uppercase">Loading View...</span>
    </div>
  </div>
);

function App() {
  return (
    <ErrorBoundary>
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
      <Suspense fallback={<PageLoader />}>
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
            <Route path="events" element={<EventsPage />} />
            <Route path="users" element={<UserManagementPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          {/* Public Citizen Information Service (Unauthenticated, Mobile-First) */}
          <Route path="/public" element={<PublicAdvisoryPage />} />
          <Route path="/public/advisories" element={<PublicAdvisoryPage />} />

          {/* Studio Innovation Showcase */}
          <Route path="/studio" element={<StudioHomePage />} />

          {/* Shorthand routes */}
          <Route path="/dashboard" element={<Navigate to="/app" replace />} />
          <Route path="/command" element={<CommandCenterPage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}

export default App;
