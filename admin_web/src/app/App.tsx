import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AdminShell } from '../components/AdminShell';
import { DesignSystemPage } from '../design-system/catalog/DesignSystemPage';
import { AuthProvider } from '../features/auth/AuthProvider';
import { LoginPage } from '../features/auth/LoginPage';
import { DashboardPage } from '../features/dashboard/DashboardPage';
import { HistoryPage } from '../features/history/HistoryPage';
import { MissionPage } from '../features/missions/MissionPage';
import { OrderDetailPage } from '../features/orders/OrderDetailPage';
import { OrdersPage } from '../features/orders/OrdersPage';
import { OperationsPage } from '../features/telemetry/OperationsPage';
import { VehiclesPage } from '../features/vehicles/VehiclesPage';
import { NotFoundPage } from '../routes/NotFoundPage';
import { RequireAdmin } from '../routes/RequireAdmin';

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAdmin />}>
            <Route element={<AdminShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="orders" element={<OrdersPage />} />
              <Route path="orders/:orderId" element={<OrderDetailPage />} />
              <Route path="missions/:missionId" element={<MissionPage />} />
              <Route path="vehicles" element={<VehiclesPage />} />
              <Route path="operations" element={<OperationsPage />} />
              <Route path="history" element={<HistoryPage />} />
              {import.meta.env.DEV ? (
                <Route path="design-system" element={<DesignSystemPage />} />
              ) : null}
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
