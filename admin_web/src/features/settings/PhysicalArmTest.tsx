import { useEffect, useState } from 'react';
import { Button, Card, Feedback, Modal } from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services';
import { benchArmApi, type BenchArmRequest, type BenchArmTarget } from '../../services/real-api';
import { formatDateTime } from '../../utils/format';

const statusLabels: Record<BenchArmRequest['status'], string> = {
  PENDING: 'Aguardando gateway',
  DISPATCHING: 'Reservada pelo gateway',
  EXPIRED: 'Expirada antes da transmissão',
  NOT_SENT: 'Encerrada antes da transmissão',
  REJECTED: 'Rejeitada pelo PX4',
  UNCONFIRMED: 'Resultado não confirmado',
  CONFIRMED: 'Armamento confirmado',
};

export function PhysicalArmTest() {
  const { data, error, reload, setData } = useAsyncData(benchArmApi.status);
  const [selection, setSelection] = useState('');
  const [confirming, setConfirming] = useState<BenchArmTarget | null>(null);
  const [sending, setSending] = useState(false);
  const [requestError, setRequestError] = useState('');
  const enabled = data?.enabled === true;

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => void reload(), 2_000);
    return () => window.clearInterval(timer);
  }, [enabled, reload]);

  const target = data?.target;
  const request = data?.request;
  const occupied = request?.status === 'PENDING' || request?.status === 'DISPATCHING';
  const canRequest = !error && enabled && !occupied && Boolean(target?.session_id)
    && target?.session_id === selection;
  const confirm = async () => {
    if (sending || !canRequest || !confirming || confirming.session_id !== target?.session_id) return;
    setSending(true);
    setRequestError('');
    try {
      const recorded = await benchArmApi.request(confirming);
      if (data) setData({ ...data, request: recorded });
      setConfirming(null);
      setSelection('');
      await reload();
    } catch (requestFailure) {
      setRequestError(getErrorMessage(requestFailure));
    } finally {
      setSending(false);
    }
  };

  return (
    <Card title="Teste de armamento · Pixhawk física">
      <div className="stack">
        {error ? <Feedback tone="error">{error}</Feedback> : null}
        {data && !enabled ? <Feedback>Perfil físico de ensaio desativado.</Feedback> : null}
        {enabled && !target?.session_id ? (
          <Feedback>Aguardando a controladora configurada no perfil físico de ensaio.</Feedback>
        ) : null}
        {target ? (
          <>
            <div className="field">
              <label htmlFor="physical-arm-target">Veículo físico de ensaio</label>
              <select
                id="physical-arm-target"
                className="select"
                value={selection === target.session_id ? selection : ''}
                disabled={!target.session_id || occupied || sending || Boolean(error)}
                onChange={(event) => setSelection(event.target.value)}
              >
                <option value="">Selecione o veículo</option>
                {target.session_id ? <option value={target.session_id}>{target.name}</option> : null}
              </select>
            </div>
            <dl className="data-list single-column">
              <div>
                <dt>Estado observado na Pixhawk</dt>
                <dd>
                  {target.armed === null ? 'Indisponível' : target.armed ? 'Armada' : 'Desarmada'}
                  {target.heartbeat_at ? ` · ${formatDateTime(target.heartbeat_at)}` : ''}
                </dd>
              </div>
              {request ? (
                <>
                  <div><dt>Solicitação registrada</dt><dd>{formatDateTime(request.requested_at)} · {statusLabels[request.status]} · #{request.id.slice(0, 8)}</dd></div>
                  <div><dt>Comando transmitido</dt><dd>{request.transmitted === null ? 'Sem registro' : request.transmitted ? 'Sim' : 'Não'}</dd></div>
                  <div><dt>Resposta do PX4</dt><dd>{request.ack_result === null ? 'Sem ACK registrado' : request.ack_result === 0 ? 'Aceito' : `Recusado · MAV_RESULT ${request.ack_result}`}</dd></div>
                  <div><dt>Armamento confirmado para a solicitação</dt><dd>{request.confirmed_heartbeat_at ? formatDateTime(request.confirmed_heartbeat_at) : 'Sem confirmação'}</dd></div>
                </>
              ) : null}
            </dl>
            {request?.detail ? <Feedback>{request.detail}</Feedback> : null}
            {request?.status === 'UNCONFIRMED' ? (
              <Feedback tone="warning">Resultado incerto. Confira o estado diretamente no QGroundControl antes de nova solicitação.</Feedback>
            ) : null}
          </>
        ) : null}
        <div className="decision-actions">
          <Button variant="secondary" disabled={!canRequest || !target} onClick={() => {
            if (target) {
              setRequestError('');
              setConfirming(target);
            }
          }}>
            Solicitar ARM físico
          </Button>
        </div>
      </div>
      <Modal
        open={confirming !== null}
        title="Confirmar ARM físico"
        closeDisabled={sending}
        onClose={() => setConfirming(null)}
        footer={
          <>
            <Button variant="secondary" disabled={sending} onClick={() => setConfirming(null)}>Cancelar</Button>
            <Button variant="warning" loading={sending} disabled={!canRequest || confirming?.session_id !== target?.session_id} onClick={() => void confirm()}>
              Confirmar ARM físico
            </Button>
          </>
        }
      >
        <p>Solicitar armamento normal de {confirming?.name}? Confirme que o operador liberou a bancada sem hélices e que o desarmamento independente está disponível.</p>
        {requestError ? <Feedback tone="error">{requestError}</Feedback> : null}
      </Modal>
    </Card>
  );
}
