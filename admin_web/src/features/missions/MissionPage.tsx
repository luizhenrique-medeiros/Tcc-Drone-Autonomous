import {
  AlertOctagon,
  ArrowLeft,
  BatteryCharging,
  CheckCircle2,
  Download,
  FileCheck2,
  Gauge,
  MapPin,
  Navigation,
  Radio,
  RefreshCw,
  RotateCcw,
  Route,
  Satellite,
  ShieldCheck,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { SatelliteMap } from '../../components/SatelliteMap';
import {
  Button,
  Card,
  Feedback,
  Modal,
  PageHeader,
  StateView,
  StatusBadge,
} from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import {
  adminApi,
  getErrorMessage,
  type FlightAuthorizationInput,
  type Mission,
  type Order,
  type Vehicle,
  type VehicleHealth,
} from '../../services';
import {
  formatCoordinate,
  formatDateTime,
  formatDistance,
  shortId,
} from '../../utils/format';
import { FlightAuthorizationDialog } from './FlightAuthorizationDialog';
import { isVehicleReadyForAuthorization } from './vehicle-readiness';

interface MissionPageData {
  mission: Mission;
  order: Order;
  vehicle: Vehicle | null;
  health: VehicleHealth | null;
}

const flowStages = [
  { label: 'Gerada', statuses: ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER'] },
  { label: 'Revisão', statuses: ['UNDER_REVIEW'] },
  { label: 'Pronta', statuses: ['READY_FOR_AUTHORIZATION'] },
  { label: 'Autorizada', statuses: ['AUTHORIZED', 'UPLOADING', 'UPLOADED'] },
  {
    label: 'Execução',
    statuses: [
      'EXECUTING',
      'DESTINATION_REACHED',
      'DELIVERY_CONFIRMED',
      'RETURNING',
    ],
  },
  { label: 'Concluída', statuses: ['COMPLETED'] },
];

const getStage = (status: Mission['status']) => {
  const index = flowStages.findIndex((stage) => stage.statuses.includes(status));
  return index < 0 ? 0 : index;
};

export function MissionPage() {
  const { missionId = '' } = useParams();
  const loader = useCallback(async (): Promise<MissionPageData> => {
    const mission = await adminApi.getMission(missionId);
    const [order, vehicles] = await Promise.all([
      adminApi.getOrder(mission.order_id),
      adminApi.listVehicles(),
    ]);
    const vehicle =
      vehicles.find((item) => item.id === mission.vehicle_id) ?? vehicles[0] ?? null;
    const health = vehicle
      ? await adminApi.getVehicleHealth(vehicle.id).catch(() => null)
      : null;
    return { mission, order, vehicle, health };
  }, [missionId]);
  const { data, isLoading, error, reload, setData } = useAsyncData(loader);
  const [isActing, setIsActing] = useState(false);
  const [actionError, setActionError] = useState('');
  const [success, setSuccess] = useState('');
  const [authorizationOpen, setAuthorizationOpen] = useState(false);
  const [criticalAction, setCriticalAction] = useState<'rtl' | 'abort' | null>(null);
  const [criticalReason, setCriticalReason] = useState('');

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

  const { mission, order, vehicle, health } = data;
  const activeStage = getStage(mission.status);
  const canStartReview = ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER'].includes(
    mission.status,
  );
  const canFinishReview = mission.status === 'UNDER_REVIEW';
  const canAuthorize = mission.status === 'READY_FOR_AUTHORIZATION';
  const canIntervene = ['AUTHORIZED', 'UPLOADING', 'UPLOADED', 'EXECUTING'].includes(
    mission.status,
  );

  const updateMission = (next: Mission) => setData({ ...data, mission: next });

  const runMissionAction = async (
    action: () => Promise<Mission>,
    successMessage: string,
  ) => {
    setIsActing(true);
    setActionError('');
    setSuccess('');
    try {
      updateMission(await action());
      setSuccess(successMessage);
    } catch (missionError) {
      setActionError(getErrorMessage(missionError));
    } finally {
      setIsActing(false);
    }
  };

  const handleExport = async () => {
    setIsActing(true);
    setActionError('');
    try {
      await adminApi.exportMission(mission.id);
      setSuccess('Arquivo compatível com Mission Planner exportado. Revise-o externamente antes de registrar a revisão.');
    } catch (exportError) {
      setActionError(getErrorMessage(exportError));
    } finally {
      setIsActing(false);
    }
  };

  const handleAuthorize = async (input: FlightAuthorizationInput) => {
    setIsActing(true);
    setActionError('');
    try {
      updateMission(await adminApi.authorizeFlight(mission.id, input));
      setAuthorizationOpen(false);
      setSuccess('Autorização de uso único criada. O gateway ainda deve validar prazo, versão e saúde antes do upload.');
    } catch (authorizationError) {
      setActionError(getErrorMessage(authorizationError));
    } finally {
      setIsActing(false);
    }
  };

  const handleCriticalAction = async () => {
    if (!criticalAction) return;
    const action = criticalAction;
    await runMissionAction(
      () =>
        action === 'rtl'
          ? adminApi.requestRtl(mission.id, criticalReason)
          : adminApi.abortMission(mission.id, criticalReason),
      action === 'rtl'
        ? 'Solicitação de RTL registrada. A execução depende da validação do gateway e do estado físico do veículo.'
        : 'Solicitação de abortamento registrada na missão.',
    );
    setCriticalAction(null);
  };

  return (
    <>
      <Link className="back-link" to={`/orders/${order.id}`}>
        <ArrowLeft size={17} /> Voltar ao pedido #{shortId(order.id)}
      </Link>
      <PageHeader
        eyebrow="Segunda autorização"
        title={`Missão #${shortId(mission.id)}`}
        description={`Versão ${mission.version} · criada em ${formatDateTime(mission.created_at)} · vinculada ao pedido #${shortId(order.id)}.`}
        actions={
          <>
            <StatusBadge status={mission.status} />
            <Button variant="secondary" size="small" onClick={() => void reload()} loading={isLoading}>
              <RefreshCw size={16} /> Atualizar
            </Button>
          </>
        }
      />
      {success ? <Feedback tone="success" className="page-feedback">{success}</Feedback> : null}
      {actionError && !authorizationOpen && !criticalAction ? (
        <Feedback tone="error" className="page-feedback">{actionError}</Feedback>
      ) : null}

      <ol className="mission-progress" aria-label="Progresso da missão">
        {flowStages.map((stage, index) => (
          <li
            key={stage.label}
            className={
              index < activeStage
                ? 'mission-progress__done'
                : index === activeStage
                  ? 'mission-progress__active'
                  : ''
            }
          >
            <span>{index < activeStage ? <CheckCircle2 size={17} /> : index + 1}</span>
            <strong>{stage.label}</strong>
          </li>
        ))}
      </ol>

      <div className="mission-layout">
        <div className="stack">
          <Card
            title="Rota e waypoints"
            action={<span className="analysis-label"><Satellite size={16} /> Revisão visual obrigatória</span>}
          >
            <SatelliteMap points={mission.waypoints} title="Traçado planejado" height={390} />
            <div className="mission-facts">
              <div><span><Route size={18} /></span><small>Distância total</small><strong>{formatDistance(mission.estimated_distance_m)}</strong></div>
              <div><span><Navigation size={18} /></span><small>Altitude configurada</small><strong>{mission.altitude_m} m</strong></div>
              <div><span><MapPin size={18} /></span><small>Waypoints</small><strong>{mission.waypoints.length}</strong></div>
              <div><span><FileCheck2 size={18} /></span><small>Versão</small><strong>v{mission.version}</strong></div>
            </div>
          </Card>

          <Card title="Sequência da missão">
            <div className="table-wrap">
              <table className="data-table waypoints-table">
                <thead>
                  <tr><th>#</th><th>Comando</th><th>Latitude</th><th>Longitude</th><th>Altitude</th><th>Finalidade</th></tr>
                </thead>
                <tbody>
                  {mission.waypoints.map((waypoint) => (
                    <tr key={waypoint.id}>
                      <td><span className="waypoint-index">{waypoint.sequence}</span></td>
                      <td><strong>{waypoint.command}</strong></td>
                      <td className="mono">{formatCoordinate(waypoint.latitude)}</td>
                      <td className="mono">{formatCoordinate(waypoint.longitude)}</td>
                      <td>{waypoint.altitude_m} m</td>
                      <td>{waypoint.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <aside className="stack mission-side">
          <Card title="Revisão no Mission Planner">
            <div className="review-flow">
              <ReviewStep
                done={Boolean(mission.exported_at) || activeStage > 0}
                number="1"
                title="Exportar arquivo"
                detail="Baixe a versão exata da missão."
              />
              <ReviewStep
                done={Boolean(mission.reviewed_at) || activeStage > 1}
                number="2"
                title="Revisar externamente"
                detail="Abra no Mission Planner e confira o traçado."
              />
              <ReviewStep
                done={activeStage > 2}
                number="3"
                title="Autorizar o voo"
                detail="Somente após saúde e checklist válidos."
              />
            </div>
            <div className="decision-actions mission-actions">
              {canStartReview ? (
                <>
                  <Button variant="secondary" onClick={() => void handleExport()} loading={isActing}>
                    <Download size={17} /> Baixar .waypoints
                  </Button>
                  <Button
                    onClick={() =>
                      void runMissionAction(
                        () => adminApi.markMissionUnderReview(mission.id),
                        'Abertura no Mission Planner registrada. Conclua a revisão antes de avançar.',
                      )
                    }
                    loading={isActing}
                  >
                    <FileCheck2 size={17} /> Registrar abertura no Planner
                  </Button>
                </>
              ) : null}
              {canFinishReview ? (
                <>
                  <Feedback tone="warning">Confirme somente depois de revisar a rota no Mission Planner. O navegador não substitui essa revisão.</Feedback>
                  <Button
                    onClick={() =>
                      void runMissionAction(
                        () => adminApi.markMissionReviewed(mission.id),
                        'Revisão registrada. A missão aguarda a segunda autorização.',
                      )
                    }
                    loading={isActing}
                  >
                    <CheckCircle2 size={17} /> Confirmar revisão operacional
                  </Button>
                </>
              ) : null}
              {canAuthorize ? (
                <>
                  <Feedback tone={isVehicleReadyForAuthorization(health) ? 'success' : 'error'}>
                    {isVehicleReadyForAuthorization(health)
                      ? 'Saúde atual atende aos limites mínimos. Ainda é necessário preencher todo o checklist.'
                      : 'Autorização bloqueada: a leitura do veículo não atende aos limites mínimos.'}
                  </Feedback>
                  <Button
                    variant="warning"
                    disabled={!isVehicleReadyForAuthorization(health)}
                    onClick={() => { setActionError(''); setAuthorizationOpen(true); }}
                  >
                    <ShieldCheck size={18} /> Iniciar autorização de voo
                  </Button>
                </>
              ) : null}
              {mission.authorization ? (
                <div className="authorization-record">
                  <ShieldCheck size={25} />
                  <div>
                    <strong>Autorização de uso único emitida</strong>
                    <span>Por {mission.authorization.admin_name}</span>
                    <span>Operador: {mission.authorization.operator_name}</span>
                    <span>Expira: {formatDateTime(mission.authorization.expires_at)}</span>
                    {mission.authorization.consumed_at ? <small>Consumida em {formatDateTime(mission.authorization.consumed_at)}</small> : <small>Aguardando consumo pelo gateway</small>}
                  </div>
                </div>
              ) : null}
              {canIntervene ? (
                <>
                  <Link className="button button--secondary" to={`/operations?mission=${mission.id}`}><Radio size={17} /> Abrir telemetria</Link>
                  <div className="critical-actions">
                    <Button variant="secondary" onClick={() => { setCriticalReason(''); setCriticalAction('rtl'); }}><RotateCcw size={17} /> Solicitar RTL</Button>
                    <Button variant="danger" onClick={() => { setCriticalReason(''); setCriticalAction('abort'); }}><AlertOctagon size={17} /> Abortar missão</Button>
                  </div>
                </>
              ) : null}
            </div>
          </Card>

          <Card title="Saúde antes do voo" action={<Link to="/vehicles">Diagnóstico</Link>}>
            {!vehicle || !health ? (
              <StateView state="empty" compact title="Sem leitura de saúde" description="A autorização permanece bloqueada." />
            ) : (
              <div className="vehicle-checks">
                <VehicleCheck icon={<Radio />} label="Conexão / heartbeat" value={health.heartbeat_ok ? 'Ativo' : 'Ausente'} ok={health.connected && health.heartbeat_ok} />
                <VehicleCheck icon={<Satellite />} label="GPS / satélites" value={`${health.gps_fix} · ${health.satellites}`} ok={health.satellites >= 10} />
                <VehicleCheck icon={<Gauge />} label="EKF / armamento" value={`${health.ekf_ok ? 'EKF OK' : 'Falha'} · ${health.armed ? 'ARMADO' : 'Desarmado'}`} ok={health.ekf_ok && !health.armed} />
                <VehicleCheck icon={<BatteryCharging />} label="Bateria" value={`${health.battery_percent}%${health.battery_voltage ? ` · ${health.battery_voltage} V` : ''}`} ok={health.battery_percent >= 40} />
                <VehicleCheck icon={<Navigation />} label="Origem / RTL / geofence" value={health.origin_known && health.rtl_configured && health.geofence_enabled ? 'Configurados' : 'Incompleto'} ok={health.origin_known && health.rtl_configured && health.geofence_enabled} />
                <p className="last-update">Leitura: {formatDateTime(health.measured_at)}</p>
              </div>
            )}
          </Card>

          <Card title="Integridade do artefato">
            <dl className="data-list single-column">
              <div><dt>Hash</dt><dd className="mono">{mission.file_hash ?? 'Gerado no backend'}</dd></div>
              <div><dt>Destino final</dt><dd className="mono">{formatCoordinate(mission.destination.latitude)}, {formatCoordinate(mission.destination.longitude)}</dd></div>
              <div><dt>Revisão</dt><dd>{mission.reviewed_at ? `${mission.reviewer_name ?? 'Admin'} · ${formatDateTime(mission.reviewed_at)}` : 'Pendente'}</dd></div>
            </dl>
          </Card>
        </aside>
      </div>

      <FlightAuthorizationDialog
        open={authorizationOpen}
        mission={mission}
        vehicle={vehicle}
        health={health}
        isSubmitting={isActing}
        error={actionError}
        onClose={() => setAuthorizationOpen(false)}
        onSubmit={handleAuthorize}
      />

      <Modal
        open={criticalAction !== null}
        title={criticalAction === 'rtl' ? 'Solicitar retorno ao ponto de origem' : 'Abortar missão'}
        onClose={() => setCriticalAction(null)}
        closeDisabled={isActing}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCriticalAction(null)} disabled={isActing}>Cancelar</Button>
            <Button variant="danger" onClick={() => void handleCriticalAction()} loading={isActing} disabled={criticalReason.trim().length < 10}>
              Confirmar solicitação crítica
            </Button>
          </>
        }
      >
        <div className="stack">
          <Feedback tone="error">
            A solicitação será auditada e enviada ao gateway. O ArduPilot e o operador continuam sendo responsáveis pela resposta segura conforme o estado físico atual.
          </Feedback>
          <div className="field">
            <label htmlFor="critical-reason">Justificativa operacional</label>
            <textarea className="textarea" id="critical-reason" value={criticalReason} onChange={(event) => setCriticalReason(event.target.value)} minLength={10} maxLength={500} />
          </div>
          {actionError ? <Feedback tone="error">{actionError}</Feedback> : null}
        </div>
      </Modal>
    </>
  );
}

function ReviewStep({ done, number, title, detail }: { done: boolean; number: string; title: string; detail: string }) {
  return (
    <div className={`review-step ${done ? 'review-step--done' : ''}`}>
      <span>{done ? <CheckCircle2 size={18} /> : number}</span>
      <div><strong>{title}</strong><small>{detail}</small></div>
    </div>
  );
}

function VehicleCheck({ icon, label, value, ok }: { icon: React.ReactNode; label: string; value: string; ok: boolean }) {
  return (
    <div className="vehicle-check">
      <span>{icon}</span>
      <div><small>{label}</small><strong>{value}</strong></div>
      <span className={`vehicle-check__result ${ok ? 'vehicle-check__result--ok' : ''}`}>{ok ? 'OK' : 'Bloqueio'}</span>
    </div>
  );
}
