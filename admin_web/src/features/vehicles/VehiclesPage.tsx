import {
  Activity,
  BatteryCharging,
  CheckCircle2,
  Clock3,
  Gauge,
  MapPinned,
  Radio,
  RefreshCw,
  Satellite,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import { useCallback, useEffect } from 'react';
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
  type StreamStatus,
  useOperationsStream,
} from '../../hooks/useOperationsStream';
import {
  adminApi,
  generateOperationalAlerts,
  getErrorMessage,
  type Vehicle,
  type VehicleHealth,
} from '../../services';
import {
  formatDateTime,
  formatNullableText,
  formatOptionalNumber,
  formatPercent,
} from '../../utils/format';
import {
  getVehicleReadiness,
  isGpsFixValid,
} from '../missions/vehicle-readiness';

interface VehicleReading {
  vehicle: Vehicle;
  health: VehicleHealth | null;
  healthError: string;
}

const connectionLabel = (value: boolean | null) =>
  value === true ? 'ONLINE' : value === false ? 'OFFLINE' : '--';

const featureFlagLabel = (value: boolean | null) =>
  value === true ? 'HABILITADO' : value === false ? 'DESABILITADO' : '--';

const websocketLabel = (status: StreamStatus) =>
  status === 'connected'
    ? 'ONLINE'
    : status === 'disabled'
      ? 'DESATIVADO NO DEMO'
      : status.toUpperCase();

