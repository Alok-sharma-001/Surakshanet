import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/**
 * Gates every /app route behind a valid session. Found live during a
 * 2026-09-12 acceptance audit: /app and every page under it (including
 * User Management and Audit) rendered fully for a browser with zero
 * stored token — no redirect to /login existed anywhere. The backend
 * already enforces real authorization on every API call (confirmed via
 * a live RBAC matrix across all 5 roles), so no protected data was ever
 * actually served to that unauthenticated shell — but a real user should
 * never see the operator dashboard's layout before proving who they are.
 */
export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
