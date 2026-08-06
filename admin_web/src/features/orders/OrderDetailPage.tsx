import {
  ArrowLeft,
  Ban,
  Check,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  MapPin,
  Navigation,
  PackageCheck,
  Route,
  UserRound,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
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
import { adminApi, getErrorMessage } from '../../services';
import {
  formatCoordinate,
  formatCurrency,
  formatDateTime,
  formatDistance,
  shortId,
} from '../../utils/format';

export function OrderDetailPage() {
  const { orderId = '' } = useParams();
  const navigate = useNavigate();
  const loader = useCallback(() => adminApi.getOrder(orderId), [orderId]);
  const { data: order, isLoading, error, reload, setData } = useAsyncData(loader);
  const [decisionModal, setDecisionModal] = useState<'approve' | 'reject' | null>(
    null,
  );
  const [approvalConfirmed, setApprovalConfirmed] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [isActing, setIsActing] = useState(false);
  const [actionError, setActionError] = useState('');
  const [success, setSuccess] = useState('');

  if (isLoading && !order) return <StateView state="loading" />;
  if (error && !order) {
    return (
      <StateView
        state="error"
        description={error}
        actionLabel="Tentar novamente"
        onAction={() => void reload()}
      />
    );
  }
  if (!order) return null;

  const canDecide = order.status === 'PENDING_ADMIN_APPROVAL';
  const canPrepare = order.status === 'APPROVED';
  const exactPoint = {
    latitude: order.delivery_point.latitude,
    longitude: order.delivery_point.longitude,
    label: order.delivery_point.label,
  };

  const handleApprove = async () => {
    setIsActing(true);
    setActionError('');
    try {
      setData(await adminApi.approveOrder(order.id));
      setDecisionModal(null);
      setSuccess(
        'Pedido aprovado. A aprovação não autorizou nenhum voo; a missão ainda precisa ser preparada e revisada.',
      );
    } catch (approveError) {
      setActionError(getErrorMessage(approveError));
    } finally {
      setIsActing(false);
    }
  };

  const handleReject = async () => {
    setIsActing(true);
    setActionError('');
    try {
      setData(await adminApi.rejectOrder(order.id, rejectionReason));
      setDecisionModal(null);
      setSuccess('Pedido rejeitado e motivo registrado na trilha de auditoria.');
    } catch (rejectError) {
      setActionError(getErrorMessage(rejectError));
    } finally {
      setIsActing(false);
    }
  };

  const handlePrepareMission = async () => {
    setIsActing(true);
    setActionError('');
    try {
      const mission = await adminApi.prepareMission(order.id);
      navigate(`/missions/${mission.id}`);
    } catch (prepareError) {
      setActionError(getErrorMessage(prepareError));
    } finally {
      setIsActing(false);
    }
  };

  return (
    <>
      <Link className="back-link" to="/orders"><ArrowLeft size={17} /> Voltar para a fila</Link>
      <PageHeader
        eyebrow="Análise administrativa"
        title={`Pedido #${shortId(order.id)}`}
        description={`Enviado em ${formatDateTime(order.created_at)} · coordenadas finais definidas pelo cliente.`}
        actions={<StatusBadge status={order.status} />}
      />
      {success ? <Feedback tone="success" className="page-feedback">{success}</Feedback> : null}
      {actionError && !decisionModal ? (
        <Feedback tone="error" className="page-feedback">{actionError}</Feedback>
      ) : null}

      <div className="order-detail-grid">
        <div className="stack">
          <Card title="Ponto final de entrega" action={<span className="analysis-label"><Navigation size={16} /> Não editável</span>}>
            <SatelliteMap points={[exactPoint]} />
            <div className="location-comparison">
              <article>
                <span className="location-comparison__step">1</span>
                <div>
                  <small>Referência aproximada pesquisada</small>
                  <strong>{order.delivery_point.searched_address ?? 'Não informada'}</strong>
                  {order.delivery_point.approximate_latitude !== undefined ? (
                    <span className="mono">
                      {formatCoordinate(order.delivery_point.approximate_latitude)}, {formatCoordinate(order.delivery_point.approximate_longitude ?? 0)}
                    </span>
                  ) : null}
                </div>
              </article>
              <article className="location-comparison__final">
                <span className="location-comparison__step"><MapPin size={17} /></span>
                <div>
                  <small>2 · Ponto final posicionado manualmente</small>
                  <strong>{order.delivery_point.label ?? 'Ponto sem rótulo'}</strong>
                  <span className="mono">{formatCoordinate(order.delivery_point.latitude)}, {formatCoordinate(order.delivery_point.longitude)}</span>
                </div>
              </article>
            </div>
            <Feedback tone="info">
              O endereço é apenas referência. A missão deve usar exclusivamente a latitude e longitude finais acima. O painel não altera silenciosamente o ponto do cliente.
            </Feedback>
          </Card>

          <Card title="Itens e valores simulados">
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Produto</th><th>Qtd.</th><th>Unitário</th><th>Subtotal</th></tr></thead>
                <tbody>
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td><strong>{item.product_name}</strong></td>
                      <td>{item.quantity}</td>
                      <td>{formatCurrency(item.unit_price)}</td>
                      <td><strong>{formatCurrency(item.subtotal)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="order-totals">
              <span>Subtotal <strong>{formatCurrency(order.subtotal)}</strong></span>
              <span>Entrega <strong>{formatCurrency(order.delivery_fee)}</strong></span>
              <span>Desconto <strong>− {formatCurrency(order.discount)}</strong></span>
              <span className="order-totals__total">Total simulado <strong>{formatCurrency(order.total)}</strong></span>
            </div>
          </Card>
        </div>

        <aside className="stack order-summary-column">
          <Card title="Resumo operacional">
            <div className="summary-facts">
              <SummaryFact icon={<UserRound />} label="Cliente" value={order.customer.name} detail={order.customer.email} />
              <SummaryFact icon={<Clock3 />} label="Distância estimada" value={formatDistance(order.estimated_distance_m)} detail="Valor sujeito à validação da missão" />
              <SummaryFact icon={<CircleDollarSign />} label="Pagamento" value={order.simulated_payment_method.replaceAll('_', ' ')} detail="Registro acadêmico — sem cobrança real" />
              <SummaryFact icon={<PackageCheck />} label="Confirmação do cliente" value={order.delivery_point.customer_confirmed ? 'Ponto confirmado' : 'Não confirmado'} detail={order.delivery_point.controlled_area_confirmed ? 'Cliente declarou área adequada' : 'Área não declarada'} />
            </div>
          </Card>

          <Card title="Instruções de entrega">
            <p className="instruction-box">{order.delivery_point.instructions || 'Nenhuma instrução informada.'}</p>
            {order.delivery_point.reference_address ? <p className="muted reference-address">Referência: {order.delivery_point.reference_address}</p> : null}
          </Card>

          {order.admin_decision ? (
            <Card title="Decisão registrada">
              <div className="decision-record">
                {order.admin_decision.decision === 'APPROVED' ? <CheckCircle2 size={25} /> : <XCircle size={25} />}
                <div>
                  <strong>{order.admin_decision.decision === 'APPROVED' ? 'Pedido aprovado' : 'Pedido rejeitado'}</strong>
                  <span>{order.admin_decision.admin_name} · {formatDateTime(order.admin_decision.created_at)}</span>
                  {order.admin_decision.reason ? <p>{order.admin_decision.reason}</p> : null}
                </div>
              </div>
            </Card>
          ) : null}

          <Card title="Próxima ação">
            {canDecide ? (
              <div className="decision-actions">
                <Feedback tone="warning">
                  Confirme visualmente o ponto, as instruções e a adequação do local antes de decidir.
                </Feedback>
                <Button onClick={() => { setActionError(''); setApprovalConfirmed(false); setDecisionModal('approve'); }}>
                  <Check size={18} /> Aprovar pedido
                </Button>
                <Button variant="danger" onClick={() => { setActionError(''); setRejectionReason(''); setDecisionModal('reject'); }}>
                  <Ban size={18} /> Rejeitar pedido
                </Button>
              </div>
            ) : canPrepare ? (
              <div className="decision-actions">
                <Feedback tone="success">A primeira aprovação foi concluída. Preparar a missão não autoriza seu envio ou execução.</Feedback>
                <Button loading={isActing} onClick={() => void handlePrepareMission()}>
                  <Route size={18} /> Preparar missão
                </Button>
              </div>
            ) : order.mission_id ? (
              <div className="decision-actions">
                <Feedback>O fluxo segue na revisão da missão e, depois, na autorização reforçada de voo.</Feedback>
                <Link className="button" to={`/missions/${order.mission_id}`}><Route size={18} /> Abrir missão</Link>
              </div>
            ) : (
              <p className="muted">Este pedido não possui ação administrativa disponível no estado atual.</p>
            )}
          </Card>
        </aside>
      </div>

      <Modal
        open={decisionModal === 'approve'}
        title="Confirmar aprovação do pedido"
        onClose={() => setDecisionModal(null)}
        closeDisabled={isActing}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDecisionModal(null)} disabled={isActing}>Cancelar</Button>
            <Button onClick={() => void handleApprove()} loading={isActing} disabled={!approvalConfirmed}>Confirmar aprovação</Button>
          </>
        }
      >
        <div className="stack">
          <Feedback tone="warning"><strong>Esta é somente a aprovação do pedido.</strong><p>Nenhum voo será autorizado ou iniciado nesta etapa.</p></Feedback>
          <dl className="data-list">
            <div><dt>Pedido</dt><dd>#{shortId(order.id)}</dd></div>
            <div><dt>Distância estimada</dt><dd>{formatDistance(order.estimated_distance_m)}</dd></div>
            <div><dt>Destino final</dt><dd>{order.delivery_point.label}</dd></div>
            <div><dt>Coordenadas</dt><dd className="mono">{formatCoordinate(order.delivery_point.latitude)}, {formatCoordinate(order.delivery_point.longitude)}</dd></div>
          </dl>
          {actionError ? <Feedback tone="error">{actionError}</Feedback> : null}
          <div className="check-row">
            <input id="approval-check" type="checkbox" checked={approvalConfirmed} onChange={(event) => setApprovalConfirmed(event.target.checked)} />
            <label htmlFor="approval-check"><strong>Revisei o mapa e o ponto final informado pelo cliente.</strong><small>Entendo que a missão será preparada em uma etapa separada.</small></label>
          </div>
        </div>
      </Modal>

      <Modal
        open={decisionModal === 'reject'}
        title="Rejeitar pedido"
        onClose={() => setDecisionModal(null)}
        closeDisabled={isActing}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDecisionModal(null)} disabled={isActing}>Cancelar</Button>
            <Button variant="danger" onClick={() => void handleReject()} loading={isActing} disabled={rejectionReason.trim().length < 10}>Registrar rejeição</Button>
          </>
        }
      >
        <div className="stack">
          <Feedback tone="warning">A rejeição é terminal para este fluxo e o motivo ficará visível na auditoria e para o cliente.</Feedback>
          <div className="field">
            <label htmlFor="rejection-reason">Motivo da rejeição</label>
            <textarea className="textarea" id="rejection-reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} minLength={10} maxLength={500} placeholder="Ex.: o ponto selecionado possui obstáculos e não é adequado para uma entrega controlada." />
            <span className="field__hint">Mínimo de 10 caracteres · {rejectionReason.length}/500</span>
          </div>
          {actionError ? <Feedback tone="error">{actionError}</Feedback> : null}
        </div>
      </Modal>
    </>
  );
}

function SummaryFact({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return (
    <div className="summary-fact">
      <span>{icon}</span>
      <div><small>{label}</small><strong>{value}</strong><p>{detail}</p></div>
    </div>
  );
}
