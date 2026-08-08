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
import { OperationalAlerts } from '../../components/OperationalAlerts';
import { OperationalSourceBadge } from '../../components/OperationalSourceBadge';
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
import {
  type StreamStatus,
  useOperationsStream,
} from '../../hooks/useOperationsStream';
import {
  adminApi,
  appConfig,
  generateOperationalAlerts,
  getErrorMessage,
  type Mission,
  type SystemEvent,
  type TelemetryPoint,
  type Vehicle,
  type VehicleHealth,
} from '../../services';
import {
  formatCoordinate,
  formatDateTime,
  formatNullableText,
  formatOptionalNumber,
  formatPercent,
  formatTime,
  shortId,
} from '../../utils/format';

interface OperationsData {
  missions: Mission[];
  missionErrors: string[];
  telemetry: TelemetryPoint[];
  telemetryError: string;
  events: SystemEvent[];
  vehicle: Vehicle | null;
  health: VehicleHealth | null;
  healthError: string;
}

const timestamp = (value: string | null) => {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const streamLabel = (status: StreamStatus) => {
  if (appConfig.demoMode) return 'Demo com polling';
  const labels: Record<StreamStatus, string> = {
    disabled: 'Tempo real desativado',
    connecting: 'Conectando WebSocket',
    authenticating: 'Autenticando WebSocket',
    connected: 'WebSocket conectado',
    reconnecting: 'Reconectando WebSocket',
    disconnected: 'WebSocket indisponível',
  };
  return labels[status];
};

export function OperationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedMissionId = searchParams.get('mission') ?? '';
  const loader = useCallback(async (): Promise<OperationsData> => {
    const [orders, events, vehicles] = await Promise.all([
      adminApi.listOrders(),
      adminApi.listEvents(),
      adminApi.listVehicles(),
    ]);

    const missionResults = await Promise.all(
      orders
        .filter((order) => order.mission_id)
        .map(async (order) => {
          try {
            return {
              mission: await adminApi.getMission(order.mission_id as string),
              error: '',
            };
          } catch (missionError) {
            return {
              mission: null,
              error: `Missão #${shortId(order.mission_id as string)}: ${getErrorMessage(missionError)}`,
            };
          }
        }),
    );
    const missions = missionResults.flatMap(({ mission }) => mission ? [mission] : []);
    const missionErrors = missionResults.flatMap(({ error: missionError }) => missionError ? [missionError] : []);
    const selected =
      missions.find((mission) => mission.id === requestedMissionId) ??
      missions.find((mission) => mission.status === 'EXECUTING') ??
      missions[0] ??
      null;
    const vehicle =
      vehicles.find((item) => item.id === selected?.vehicle_id) ?? vehicles[0] ?? null;

    let telemetry: TelemetryPoint[] = [];
    let telemetryError = '';
    let health: VehicleHealth | null = null;
    let healthError = '';
    await Promise.all([
      (async () => {
        if (!selected) return;
        try {
          telemetry = await adminApi.listTelemetry(selected.id);
        } catch (loadError) {
          telemetryError = getErrorMessage(loadError);
        }
      })(),
      (async () => {
        if (!vehicle) return;
        try {
          health = await adminApi.getVehicleHealth(vehicle.id);
        } catch (loadError) {
          healthError = getErrorMessage(loadError);
        }
      })(),
    ]);

    return {
      missions,
      missionErrors,
      telemetry,
      telemetryError,
      events,
      vehicle,
      health,
      healthError,
    };
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
    data.missions[0] ??
    null;
  const telemetry = selectedMission
    ? data.telemetry
        .filter((point) => point.mission_id === selectedMission.id)
        .sort((a, b) => timestamp(a.recorded_at) - timestamp(b.recorded_at))
    : [];
  const latest = telemetry.at(-1);
  const missionEvents = selectedMission
    ? data.events.filter((event) => event.mission_id === selectedMission.id)
    : data.events;
  const alertEvents = data.events.filter(
    (event) =>
      (!selectedMission || event.mission_id === selectedMission.id) ||
      (data.vehicle !== null && event.vehicle_id === data.vehicle.id),
  );
  const partialErrors = [
    error,
    ...data.missionErrors,
    data.telemetryError,
    data.healthError,
  ].filter(Boolean);
  const operationalAlerts = generateOperationalAlerts({
    backendError: partialErrors.join(' '),
    streamStatus,
    vehicle: data.vehicle,
    health: data.health,
    mission: selectedMission,
    telemetry,
    events: alertEvents,
    expectVehicle: true,
  });
  const telemetryCoordinates = telemetry.flatMap((point) =>
    point.latitude !== null && point.longitude !== null
      ? [{
          latitude: point.latitude,
          longitude: point.longitude,
          label: `Telemetria ${formatTime(point.recorded_at)}`,
        }]
      : [],
  );
  const mapPoints = selectedMission
    ? telemetryCoordinates.length > 0
      ? [selectedMission.origin, ...telemetryCoordinates, selectedMission.destination]
      : selectedMission.waypoints
    : [];

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
              {streamLabel(streamStatus)}
            </span>
            <Button variant="secondary" size="small" onClick={() => void reload()} loading={isLoading}>
              <RefreshCw size={16} /> Atualizar
            </Button>
          </>
        }
      />
      {error && data ? (
        <Feedback tone="error" className="page-feedback">
          {error} · os últimos dados bem-sucedidos permanecem visíveis e identificados.
        </Feedback>
      ) : null}

      <div className="operations-selector">
        <div className="field">
          <label htmlFor="mission-select">Missão acompanhada</label>
          <select
            className="select"
            id="mission-select"
            value={selectedMission?.id ?? ''}
            onChange={(event) => setSearchParams({ mission: event.target.value })}
            disabled={data.missions.length === 0}
          >
            {data.missions.length === 0 ? <option value="">Nenhuma missão carregada</option> : null}
            {data.missions.map((mission) => (
              <option value={mission.id} key={mission.id}>
                #{shortId(mission.id)} · {mission.status.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </div>
        {selectedMission ? <StatusBadge status={selectedMission.status} /> : null}
        {latest ? <OperationalSourceBadge {...latest} /> : null}
      </div>

      {operationalAlerts.length > 0 ? (
        <Card title="Alertas operacionais" className="page-feedback">
          <OperationalAlerts alerts={operationalAlerts} max={8} />
        </Card>
      ) : null}

      {!selectedMission ? (
        data.missionErrors.length > 0 ? (
          <StateView
            state="error"
            title="Não foi possível carregar as missões"
            description={data.missionErrors.join(' ')}
            actionLabel="Tentar novamente"
            onAction={() => void reload()}
          />
        ) : (
          <StateView state="empty" title="Nenhuma missão disponível" description="Prepare e revise uma missão para iniciar o acompanhamento." />
        )
      ) : (
        <>
          {data.telemetryError ? (
            <Feedback tone="error" className="page-feedback">
              Falha ao carregar telemetria: {data.telemetryError}. Nenhum valor é preenchido silenciosamente pelo snapshot de saúde.
            </Feedback>
          ) : telemetry.length === 0 ? (
            <Feedback tone="warning" className="page-feedback">
              Ainda não há amostras de telemetria para esta missão. Os valores abaixo permanecem como --; o snapshot de saúde é uma fonte separada.
            </Feedback>
          ) : null}
          {latest?.is_stale ? (
            <Feedback tone="error" className="page-feedback">
              A amostra mais recente foi marcada como vencida pelo backend e não representa o estado atual.
            </Feedback>
          ) : null}
          {data.health ? (
            <div className="health-source-note">
              <span>Snapshot de saúde separado:</span>
              <OperationalSourceBadge {...data.health} />
              <small>recebido {formatDateTime(data.health.received_at)}</small>
            </div>
          ) : data.healthError ? (
            <Feedback tone="error" className="page-feedback">Falha no snapshot de saúde: {data.healthError}</Feedback>
          ) : null}

          <section className="live-metrics" aria-label="Telemetria atual">
            <LiveMetric
              icon={<Navigation />}
              label="Altitude relativa"
              value={latest?.altitude_m === null || latest?.altitude_m === undefined ? '--' : `${formatOptionalNumber(latest.altitude_m, { maximumFractionDigits: 1 })} m`}
              detail={latest ? `Atualizado ${formatTime(latest.recorded_at)}` : 'Sem amostra'}
              chart={<Sparkline values={telemetry.flatMap((point) => point.altitude_m === null ? [] : [point.altitude_m])} label="Histórico de altitude" />}
            />
            <LiveMetric
              icon={<Gauge />}
              label="Velocidade"
              value={latest?.ground_speed_m_s === null || latest?.ground_speed_m_s === undefined ? '--' : `${formatOptionalNumber(latest.ground_speed_m_s, { maximumFractionDigits: 1 })} m/s`}
              detail={latest ? formatNullableText(latest.flight_mode) : 'Sem amostra'}
              chart={<Sparkline values={telemetry.flatMap((point) => point.ground_speed_m_s === null ? [] : [point.ground_speed_m_s])} label="Histórico de velocidade" color="orange" />}
            />
            <LiveMetric
              icon={<BatteryCharging />}
              label="Bateria"
              value={latest ? formatPercent(latest.battery_percent) : '--'}
              detail="Fonte: telemetria"
              chart={<Sparkline values={telemetry.flatMap((point) => point.battery_percent === null ? [] : [point.battery_percent])} label="Histórico de bateria" color="green" />}
            />
            <LiveMetric
              icon={<Satellite />}
              label="Satélites"
              value={latest?.satellites === null || latest?.satellites === undefined ? '--' : `${formatOptionalNumber(latest.satellites)} sat.`}
              detail="Fonte: telemetria"
              chart={<Sparkline values={telemetry.flatMap((point) => point.satellites === null ? [] : [point.satellites])} label="Histórico de satélites" />}
            />
          </section>

          <div className="operations-grid">
            <Card title="Posição e rota" action={<Link to={`/missions/${selectedMission.id}`}>Abrir missão</Link>}>
              <SatelliteMap
                points={mapPoints}
                title="Trajeto monitorado"
                height={410}
                activeIndex={telemetryCoordinates.length > 0 ? telemetryCoordinates.length : undefined}
              />
              {latest ? (
                <dl className="data-list telemetry-current">
                  <div><dt>Latitude atual</dt><dd className="mono">{latest.latitude === null ? '--' : formatCoordinate(latest.latitude)}</dd></div>
                  <div><dt>Longitude atual</dt><dd className="mono">{latest.longitude === null ? '--' : formatCoordinate(latest.longitude)}</dd></div>
                  <div><dt>Modo</dt><dd>{formatNullableText(latest.flight_mode)}</dd></div>
                  <div><dt>Armamento</dt><dd>{latest.armed === true ? 'Armado' : latest.armed === false ? 'Desarmado' : '--'}</dd></div>
                  <div><dt>Gravada</dt><dd>{formatDateTime(latest.recorded_at)}</dd></div>
                  <div><dt>Recebida</dt><dd>{formatDateTime(latest.received_at)}</dd></div>
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
