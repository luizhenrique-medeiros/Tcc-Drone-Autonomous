import {
  Activity,
  BatteryCharging,
  CheckCircle2,
  ClipboardList,
  Navigation,
  Radio,
  RefreshCw,
  Route,
  Satellite,
  ShieldAlert,
} from 'lucide-react';
import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { OperationalAlerts } from '../../components/OperationalAlerts';
import { OperationalSourceBadge } from '../../components/OperationalSourceBadge';
import {
  Button,
  Card,
  Feedback,
  PageHeader,
  StateView,
  StatusBadge,
} from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import {
  adminApi,
  generateOperationalAlerts,
  getErrorMessage,
  type Mission,
  type Order,
  type SystemEvent,
  type Vehicle,
  type VehicleHealth,
} from '../../services';
import {
  formatDateTime,
  formatNullableText,
  formatOptionalNumber,
  formatPercent,
  shortId,
} from '../../utils/format';

interface DashboardData {
  orders: Order[];
  missions: Mission[];
  vehicles: Vehicle[];
  health: VehicleHealth | null;
  healthError: string;
  missionErrors: number;
  events: SystemEvent[];
}

export function DashboardPage() {
  const loader = useCallback(async (): Promise<DashboardData> => {
    const [orders, vehicles, events] = await Promise.all([
      adminApi.listOrders(),
      adminApi.listVehicles(),
      adminApi.listEvents(),
    ]);
    const missionResults = await Promise.all(
        orders
          .filter((order) => order.mission_id)
          .map(async (order) => {
            try {
              return await adminApi.getMission(order.mission_id as string);
            } catch {
              return null;
            }
          }),
      );
    const missions = missionResults.filter(
      (mission): mission is Mission => mission !== null,
    );
    let health: VehicleHealth | null = null;
    let healthError = '';
    if (vehicles[0]) {
      try {
        health = await adminApi.getVehicleHealth(vehicles[0].id);
      } catch (loadError) {
        healthError = getErrorMessage(loadError);
      }
    }
    return {
      orders,
      missions,
      vehicles,
      health,
      healthError,
      missionErrors: missionResults.length - missions.length,
      events,
    };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  if (isLoading && !data) return <StateView state="loading" />;
  if (error && !data) {
    return (
      <StateView
        state="error"
        description={error}
        actionLabel="Tentar novamente"
        onAction={() => void reload()}
      />
    );
  }
  if (!data) return null;

  const pending = data.orders.filter(
    (order) => order.status === 'PENDING_ADMIN_APPROVAL',
  ).length;
  const approved = data.orders.filter((order) => order.status === 'APPROVED').length;
  const review = data.missions.filter((mission) =>
    ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER', 'UNDER_REVIEW'].includes(
      mission.status,
    ),
  ).length;
  const authorization = data.missions.filter(
    (mission) => mission.status === 'READY_FOR_AUTHORIZATION',
  ).length;
  const active = data.missions.filter((mission) => mission.status === 'EXECUTING');
  const vehicle = data.vehicles[0];
  const operationalAlerts = generateOperationalAlerts({
    backendError:
      data.healthError ||
      (data.missionErrors > 0
        ? `${data.missionErrors} missão(ões) não puderam ser carregadas.`
        : undefined),
    vehicle,
    health: data.health,
    mission: active[0] ?? null,
    events: data.events,
    expectVehicle: true,
  });

  return (
    <>
      <PageHeader
        eyebrow="Operação segura"
        title="Visão geral"
        description="Prioridades administrativas, integridade do veículo e progresso das missões em um único lugar."
        actions={
          <Button variant="secondary" onClick={() => void reload()} loading={isLoading}>
            <RefreshCw size={17} aria-hidden="true" /> Atualizar
          </Button>
        }
      />
      {error ? <Feedback tone="warning">{error}</Feedback> : null}

      <section className="metrics-grid" aria-label="Indicadores operacionais">
        <Link className="metric-card metric-card--orange" to="/orders?status=pending">
          <span className="metric-card__icon"><ClipboardList size={22} /></span>
          <div><strong>{pending}</strong><span>Pedidos aguardando análise</span></div>
          <small>Primeira decisão humana</small>
        </Link>
        <Link className="metric-card" to="/orders?status=approved">
          <span className="metric-card__icon"><CheckCircle2 size={22} /></span>
          <div><strong>{approved}</strong><span>Pedidos aprovados</span></div>
          <small>Aguardando preparação</small>
        </Link>
        <Link className="metric-card" to="/orders">
          <span className="metric-card__icon"><Route size={22} /></span>
          <div><strong>{review}</strong><span>Missões em revisão</span></div>
          <small>Mission Planner obrigatório</small>
        </Link>
        <Link className="metric-card metric-card--blue" to="/orders">
          <span className="metric-card__icon"><ShieldAlert size={22} /></span>
          <div><strong>{authorization}</strong><span>Aguardando voo</span></div>
          <small>Segunda autorização</small>
        </Link>
      </section>

      <div className="dashboard-grid">
        <Card
          title="Saúde do veículo"
          action={<Link to="/vehicles">Ver diagnóstico</Link>}
          className="dashboard-health"
        >
          {!vehicle || !data.health ? (
            <StateView
              state="empty"
              compact
              title="Veículo sem leitura"
              description="A autorização permanece bloqueada até uma leitura válida."
            />
          ) : (
            <>
              <div className="vehicle-heading">
                <div>
                  <span className="vehicle-pulse" aria-hidden="true"><Radio size={21} /></span>
                  <div><strong>{vehicle.name}</strong><small>{vehicle.system}</small></div>
                </div>
                <div className="cluster">
                  <OperationalSourceBadge {...data.health} />
                  <StatusBadge status={vehicle.status} />
                </div>
              </div>
              <div className="health-grid">
                <HealthMetric
                  icon={<BatteryCharging size={20} />}
                  label="Bateria"
                  value={formatPercent(data.health.battery_percent)}
                  ok={data.health.battery_percent !== null && data.health.battery_percent >= 40}
                />
                <HealthMetric
                  icon={<Satellite size={20} />}
                  label="GPS"
                  value={`${formatOptionalNumber(data.health.satellites)} sat. · ${formatNullableText(data.health.gps_fix)}`}
                  ok={data.health.satellites !== null && data.health.satellites >= 10}
                />
                <HealthMetric
                  icon={<Navigation size={20} />}
                  label="Modo"
                  value={formatNullableText(data.health.flight_mode)}
                  ok={data.health.armed === false}
                />
                <HealthMetric
                  icon={<Activity size={20} />}
                  label="Heartbeat / EKF"
                  value={data.health.ekf_ok === true ? 'Nominal' : data.health.ekf_ok === false ? 'Verificar' : '--'}
                  ok={data.health.heartbeat_ok === true && data.health.ekf_ok === true}
                />
              </div>
              <p className="last-update">
                Medido: {formatDateTime(data.health.measured_at)} · recebido: {formatDateTime(data.health.received_at)} · veículo{' '}
                {data.health.armed === true
                  ? 'armado'
                  : data.health.armed === false
                    ? 'desarmado'
                    : '--'}
              </p>
            </>
          )}
        </Card>

        <Card
          title="Alertas recentes"
          action={<Link to="/history">Ver eventos</Link>}
        >
          <OperationalAlerts
            alerts={operationalAlerts}
            max={4}
            emptyMessage="Nenhum alerta operacional ativo."
          />
        </Card>
      </div>

      <div className="dashboard-grid dashboard-grid--bottom">
        <Card
          title="Pedidos recentes"
          action={<Link to="/orders">Abrir fila completa</Link>}
        >
          <div className="compact-list">
            {data.orders.slice(0, 5).map((order) => (
              <Link to={`/orders/${order.id}`} key={order.id} className="compact-list__row">
                <div><strong>#{shortId(order.id)}</strong><span>{order.customer.name}</span></div>
                <StatusBadge status={order.status} />
                <small>{formatDateTime(order.created_at)}</small>
              </Link>
            ))}
          </div>
        </Card>

        <Card title="Missões em execução" action={<Link to="/operations">Telemetria</Link>}>
          {active.length === 0 ? (
            <StateView
              state="empty"
              compact
              title="Nenhuma missão em voo"
              description="O painel continuará acompanhando heartbeat e eventos."
            />
          ) : (
            <div className="active-missions">
              {active.map((mission) => (
                <Link to={`/missions/${mission.id}`} key={mission.id}>
                  <span className="active-missions__icon"><Navigation size={21} /></span>
                  <div><strong>Missão #{shortId(mission.id)}</strong><span>Versão {mission.version} · {mission.waypoints.length} waypoints</span></div>
                  <StatusBadge status={mission.status} />
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

function HealthMetric({
  icon,
  label,
  value,
  ok,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  ok: boolean;
}) {
  return (
    <div className={`health-metric ${ok ? 'health-metric--ok' : 'health-metric--alert'}`}>
      <span>{icon}</span>
      <div><small>{label}</small><strong>{value}</strong></div>
    </div>
  );
}
