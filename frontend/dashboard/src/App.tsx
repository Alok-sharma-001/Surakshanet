import React, { useEffect, useState } from 'react';
import { Navigate, Routes, Route, Outlet } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import DashboardLayout from './components/Layout/DashboardLayout';

// Mock components for pages
const TrafficMapPage = () => <div className="p-4">Traffic Map</div>;
const JunctionDetailPage = () => <div className="p-4">Junction Detail</div>;
const SignalControlPage = () => <div className="p-4">Signal Control</div>;
const ForecastingPage = () => <div className="p-4">Forecasting</div>;
const RoutingPage = () => <div className="p-4">Routing</div>;
const AlertsPage = () => <div className="p-4">Alerts</div>;
const EmergencyPage = () => <div className="p-4">Emergency</div>;
const AnalyticsPage = () => <div className="p-4">Analytics</div>;
const UserManagementPage = () => <div className="p-4">User Management</div>;

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loadFromStorage } = useAuthStore();
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    loadFromStorage();
    setIsLoaded(true);
  }, [loadFromStorage]);

  if (!isLoaded) return <div>Loading...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return <>{children}</>;
};

function App() {
  return (
    <>
      <Toaster position="top-right" />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<TrafficMapPage />} />
          <Route path="junctions/:id" element={<JunctionDetailPage />} />
          <Route path="signals" element={<SignalControlPage />} />
          <Route path="forecasting" element={<ForecastingPage />} />
          <Route path="routing" element={<RoutingPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="emergency" element={<EmergencyPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="users" element={<UserManagementPage />} />
        </Route>
      </Routes>
    </>
  );
}

export default App;
