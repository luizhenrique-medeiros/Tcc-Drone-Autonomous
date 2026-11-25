import { ArrowLeft, Download, FileCheck2, MapPin, Navigation, Radio, RefreshCw, Route } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { SatelliteMap } from '../../components/SatelliteMap';
import { Button, Card, Feedback, Modal, PageHeader, StateView, StatusBadge } from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { useOperationsStream } from '../../hooks/useOperationsStream';
import { adminApi, getErrorMessage } from '../../services';
import { formatCoordinate, formatDateTime, formatDistance, shortId } from '../../utils/format';
import { FlightTrackingPanel } from '../telemetry/FlightTrackingPanel';

export function MissionPage() {
  const { missionId = '' } = useParams();
  const loader = useCallback(async () => {
    const mission = await adminApi.getMission(missionId);
    const order = await adminApi.getOrder(mission.order_id);
    return { mission, order };
  }, [missionId]);
  const { data, isLoading, error, reload, setData } = useAsyncData(loader);
  useOperationsStream(() => void reload());
  const [isActing, setIsActing] = useState(false);
  const [actionError, setActionError] = useState('');
  const [success, setSuccess] = useState('');
  const [qgcDraftOpen, setQgcDraftOpen] = useState(false);
  const [homeAmsl, setHomeAmsl] = useState('');
  const [qgcReviewOpen, setQgcReviewOpen] = useState(false);
  const [qgcPlan, setQgcPlan] = useState<File | null>(null);

  if (isLoading && !data) return <StateView state="loading" />;
  if (error && !data) {
    return <StateView state="error" description={error} actionLabel="Tentar novamente" onAction={() => void reload()} />;
  }
  if (!data) return null;

  const { mission, order } = data;
  const reviewStatus = mission.qgroundcontrol_review_status;
  const mayRegisterReview = ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER', 'UNDER_REVIEW', 'READY_FOR_AUTHORIZATION'].includes(mission.status);
  const manualAmsl = homeAmsl.trim() ? Number(homeAmsl) : undefined;
  const invalidAmsl = manualAmsl !== undefined &&
    (!Number.isFinite(manualAmsl) || manualAmsl < -1000 || manualAmsl > 100000);

  const runFileAction = async (action: () => Promise<void>) => {
    setIsActing(true);
    setActionError('');
    setSuccess('');
    try {
      await action();
    } catch (actionError) {
      setActionError(getErrorMessage(actionError));
    } finally {
      setIsActing(false);
    }
  };

  const handleDraftDownload = () => runFileAction(async () => {
    if (invalidAmsl || !mission.file_hash) return;
    const filename = await adminApi.downloadQgcPlan(mission.id, mission.version, mission.file_hash, manualAmsl);
    setQgcDraftOpen(false);
    setSuccess(`Arquivo ${filename} baixado. Abra no QGroundControl em Plan → Open e revise a missão.`);
    await reload();
  });

  const handleQgcReview = () => runFileAction(async () => {
    if (!qgcPlan || !mission.file_hash) return;
    if (qgcPlan.size > 65536) throw new Error('O arquivo .plan excede 64 KiB.');
    const result = await adminApi.recordQgcReview(mission.id, mission.version, mission.file_hash, await qgcPlan.text());
    setData({ ...data, mission: { ...mission, qgroundcontrol_review_status: 'CURRENT' } });
    setQgcReviewOpen(false);
    setQgcPlan(null);
    setSuccess(`Plano revisado registrado (${result.plan_sha256}).`);
    await reload();
  });

  const handleReviewedPlanDownload = () => runFileAction(async () => {
    const filename = await adminApi.downloadReviewedQgcPlan(mission.id);
    setSuccess(`Arquivo ${filename} baixado. No QGroundControl, use Plan → Open para carregar a revisão.`);
  });

  return (
    <>
      <Link className="back-link" to={`/orders/${order.id}`}>
        <ArrowLeft size={17} /> Voltar ao pedido #{shortId(order.id)}
      </Link>
      <PageHeader
        eyebrow="Planejamento"
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
      {actionError && !qgcDraftOpen && !qgcReviewOpen ? (
        <Feedback tone="error" className="page-feedback">{actionError}</Feedback>
      ) : null}

      <div className="mission-layout">
        <div className="stack">
          <Card title="Rota planejada">
            <SatelliteMap points={[mission.origin, mission.destination]} title="Origem e destino do plano" height={390} />
            <div className="mission-facts">
              <div><span><Route size={18} /></span><small>Distância estimada</small><strong>{formatDistance(mission.estimated_distance_m)}</strong></div>
              <div><span><Navigation size={18} /></span><small>Altitude relativa ao Home</small><strong>{mission.altitude_m} m</strong></div>
              <div><span><MapPin size={18} /></span><small>Destino</small><strong>{mission.destination.label ?? 'Ponto de entrega'}</strong></div>
              <div><span><FileCheck2 size={18} /></span><small>Versão</small><strong>v{mission.version}</strong></div>
            </div>
          </Card>
        </div>

        <aside className="stack mission-side">
          <Card title="Plano para QGroundControl">
            <div className="decision-actions mission-actions">
              {reviewStatus === 'CURRENT' ? (
                <Button variant="primary" loading={isActing} onClick={() => void handleReviewedPlanDownload()}>
                  <Download size={17} /> Baixar plano revisado para o QGroundControl
                </Button>
              ) : null}
              {reviewStatus === 'OUTDATED' ? (
                <Feedback tone="warning">A revisão é de uma versão anterior. Registre o arquivo da versão atual.</Feedback>
              ) : null}
              <Button disabled={isActing || !mission.file_hash} onClick={() => {
                setActionError('');
                setHomeAmsl('');
                setQgcDraftOpen(true);
              }}>
                <Download size={17} /> Baixar missão para QGroundControl
              </Button>
              {mayRegisterReview ? (
                <Button variant="secondary" disabled={!mission.file_hash || isActing} onClick={() => {
                  setActionError('');
                  setQgcPlan(null);
                  setQgcReviewOpen(true);
                }}>
                  <FileCheck2 size={17} /> Registrar arquivo revisado
                </Button>
              ) : null}
              <p>Abra o .plan em Plan → Open. A revisão operacional, o upload ao veículo e a operação de voo são feitos no QGroundControl.</p>
            </div>
          </Card>
          <Card title="Integridade do plano">
            <dl className="data-list single-column">
              <div><dt>Destino final</dt><dd className="mono">{formatCoordinate(mission.destination.latitude)}, {formatCoordinate(mission.destination.longitude)}</dd></div>
              <div><dt>Origem planejada</dt><dd className="mono">{formatCoordinate(mission.origin.latitude)}, {formatCoordinate(mission.origin.longitude)}</dd></div>
              <div><dt>Arquivo exportado nesta revisão</dt><dd>{mission.qgroundcontrol_plan_exported_at ? formatDateTime(mission.qgroundcontrol_plan_exported_at) : 'Pendente'}</dd></div>
              <div><dt>Revisão registrada</dt><dd>{reviewStatus === 'CURRENT' ? `Versão ${mission.version}` : reviewStatus === 'OUTDATED' ? 'Versão anterior' : 'Pendente'}</dd></div>
            </dl>
            <Link className="button button--secondary" to={`/operations?mission=${mission.id}`}>
              <Radio size={17} /> Abrir telemetria
            </Link>
          </Card>
        </aside>
      </div>

      <FlightTrackingPanel key={mission.id} mission={mission} />

      <Modal open={qgcDraftOpen} title="Baixar missão para QGroundControl" onClose={() => setQgcDraftOpen(false)} closeDisabled={isActing}
        footer={<><Button variant="secondary" onClick={() => setQgcDraftOpen(false)} disabled={isActing}>Cancelar</Button>
          <Button onClick={() => void handleDraftDownload()} loading={isActing} disabled={invalidAmsl}>Baixar .plan</Button></>}>
        <div className="stack">
          <ol>
            <li>Decolagem na origem planejada da missão.</li>
            <li>Um waypoint no ponto de entrega do pedido, com espera de 5 segundos.</li>
            <li><strong>Return To Launch (RTL)</strong>.</li>
          </ol>
          <div className="field">
            <label htmlFor="qgc-home-amsl">Altitude AMSL da origem em metros (opcional)</label>
            <input id="qgc-home-amsl" className="input" type="number" min="-1000" max="100000" step="any"
              value={homeAmsl} onChange={(event) => setHomeAmsl(event.target.value)} disabled={isActing} />
            <small>Se estiver em branco, confira a altitude do Home planejado no QGroundControl.</small>
          </div>
          {actionError ? <Feedback tone="error">{actionError}</Feedback> : null}
        </div>
      </Modal>
      <Modal open={qgcReviewOpen} title="Registrar plano revisado no QGroundControl" onClose={() => setQgcReviewOpen(false)} closeDisabled={isActing}
        footer={<><Button variant="secondary" onClick={() => setQgcReviewOpen(false)} disabled={isActing}>Cancelar</Button>
          <Button onClick={() => void handleQgcReview()} loading={isActing} disabled={!qgcPlan || isActing}>Registrar plano revisado</Button></>}>
        <div className="stack">
          <p>Selecione o arquivo que você revisou e salvou no QGroundControl.</p>
          <div className="field">
            <label htmlFor="qgc-review-file">Arquivo .plan revisado</label>
            <input id="qgc-review-file" type="file" accept=".plan,application/json" disabled={isActing}
              onChange={(event) => setQgcPlan(event.target.files?.[0] ?? null)} />
          </div>
          {actionError ? <Feedback tone="error">{actionError}</Feedback> : null}
        </div>
      </Modal>
    </>
  );
}
