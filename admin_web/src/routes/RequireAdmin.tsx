import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { StateView } from '../design-system/components';
import { useAuth } from '../features/auth/use-auth';

export function RequireAdmin() {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <main className="auth-loading">
        <StateView state="loading" title="Validando sessão administrativa" />
      </main>
    );
  }
  if (!user || user.role !== 'ADMIN') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}
