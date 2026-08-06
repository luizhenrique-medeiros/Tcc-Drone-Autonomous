import {
  Activity,
  BatteryCharging,
  Clock3,
  Gauge,
  Navigation,
  Radio,
  RefreshCw,
  Satellite,
  WifiOff,
} from 'lucide-react';
import { useCallback, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { SatelliteMap } from '../../components/SatelliteMap';
import { Sparkline } from '../../components/Sparkline';
import {
  Button,
  Card,
  Feedback,
  PageHeader,
  StateView,
  StatusBadge,
} from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { useOperationsStream } from '../../hooks/useOperationsStream';
import {
  adminApi,
  appConfig,
  type Mission,
  type SystemEvent,
  type TelemetryPoint,
  type Vehicle,
  type VehicleHealth,
} from '../../services';
import { formatDateTime, formatTime, shortId } from '../../utils/format';

interface OperationsData {
  missions: Mission[];
  telemetry: TelemetryPoint[];
  events: SystemEvent[];
  vehicle: Vehicle | null;
  health: VehicleHealth | null;
}

export function OperationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedMissionId = searchParams.get('mission') ?? '';
  const loader = useCallback(async (): Promise<OperationsData> => {
    const [orders, events, vehicles] = await Promise.all([
      adminApi.listOrders(),
      adminApi.listEvents(),
      adminApi.listVehicles(),
    ]);
    const missions = (
      await Promise.all(
        orders
          .filter((order) => order.mission_id)
          .map((order) =>
            adminApi.getMission(order.mission_id as string).catch(() => null),
          ),
      )
    ).filter((mission): mission is Mission => mission !== null);
    const selected =
      missions.find((mission) => mission.id === requestedMissionId) ??
      missions.find((mission) => mission.status === 'EXECUTING') ??
      missions[0];
    const vehicle =
      vehicles.find((item) => item.id === selected?.vehicle_id) ?? vehicles[0] ?? null;
    const [telemetry, health] = await Promise.all([
      adminApi.listTelemetry(selected?.id).catch(() => []),
      vehicle ? adminApi.getVehicleHealth(vehicle.id).catch(() => null) : null,
    ]);
    return { missions, telemetry, events, vehicle, health };
  }, [requestedMissionId]);
  const { data, isLoading, error, reload } = useAsyncData(loader);
  const streamStatus = useOperationsStream(() => void reload());

  useEffect(() => {
    const timer = window.setInterval(() => void reload(), 7_500);
    return () => window.clearInterval(timer);
  }, [reload]);

  if (isLoading && !data) return <StateView state="loading" />;
  if (error && !data) {
    return <StateView state="error" description={error} actionLabel="Tentar novamente" onAction={() => void reload()} />;
  }
  if (!data) return null;

  const selectedMission =
    data.missions.find((mission) => mission.id === requestedMissionId) ??
    data.missions.find((mission) => mission.status === 'EXECUTING') ??
    data.missions[0] ?? null;
  const telemetry = selectedMission
    ? data.telemetry.filter((point) => point.mission_id === selectedMission.id)
    : [];
  const latest = telemetry.at(-1);
  const missionEvents = selectedMission
    ? data.events.filter((event) => event.mission_id === selectedMission.id)
    : data.events;

  return (
    <>
      <PageHeader
        eyebrow="Acompanhamento"
        title="Operação ao vivo"
        description="Telemetria normalizada recebida do backend. O navegador não envia comandos MAVLink diretamente."
        actions={
          <>
            <span className={`stream-status stream-status--${streamStatus}`}>
              {streamStatus === 'connected' ? <Radio size={16} /> : <WifiOff size={16} />}
              {appConfig.demoMode
                ? 'Demo com polling'
                : streamStatus === 'connected'
                  ? 'WebSocket conectado'
                  : 'Polling de segurança'}
            </span>
            <Button variant="secondary" size="small" onClick={() => void reload()} loading={isLoading}>
              <RefreshCw size={16} /> Atualizar
            </Button>
          </>
        }
      />
      {error ? <Feedback tone="warning" className="page-feedback">{error}</Feedback> : null}

      <div className="operations-selector">
        <div className="field">
          <label htmlFor="mission-select">Missão acompanhada</label>
          <select
            className="select"
            id="mission-select"
            value={selectedMission?.id ?? ''}
            onChange={(event) => setSearchParams({ mission: event.target.value })}
          >
            {data.missions.map((mission) => (
              <option value={mission.id} key={mission.id}>
                #{shortId(mission.id)} · {mission.status.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </div>
        {selectedMission ? <StatusBadge status={selectedMission.status} /> : null}
      </div>

      {!selectedMission ? (
        <StateView state="empty" title="Nenhuma missão disponível" description="Prepare e revise uma missão para iniciar o acompanhamento." />
      ) : (
        <>
          {telemetry.length === 0 ? (
            <Feedback tone="warning" className="page-feedback">
              Ainda não há amostras de telemetria para esta missão. O estado mostrado abaixo vem da última leitura de saúde.
            </Feedback>
          ) : null}
          <section className="live-metrics" aria-label="Telemetria atual">
            <LiveMetric icon={<Navigation />} label="Altitude relativa" value={latest ? `${latest.altitude_m.toFixed(1)} m` : '—'} detail={latest ? `Atualizado ${formatTime(latest.recorded_at)}` : 'Sem amostra'} chart={<Sparkline values={telemetry.map((point) => point.altitude_m)} label="Histórico de altitude" />} />
            <LiveMetric icon={<Gauge />} label="Velocidade" value={latest ? `${latest.ground_speed_m_s.toFixed(1)} m/s` : '—'} detail={latest?.flight_mode ?? data.health?.flight_mode ?? 'Sem amostra'} chart={<Sparkline values={telemetry.map((point) => point.ground_speed_m_s)} label="Histórico de velocidade" color="orange" />} />
            <LiveMetric icon={<BatteryCharging />} label="Bateria" value={`${latest?.battery_percent.toFixed(0) ?? data.health?.battery_percent ?? '—'}%`} detail={data.health?.battery_voltage ? `${data.health.battery_voltage} V` : 'Tensão indisponível'} chart={<Sparkline values={telemetry.map((point) => point.battery_percent)} label="Histórico de bateria" color="green" />} />
            <LiveMetric icon={<Satellite />} label="GPS" value={`${latest?.satellites ?? data.health?.satellites ?? '—'} sat.`} detail={data.health?.gps_fix ?? 'Sem leitura'} chart={<Sparkline values={telemetry.map((point) => point.satellites)} label="Histórico de satélites" />} />
          </section>

          <div className="operations-grid">
            <Card title="Posição e rota" action={<Link to={`/missions/${selectedMission.id}`}>Abrir missão</Link>}>
              <SatelliteMap
                points={
                  telemetry.length > 0
                    ? [selectedMission.origin, ...telemetry, selectedMission.destination]
                    : selectedMission.waypoints
                }
                title="Trajeto monitorado"
                height={410}
                activeIndex={telemetry.length > 0 ? telemetry.length : undefined}
              />
              {latest ? (
                <dl className="data-list telemetry-current">
                  <div><dt>Latitude atual</dt><dd className="mono">{latest.latitude.toFixed(6)}</dd></div>
                  <div><dt>Longitude atual</dt><dd className="mono">{latest.longitude.toFixed(6)}</dd></div>
                  <div><dt>Modo</dt><dd>{latest.flight_mode}</dd></div>
                  <div><dt>Armamento</dt><dd>{latest.armed ? 'Armado' : 'Desarmado'}</dd></div>
                </dl>
              ) : null}
            </Card>

            <Card title="Linha do tempo da missão" action={<Link to="/history">Todos os eventos</Link>}>
              {missionEvents.length === 0 ? (
                <StateView state="empty" compact title="Sem eventos para esta missão" />
              ) : (
                <div className="timeline">
                  {missionEvents.slice(0, 12).map((event) => (
                    <article className={`timeline__item timeline__item--${event.severity.toLowerCase()}`} key={event.id}>
                      <span className="timeline__marker"><Activity size={15} /></span>
                      <div><strong>{event.message}</strong><span>{event.type.replaceAll('_', ' ')}</span><small><Clock3 size={13} /> {formatDateTime(event.created_at)}</small></div>
                    </article>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  );
}

function LiveMetric({ icon, label, value, detail, chart }: { icon: React.ReactNode; label: string; value: string; detail: string; chart: React.ReactNode }) {
  return (
    <article className="live-metric">
      <span className="live-metric__icon">{icon}</span>
      <div><small>{label}</small><strong>{value}</strong><span>{detail}</span></div>
      {chart}
    </article>
  );
}
