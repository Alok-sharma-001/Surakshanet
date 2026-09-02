import React, { useEffect, useState } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import DashboardLayout from './components/Layout/DashboardLayout';
import TrafficMapPage from './pages/TrafficMapPage';
import JunctionDetailPage from './pages/JunctionDetailPage';
import SignalControlPage from './pages/SignalControlPage';
import ForecastingPage from './pages/ForecastingPage';
import RoutingPage from './pages/RoutingPage';
import AlertsPage from './pages/AlertsPage';
import EmergencyPage from './pages/EmergencyPage';
import AnalyticsPage from './pages/AnalyticsPage';
import UserManagementPage from './pages/UserManagementPage';

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