export function VehiclesPage() {
  const loader = useCallback(async (): Promise<VehicleReading[]> => {
    const vehicles = await adminApi.listVehicles();
    return Promise.all(
      vehicles.map(async (vehicle) => {
        try {
          return {
            vehicle,
            health: await adminApi.getVehicleHealth(vehicle.id),
            healthError: '',
          };
        } catch (loadError) {
          return {
            vehicle,
            health: null,
            healthError: getErrorMessage(loadError),
          };
        }
      }),
    );
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);
  const streamStatus = useOperationsStream(() => void reload());
  const operationalAlerts = (data ?? []).flatMap(
    ({ vehicle, health, healthError }) =>
      generateOperationalAlerts({
        backendError: healthError || undefined,
        streamStatus,
        vehicle,
        health,
        expectVehicle: true,
      }),
  );

  useEffect(() => {
    const timer = window.setInterval(() => void reload(), 10_000);
    return () => window.clearInterval(timer);
  }, [reload]);

  return (
    <>
      <PageHeader
        eyebrow="Leitura do gateway"
        title="Saúde do veículo"
        description="Diagnóstico somente leitura. Nenhum health check arma o veículo, inicia voo ou altera parâmetros críticos."
        actions={
          <>
            <span className={`stream-status stream-status--${streamStatus}`}>
              <Radio size={16} /> WS {websocketLabel(streamStatus)}
            </span>
            <Button
              variant="secondary"
              onClick={() => void reload()}
              loading={isLoading}
            >
              <RefreshCw size={17} /> Atualizar agora
            </Button>
          </>
        }
      />
      <Feedback tone="info" className="page-feedback">
        Atualização automática a cada 10 segundos e também ao receber eventos no
        WebSocket administrativo. Ausências permanecem como -- e bloqueiam a leitura
        correspondente.
      </Feedback>
      {isLoading && !data ? <StateView state="loading" /> : null}
      {error && !data ? (
        <StateView
          state="error"
          description={error}
          actionLabel="Tentar novamente"
          onAction={() => void reload()}
        />
      ) : null}
      {error && data ? (
        <Feedback tone="error" className="page-feedback">
          {error} · os dados anteriores permanecem identificados abaixo.
        </Feedback>
      ) : null}
      {data?.length === 0 ? (
        <StateView
          state="empty"
          title="Nenhum veículo cadastrado"
          description="Cadastre o veículo no backend antes da operação."
        />
      ) : null}
      {operationalAlerts.length > 0 ? (
        <Card title="Alertas de saúde" className="page-feedback">
          <OperationalAlerts alerts={operationalAlerts} max={6} />
        </Card>
      ) : null}
      {data ? (
        <div className="vehicles-stack">
          {data.map(({ vehicle, health, healthError }) => {
            const readiness = getVehicleReadiness(health);
            const minimumSatellites =
              health?.authorization_limits?.min_gps_satellites ?? null;
            const minimumBattery =
              health?.authorization_limits?.min_battery_percent ?? null;
            return (
              <Card
                key={vehicle.id}
                title={
                  <div className="vehicle-title">
                    <span>
                      <Radio size={22} />
                    </span>
                    <div>
                      <h2>{vehicle.name}</h2>
                      <small>{vehicle.system}</small>
                    </div>
                  </div>
                }
                action={
                  <div className="cluster">
                    {health ? <OperationalSourceBadge {...health} /> : null}
                    <StatusBadge
                      status={
                        health &&
                        (health.is_stale ||
                          health.connected !== true ||
                          health.heartbeat_ok !== true)
                          ? 'OFFLINE'
                          : vehicle.status
                      }
                    />
                  </div>
                }
              >
                {!health ? (
                  <StateView
                    state="error"
                    compact
                    title="Leitura indisponível"
                    description={`${healthError || 'A API não retornou uma leitura.'} A autorização de voo está bloqueada para este veículo.`}
                  />
                ) : (
                  <>
                    <div
                      className={`vehicle-readiness ${readiness.ready ? 'vehicle-readiness--ok' : 'vehicle-readiness--blocked'}`}
                    >
                      {readiness.ready ? (
                        <CheckCircle2 size={25} />
                      ) : (
                        <TriangleAlert size={25} />
                      )}
                      <div>
                        <strong>
                          {readiness.ready
                            ? 'Leitura atual atende aos mínimos técnicos'
                            : 'Leitura atual possui bloqueios'}
                        </strong>
                        <span>
                          {readiness.ready
                            ? 'O checklist humano e a validação do backend ainda são obrigatórios.'
                            : readiness.blockers.join(' ')}
                        </span>
                      </div>
                    </div>

                    <div className="diagnostics-grid">
                      <Diagnostic
                        icon={<Radio />}
                        label="Gateway"
                        value={formatNullableText(health.connection_state)}
                        detail={`ID ${vehicle.gateway_id}`}
                        ok={
                          health.connected === true &&
                          health.heartbeat_ok === true &&
                          !health.is_stale
                        }
                      />
                      <Diagnostic
                        icon={<Activity />}
                        label="Pixhawk"
                        value={connectionLabel(health.connected)}
                        detail={
                          health.connection_error
                            ? `Erro: ${health.connection_error}`
                            : 'Nenhum erro de conexão reportado'
                        }
                        ok={health.connected === true}
                      />
                      <Diagnostic
                        icon={<ShieldCheck />}
                        label="ArduPilot"
                        value={formatNullableText(vehicle.autopilot_system)}
                        detail={
                          vehicle.autopilot_version
                            ? `Versão ${vehicle.autopilot_version}`
                            : 'Versão indisponível'
                        }
                        ok={
                          health.heartbeat_ok === true &&
                          Boolean(vehicle.autopilot_version)
                        }
                      />
                      <Diagnostic
                        icon={<Radio />}
                        label="MAVLink"
                        value={
                          health.heartbeat_ok === true
                            ? 'HEARTBEAT OK'
                            : health.heartbeat_ok === false
                              ? 'SEM HEARTBEAT'
                              : '--'
                        }
                        detail={`SYSID ${formatOptionalNumber(health.mavlink_system_id)} · COMPID ${formatOptionalNumber(health.mavlink_component_id)} · idade ${formatOptionalNumber(health.heartbeat_age_seconds, { maximumFractionDigits: 1 })}s`}
                        ok={health.heartbeat_ok === true && !health.is_stale}
                      />
                      <Diagnostic
                        icon={<Gauge />}
                        label="Link MAVLink"
                        value={formatNullableText(health.connection_endpoint)}
                        detail={`${formatNullableText(health.connection_mode)} · ${formatNullableText(health.connection_topology)} · COM ${formatNullableText(health.serial_port)} · ${health.connection_baud === null ? 'baud --' : `${health.connection_baud} baud`}`}
                        ok={
                          health.connected === true &&
                          Boolean(health.connection_endpoint)
                        }
                      />
                      <Diagnostic
                        icon={<MapPinned />}
                        label="Posição atual"
                        value={
                          health.current_latitude === null ||
                          health.current_longitude === null
                            ? '--'
                            : `${health.current_latitude.toFixed(6)}, ${health.current_longitude.toFixed(6)}`
                        }
                        detail={
                          health.current_altitude_m === null
                            ? 'Altitude --'
                            : `Altitude ${formatOptionalNumber(health.current_altitude_m, { maximumFractionDigits: 1 })} m`
                        }
                        ok={
                          health.current_latitude !== null &&
                          health.current_longitude !== null
                        }
                      />
                      <Diagnostic
                        icon={<RefreshCw />}
                        label="Upload de missão"
                        value={featureFlagLabel(health.mission_upload_enabled)}
                        detail="Flag publicada pelo gateway"
                        ok={health.mission_upload_enabled === true}
                      />
                      <Diagnostic
                        icon={<ShieldCheck />}
                        label="Comandos de voo"
                        value={featureFlagLabel(health.flight_commands_enabled)}
                        detail="Flag publicada pelo gateway"
                        ok={health.flight_commands_enabled === true}
                      />
                      <Diagnostic
                        icon={<ShieldCheck />}
                        label="Início de missão"
                        value={featureFlagLabel(health.mission_start_enabled)}
                        detail="Flag independente publicada pelo gateway"
                        ok={health.mission_start_enabled === true}
                      />
                      <Diagnostic
                        icon={<Activity />}
                        label="Backend"
                        value="ONLINE"
                        detail="Esta leitura foi obtida pela API autenticada"
                        ok
                      />
                      <Diagnostic
                        icon={<Radio />}
                        label="WebSocket"
                        value={websocketLabel(streamStatus)}
                        detail="Atualiza esta página quando o gateway publica health"
                        ok={streamStatus === 'connected'}
                      />
                      <Diagnostic
                        icon={<Gauge />}
                        label="Modo / armamento"
                        value={formatNullableText(health.flight_mode)}
                        detail={
                          health.armed === true
                            ? 'VEÍCULO ARMADO'
                            : health.armed === false
                              ? 'Veículo desarmado'
                              : 'Armamento --'
                        }
                        ok={health.armed === false && Boolean(health.flight_mode)}
                      />
                      <Diagnostic
                        icon={<Satellite />}
                        label="GPS"
                        value={`${formatNullableText(health.gps_fix)} · ${formatOptionalNumber(health.satellites)} satélites`}
                        detail={
                          minimumSatellites === null
                            ? 'Mínimo do backend indisponível'
                            : `Mínimo do backend: fix 3D e ${minimumSatellites} satélites`
                        }
                        ok={
                          health.satellites !== null &&
                          minimumSatellites !== null &&
                          health.satellites >= minimumSatellites &&
                          isGpsFixValid(health.gps_fix)
                        }
                      />
                      <Diagnostic
                        icon={<Activity />}
                        label="EKF"
                        value={
                          health.ekf_ok === true
                            ? 'Estimativa válida'
                            : health.ekf_ok === false
                              ? 'Estimativa inválida'
                              : '--'
                        }
                        detail="Não contornar falhas de EKF"
                        ok={health.ekf_ok === true}
                      />
                      <Diagnostic
                        icon={<BatteryCharging />}
                        label="Bateria"
                        value={`${formatPercent(health.battery_percent)}${health.battery_voltage !== null ? ` · ${formatOptionalNumber(health.battery_voltage, { maximumFractionDigits: 2 })} V` : ''}`}
                        detail={
                          minimumBattery === null
                            ? 'Mínimo do backend indisponível'
                            : `Mínimo do backend: ${minimumBattery}%`
                        }
                        ok={
                          health.battery_percent !== null &&
                          minimumBattery !== null &&
                          health.battery_percent >= minimumBattery
                        }
                      />
                      <Diagnostic
                        icon={<MapPinned />}
                        label="Origem"
                        value={
                          health.origin_known === true
                            ? 'Origem conhecida'
                            : health.origin_known === false
                              ? 'Origem desconhecida'
                              : '--'
                        }
                        detail="Necessária para retorno seguro"
                        ok={health.origin_known === true}
                      />
                      <Diagnostic
                        icon={<ShieldCheck />}
                        label="Geofence"
                        value={
                          health.geofence_enabled === true
                            ? 'Habilitada'
                            : health.geofence_enabled === false
                              ? 'Desabilitada'
                              : '--'
                        }
                        detail="Nunca desabilitar para contornar operação"
                        ok={health.geofence_enabled === true}
                      />
                      <Diagnostic
                        icon={<RefreshCw />}
                        label="RTL"
                        value={
                          health.rtl_configured === true
                            ? 'Configurado'
                            : health.rtl_configured === false
                              ? 'Não configurado'
                              : '--'
                        }
                        detail="Área de retorno ainda exige conferência humana"
                        ok={health.rtl_configured === true}
                      />
                      <Diagnostic
                        icon={<Clock3 />}
                        label="Última amostra"
                        value={formatDateTime(health.measured_at)}
                        detail={`Recebida ${formatDateTime(health.received_at)} · ${health.is_stale ? 'DADO VENCIDO' : 'fresca segundo a API'} · HB ${formatDateTime(health.last_heartbeat_at)}`}
                        ok={!health.is_stale && Boolean(health.received_at)}
                      />
                    </div>

                    {health.connected !== true ||
                    health.heartbeat_ok !== true ||
                    health.is_stale ? (
                      <Feedback tone="error" className="page-feedback">
                        Pixhawk/gateway offline ou sem leitura atual. Motivo:{' '}
                        {health.connection_error ||
                          'motivo específico não informado pelo gateway.'}
                      </Feedback>
                    ) : null}

                    {health.preflight_messages.length > 0 ? (
                      <div className="preflight-messages">
                        <h3>Mensagens de pré-arm</h3>
                        {health.preflight_messages.map((message) => (
                          <Feedback tone="error" key={message}>
                            {message}
                          </Feedback>
                        ))}
                      </div>
                    ) : health.preflight_ok === true ? (
                      <p className="preflight-clear">
                        <CheckCircle2 size={18} /> Nenhuma mensagem de pré-arm
                        informada nesta amostra.
                      </p>
                    ) : (
                      <Feedback tone="warning" className="page-feedback">
                        Mensagens de pré-arm indisponíveis nesta amostra.
                      </Feedback>
                    )}
                  </>
                )}
              </Card>
            );
          })}
        </div>
      ) : null}
    </>
  );
}

function Diagnostic({
  icon,
  label,
  value,
  detail,
  ok,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  ok: boolean;
}) {
  return (
    <article
      className={`diagnostic ${ok ? 'diagnostic--ok' : 'diagnostic--blocked'}`}
    >
      <span className="diagnostic__icon">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
        <p>{detail}</p>
      </div>
      <span className="diagnostic__result">{ok ? 'OK' : 'BLOQUEIO'}</span>
    </article>
  );
}
