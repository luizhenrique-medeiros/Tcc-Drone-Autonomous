import {
  Activity,
  BatteryCharging,
  CheckCircle2,
  Clock3,
  Gauge,
  MapPinned,
  RefreshCw,
  Radio,
  Satellite,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import { useCallback, useEffect } from 'react';
import {
  Button,
  Card,
  Feedback,
  PageHeader,
  StateView,
  StatusBadge,
} from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { adminApi, appConfig, type Vehicle, type VehicleHealth } from '../../services';
import { formatDateTime } from '../../utils/format';
import { isVehicleReadyForAuthorization } from '../missions/vehicle-readiness';

interface VehicleReading {
  vehicle: Vehicle;
  health: VehicleHealth | null;
}

export function VehiclesPage() {
  const loader = useCallback(async (): Promise<VehicleReading[]> => {
    const vehicles = await adminApi.listVehicles();
    return Promise.all(
      vehicles.map(async (vehicle) => ({
        vehicle,
        health: await adminApi.getVehicleHealth(vehicle.id).catch(() => null),
      })),
    );
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

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
          <Button variant="secondary" onClick={() => void reload()} loading={isLoading}>
            <RefreshCw size={17} /> Atualizar agora
          </Button>
        }
      />
      <Feedback tone="info" className="page-feedback">
        Atualização automática a cada 10 segundos. A autorização usa uma nova validação no backend/gateway e não confia apenas nesta tela.
      </Feedback>
      {isLoading && !data ? <StateView state="loading" /> : null}
      {error && !data ? (
        <StateView state="error" description={error} actionLabel="Tentar novamente" onAction={() => void reload()} />
      ) : null}
      {data?.length === 0 ? <StateView state="empty" title="Nenhum veículo cadastrado" description="Cadastre o veículo no backend antes da operação." /> : null}
      {data ? (
        <div className="vehicles-stack">
          {data.map(({ vehicle, health }) => (
            <Card
              key={vehicle.id}
              title={
                <div className="vehicle-title">
                  <span><Radio size={22} /></span>
                  <div><h2>{vehicle.name}</h2><small>{vehicle.system}</small></div>
                </div>
              }
              action={<StatusBadge status={vehicle.status} />}
            >
              {!health ? (
                <StateView state="error" compact title="Leitura indisponível" description="A autorização de voo está bloqueada para este veículo." />
              ) : (
                <>
                  <div className={`vehicle-readiness ${isVehicleReadyForAuthorization(health) ? 'vehicle-readiness--ok' : 'vehicle-readiness--blocked'}`}>
                    {isVehicleReadyForAuthorization(health) ? <CheckCircle2 size={25} /> : <TriangleAlert size={25} />}
                    <div>
                      <strong>{isVehicleReadyForAuthorization(health) ? 'Leitura atual atende aos mínimos técnicos' : 'Leitura atual possui bloqueios'}</strong>
                      <span>{isVehicleReadyForAuthorization(health) ? 'O checklist humano e a validação do backend ainda são obrigatórios.' : 'Não autorize voo até resolver todos os itens abaixo.'}</span>
                    </div>
                  </div>
                  <div className="diagnostics-grid">
                    <Diagnostic icon={<Radio />} label="Conexão" value={health.connected ? 'Conectado' : 'Desconectado'} detail={health.heartbeat_ok ? 'Heartbeat dentro do prazo' : 'Heartbeat ausente'} ok={health.connected && health.heartbeat_ok} />
                    <Diagnostic icon={<Gauge />} label="Modo / armamento" value={health.flight_mode} detail={health.armed ? 'VEÍCULO ARMADO' : 'Veículo desarmado'} ok={!health.armed} />
                    <Diagnostic icon={<Satellite />} label="GPS" value={`${health.gps_fix} · ${health.satellites} satélites`} detail="Mínimo operacional: 10 satélites" ok={health.satellites >= 10} />
                    <Diagnostic icon={<Activity />} label="EKF" value={health.ekf_ok ? 'Estimativa válida' : 'Estimativa inválida'} detail="Não contornar falhas de EKF" ok={health.ekf_ok} />
                    <Diagnostic icon={<BatteryCharging />} label="Bateria" value={`${health.battery_percent}%${health.battery_voltage ? ` · ${health.battery_voltage} V` : ''}`} detail="Mínimo configurado: 40%" ok={health.battery_percent >= 40} />
                    <Diagnostic icon={<MapPinned />} label="Origem" value={health.origin_known ? 'Origem conhecida' : 'Origem desconhecida'} detail="Necessária para retorno seguro" ok={health.origin_known} />
                    <Diagnostic icon={<ShieldCheck />} label="Geofence" value={health.geofence_enabled ? 'Habilitada' : 'Desabilitada'} detail="Nunca desabilitar para contornar operação" ok={health.geofence_enabled} />
                    <Diagnostic icon={<RefreshCw />} label="RTL" value={health.rtl_configured ? 'Configurado' : 'Não configurado'} detail="Área de retorno ainda exige conferência humana" ok={health.rtl_configured} />
                    <Diagnostic icon={<Clock3 />} label="Última amostra" value={formatDateTime(health.measured_at)} detail={`Relato do veículo: ${vehicle.id}`} ok={Date.now() - Date.parse(health.measured_at) < 60_000 || appConfig.demoMode} />
                  </div>
                  {health.preflight_messages.length > 0 ? (
                    <div className="preflight-messages">
                      <h3>Mensagens de pré-arm</h3>
                      {health.preflight_messages.map((message) => <Feedback tone="error" key={message}>{message}</Feedback>)}
                    </div>
                  ) : (
                    <p className="preflight-clear"><CheckCircle2 size={18} /> Nenhuma mensagem de pré-arm informada nesta amostra.</p>
                  )}
                </>
              )}
            </Card>
          ))}
        </div>
      ) : null}
    </>
  );
}

function Diagnostic({ icon, label, value, detail, ok }: { icon: React.ReactNode; label: string; value: string; detail: string; ok: boolean }) {
  return (
    <article className={`diagnostic ${ok ? 'diagnostic--ok' : 'diagnostic--blocked'}`}>
      <span className="diagnostic__icon">{icon}</span>
      <div><small>{label}</small><strong>{value}</strong><p>{detail}</p></div>
      <span className="diagnostic__result">{ok ? 'OK' : 'BLOQUEIO'}</span>
    </article>
  );
}
