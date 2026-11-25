import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Button, Card, Feedback, Modal, StatusBadge } from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage, type GatewayCommandStatus, type Mission, type Vehicle } from '../../services';
import { px4SitlApi } from '../../services/real-api';
import { formatDateTime } from '../../utils/format';

const actions = {
  UPLOAD: 'Enviar missão',
  ARM: 'Armar drone',
  START: 'Iniciar missão',
  RTL: 'Solicitar retorno',
} as const;

type Action = keyof typeof actions;

const commandStates: Record<GatewayCommandStatus, string> = {
  PENDING: 'Solicitação registrada',
  ACKNOWLEDGED: 'Recebido pelo gateway',
  COMPLETED: 'Execução confirmada',
  FAILED: 'Falhou ou ficou sem confirmação',
};

const uploadStates: Partial<Record<Mission['status'], string>> = {
  AUTHORIZED: 'Upload solicitado',
  UPLOADING: 'Gateway enviando o plano',
  UPLOADED: 'Upload aceito pelo PX4. Aguardando releitura.',
  VERIFIED: 'Missão verificada por releitura',
};

export function Px4SitlControls({
  mission,
  vehicle,
  onChange,
  armOnly = false,
  children,
}: {
  mission: Mission;
  vehicle: Vehicle;
  onChange: () => void;
  armOnly?: boolean;
  children?: ReactNode;
}) {
  const load = useCallback(() => px4SitlApi.commands(mission.id), [mission.id]);
  const { data: commands, reload, error: queryError } = useAsyncData(load);
  const [pending, setPending] = useState<Action | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const timer = window.setInterval(() => void reload(), 2000);
    return () => window.clearInterval(timer);
  }, [reload]);

  const conflicting = commands?.some(({ status }) => status === 'PENDING' || status === 'ACKNOWLEDGED');
  const mayUpload = ['GENERATED', 'UNDER_REVIEW', 'EXPORTED_TO_MISSION_PLANNER', 'READY_FOR_AUTHORIZATION'].includes(mission.status);
  const mayReturn = ['EXECUTING', 'DESTINATION_REACHED'].includes(mission.status);
  const available: Record<Action, boolean> = {
    UPLOAD: mayUpload,
    ARM: mission.status === 'VERIFIED',
    START: mission.status === 'VERIFIED',
    RTL: mayReturn,
  };
  const shownActions: Action[] = armOnly ? ['ARM'] : Object.keys(actions) as Action[];
  const shownCommands = armOnly ? commands?.filter(({ command }) => command === 'ARM') : commands;
  const maySend = (action: Action) =>
    available[action] && Boolean(commands) && !conflicting && !queryError;

  const confirm = async () => {
    if (!pending || sending || !maySend(pending) || !mission.qgroundcontrol_sitl_review_event_id) return;
    setSending(true);
    setError('');
    try {
      if (pending === 'UPLOAD') {
        await px4SitlApi.upload(mission.id, vehicle.id, mission.qgroundcontrol_sitl_review_event_id);
      } else {
        await px4SitlApi.request(mission.id, pending);
      }
      await reload();
      setPending(null);
      onChange();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setSending(false);
    }
  };

  return (
    <Card title={armOnly ? 'Teste de armamento · PX4 SITL' : 'Comandos · PX4 SITL'}>
      <div className="stack">
        {children}
        <strong>{vehicle.name}</strong>
        {uploadStates[mission.status]
          ? <strong>{uploadStates[mission.status]}</strong>
          : <StatusBadge status={mission.status} />}
        {queryError ? <Feedback tone="error">{queryError}</Feedback> : null}
        <div className="decision-actions">
          {shownActions.map((action) => (
            <Button key={action} variant="secondary"
              disabled={!maySend(action)}
              onClick={() => { setError(''); setPending(action); }}>
              {actions[action]}
            </Button>
          ))}
        </div>
        {shownCommands?.length ? (
          <div className="timeline">
            {shownCommands.map((command) => (
              <article className="timeline__item" key={command.id}>
                <div>
                  <strong>{command.command} · {commandStates[command.status]}</strong>
                  {command.result_detail ? <span>{command.result_detail}</span> : null}
                  <small>{formatDateTime(command.requested_at)}</small>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </div>
      <Modal open={pending !== null} title={pending ? actions[pending] : ''} closeDisabled={sending}
        onClose={() => setPending(null)}
        footer={<><Button variant="secondary" disabled={sending} onClick={() => setPending(null)}>Cancelar</Button>
          <Button loading={sending} disabled={pending === null || !maySend(pending)} onClick={() => void confirm()}>Confirmar no SITL</Button></>}>
        <p>Confirmar {pending === 'ARM' ? 'o armamento normal' : 'esta ação'} para {vehicle.name} com a versão {mission.version} da missão?</p>
        {error ? <Feedback tone="error">{error}</Feedback> : null}
      </Modal>
    </Card>
  );
}
