import {
  AlertOctagon,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileCheck2,
  MapPin,
  Navigation,
  Pause,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  Route,
  Satellite,
  ShieldCheck,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { OperationalSourceBadge } from '../../components/OperationalSourceBadge';
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
import { useOperationsStream } from '../../hooks/useOperationsStream';
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
import { AutomaticPreflightChecks } from './AutomaticPreflightChecks';
import {
  authorizationTitle,
  authorizationUsageMessage,
} from './authorization-presentation';
import { FlightAuthorizationDialog } from './FlightAuthorizationDialog';
import { getMissionReadiness } from './vehicle-readiness';

interface MissionPageData {
  mission: Mission;
  order: Order;
  vehicle: Vehicle | null;
  health: VehicleHealth | null;
  healthError: string;
}

const flowStages = [
  { label: 'Gerada', statuses: ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER'] },
  { label: 'Revisão', statuses: ['UNDER_REVIEW'] },
  { label: 'Pronta', statuses: ['READY_FOR_AUTHORIZATION'] },
  {
    label: 'Autorizada',
    statuses: ['AUTHORIZED', 'UPLOADING', 'UPLOADED'],
  },
  { label: 'Verificada', statuses: ['VERIFIED'] },
  {
    label: 'Execução',
    statuses: [
      'EXECUTING',
      'PAUSED',
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
    let health: VehicleHealth | null = null;
    let healthError = '';
    if (vehicle) {
      try {
        health = await adminApi.getVehicleHealth(vehicle.id);
      } catch (loadError) {
        healthError = getErrorMessage(loadError);
      }
    }
    return { mission, order, vehicle, health, healthError };
  }, [missionId]);
  const { data, isLoading, error, reload, setData } = useAsyncData(loader);
  useOperationsStream(() => void reload());
  const [isActing, setIsActing] = useState(false);
  const [actionError, setActionError] = useState('');
  const [success, setSuccess] = useState('');
  const [authorizationOpen, setAuthorizationOpen] = useState(false);
  const [criticalAction, setCriticalAction] = useState<
    'start' | 'pause' | 'continue' | 'rtl' | 'abort' | null
  >(null);
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

  const { mission, order, vehicle, health, healthError } = data;
  const readiness = getMissionReadiness(mission, health);
  const activeStage = getStage(mission.status);
  const canStartReview = ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER'].includes(
    mission.status,
  );
  const canFinishReview = mission.status === 'UNDER_REVIEW';
  const canAuthorize = mission.status === 'READY_FOR_AUTHORIZATION';
  const canAbort = [
    'UPLOADING',
    'UPLOADED',
    'VERIFIED',
    'EXECUTING',
    'PAUSED',
    'DESTINATION_REACHED',
    'DELIVERY_CONFIRMED',
    'RETURNING',
  ].includes(mission.status);
  const canRequestRtl = [
    'EXECUTING',
    'PAUSED',
    'DESTINATION_REACHED',
    'DELIVERY_CONFIRMED',
    'RETURNING',
  ].includes(mission.status);
  const canRequestStart = mission.status === 'VERIFIED';
  const canRequestPause = [
    'EXECUTING',
    'DESTINATION_REACHED',
    'DELIVERY_CONFIRMED',
    'RETURNING',
  ].includes(mission.status);
  const canRequestContinue = mission.status === 'PAUSED';
  const canIntervene =
    canAbort ||
    canRequestRtl ||
    canRequestStart ||
    canRequestPause ||
    canRequestContinue;
  const flightCommandsEnabled = health?.flight_commands_enabled === true;
  const missionStartEnabled = health?.mission_start_enabled === true;
  const missionVehicleMatchesHealth =
    mission.vehicle_id !== undefined &&
    vehicle?.id === mission.vehicle_id &&
    health?.vehicle_id === mission.vehicle_id;
  const startCommandBlockedReason = !flightCommandsEnabled
    ? 'ALLOW_FLIGHT_COMMANDS está desabilitado no gateway.'
    : !missionStartEnabled
      ? 'ALLOW_MISSION_START está desabilitado no gateway.'
      : !missionVehicleMatchesHealth
        ? 'A leitura de saúde não pertence ao veículo vinculado à missão.'
        : health?.is_stale
          ? 'A leitura de saúde está vencida; atualize o gateway antes de solicitar START.'
          : health?.connected !== true || health.heartbeat_ok !== true
            ? 'Gateway/Pixhawk está sem conexão ou heartbeat atual.'
            : health.armed !== true
              ? 'O operador ainda não confirmou armamento físico.'
              : null;

  const updateMission = (next: Mission) => setData({ ...data, mission: next });

  const openAuthorization = async () => {
    setIsActing(true);
    setActionError('');
    setSuccess('');
    try {
      const refreshed = await loader();
      setData(refreshed);
      const refreshedReadiness = getMissionReadiness(
        refreshed.mission,
        refreshed.health,
      );
      if (
        refreshed.mission.status !== 'READY_FOR_AUTHORIZATION' ||
        !refreshedReadiness.ready
      ) {
        setActionError(
          refreshedReadiness.blockers.join(' ') ||
            'A missão não está mais pronta para autorização.',
        );
        return;
      }
      setAuthorizationOpen(true);
    } catch (refreshError) {
      setActionError(getErrorMessage(refreshError));
    } finally {
      setIsActing(false);
    }
  };

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
    const successMessages = {
      start:
        'Solicitação START registrada. O gateway ainda revalida armamento, preflight e flags locais.',
      pause: 'Solicitação de pausa registrada; aguarde o COMMAND_ACK do ArduPilot.',
      continue: 'Solicitação de continuação registrada; aguarde o COMMAND_ACK do ArduPilot.',
      rtl: 'Solicitação de RTL registrada. A execução depende da validação do gateway e do estado físico do veículo.',
      abort: 'Solicitação de abortamento registrada na missão.',
    } as const;
    await runMissionAction(
      () => {
        if (action === 'rtl') {
          return adminApi.requestRtl(mission.id, criticalReason);
        }
        if (action === 'abort') {
          return adminApi.abortMission(mission.id, criticalReason);
        }
        return adminApi.requestMissionCommand(
          mission.id,
          action.toUpperCase() as 'START' | 'PAUSE' | 'CONTINUE',
          criticalReason,
        );
      },
      successMessages[action],
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
      {healthError ? (
        <Feedback tone="error" className="page-feedback">
          Falha ao atualizar a saúde: {healthError}. A autorização permanece bloqueada.
        </Feedback>
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
                title="Autorizar missão"
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
                  <Feedback tone={readiness.ready ? 'success' : 'error'}>
                    {readiness.ready
                      ? readiness.warnings.length > 0
                        ? 'Sem bloqueios técnicos. Revise os avisos e faça as três confirmações humanas.'
                        : 'Verificações automáticas aprovadas. Ainda são necessárias três confirmações humanas.'
                      : `Autorização bloqueada: ${readiness.blockers.join(' ')}`}
                  </Feedback>
                  <Button
                    loading={isActing}
                    onClick={() => void openAuthorization()}
                  >
                    <ShieldCheck size={18} />{' '}
                    {readiness.ready
                      ? 'Autorizar missão'
                      : 'Revalidar para autorizar'}
                  </Button>
                </>
              ) : null}
              {mission.authorization ? (
                <div className="authorization-record">
                  <ShieldCheck size={25} />
                  <div>
                    <strong>{authorizationTitle(mission.authorization)}</strong>
                    <span>
                      Por {mission.authorization.admin_name}
                      {mission.authorization.administrator_id
                        ? ` · Admin #${shortId(mission.authorization.administrator_id)}`
                        : ''}
                    </span>
                    <span>Operador: {mission.authorization.operator_name}</span>
                    <span>
                      Emitida: {formatDateTime(mission.authorization.authorized_at)}
                    </span>
                    <span>Expira: {formatDateTime(mission.authorization.expires_at)}</span>
                    {mission.authorization.mission_version ? (
                      <small>Versão autorizada: {mission.authorization.mission_version}</small>
                    ) : null}
                    <small>
                      {authorizationUsageMessage(mission.authorization)}
                    </small>
                  </div>
                </div>
              ) : null}
              {canIntervene ? (
                <>
                  <Link className="button button--secondary" to={`/operations?mission=${mission.id}`}><Radio size={17} /> Abrir telemetria</Link>
                  <div className="critical-actions">
                    {canRequestStart ? <Button variant="primary" disabled={startCommandBlockedReason !== null} title={startCommandBlockedReason ?? undefined} onClick={() => { setCriticalReason(''); setCriticalAction('start'); }}><Play size={17} /> Solicitar START</Button> : null}
                    {canRequestPause ? <Button variant="secondary" disabled={!flightCommandsEnabled} title={!flightCommandsEnabled ? 'ALLOW_FLIGHT_COMMANDS está desabilitado no gateway.' : undefined} onClick={() => { setCriticalReason(''); setCriticalAction('pause'); }}><Pause size={17} /> Pausar missão</Button> : null}
                    {canRequestContinue ? <Button variant="secondary" disabled={!flightCommandsEnabled} title={!flightCommandsEnabled ? 'ALLOW_FLIGHT_COMMANDS está desabilitado no gateway.' : undefined} onClick={() => { setCriticalReason(''); setCriticalAction('continue'); }}><Play size={17} /> Continuar missão</Button> : null}
                    {canRequestRtl ? <Button variant="secondary" onClick={() => { setCriticalReason(''); setCriticalAction('rtl'); }}><RotateCcw size={17} /> Solicitar RTL</Button> : null}
                    {canAbort ? <Button variant="danger" onClick={() => { setCriticalReason(''); setCriticalAction('abort'); }}><AlertOctagon size={17} /> Abortar missão</Button> : null}
                  </div>
                </>
              ) : null}
            </div>
          </Card>

          <Card
            title="Verificações automáticas"
            action={
              <div className="cluster">
                {health ? <OperationalSourceBadge {...health} /> : null}
                <Link to="/vehicles">Diagnóstico</Link>
              </div>
            }
          >
            <AutomaticPreflightChecks mission={mission} health={health} />
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
        title={
          {
            start: 'Solicitar início explícito da missão',
            pause: 'Solicitar pausa da missão',
            continue: 'Solicitar continuação da missão',
            rtl: 'Solicitar retorno ao ponto de origem',
            abort: 'Abortar missão',
          }[criticalAction ?? 'abort']
        }
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
