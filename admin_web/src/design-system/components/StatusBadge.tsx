import type { MissionStatus, OrderStatus } from '../../services';

type Status =
  | OrderStatus
  | MissionStatus
  | 'ONLINE'
  | 'OFFLINE'
  | 'DEGRADED';

const statusLabels: Record<Status, string> = {
  DRAFT: 'Rascunho',
  PENDING_ADMIN_APPROVAL: 'Aguardando aprovação',
  APPROVED: 'Aprovado',
  REJECTED: 'Rejeitado',
  MISSION_PREPARING: 'Preparando missão',
  MISSION_READY: 'Missão criada',
  WAITING_FLIGHT_AUTHORIZATION: 'Aguardando autorização',
  MISSION_UPLOADING: 'Enviando missão',
  IN_TRANSIT: 'Em voo',
  AT_DESTINATION: 'No destino',
  DELIVERED: 'Etapa do mecanismo',
  RETURNING: 'Retornando',
  COMPLETED: 'Concluído',
  CANCELLED: 'Cancelado',
  FAILED: 'Falha',
  PENDING_VALIDATION: 'Validando missão',
  GENERATED: 'Missão gerada',
  EXPORTED_TO_MISSION_PLANNER: 'Exportada',
  UNDER_REVIEW: 'Em revisão',
  READY_FOR_AUTHORIZATION: 'Pronta para autorização',
  AUTHORIZED: 'Voo autorizado',
  UPLOADING: 'Upload em andamento',
  UPLOADED: 'Upload concluído',
  VERIFIED: 'Missão verificada',
  EXECUTING: 'Executando',
  PAUSED: 'Pausada',
  DESTINATION_REACHED: 'Destino alcançado',
  DELIVERY_CONFIRMED: 'Comando de entrega registrado',
  ABORTED: 'Abortada',
  ONLINE: 'Conectado',
  OFFLINE: 'Desconectado',
  DEGRADED: 'Atenção',
};

const dangerStatuses: Status[] = ['REJECTED', 'FAILED', 'ABORTED', 'OFFLINE'];
const warningStatuses: Status[] = [
  'PENDING_ADMIN_APPROVAL',
  'WAITING_FLIGHT_AUTHORIZATION',
  'UNDER_REVIEW',
  'READY_FOR_AUTHORIZATION',
  'DEGRADED',
  'PAUSED',
  'CANCELLED',
];
const successStatuses: Status[] = [
  'APPROVED',
  'COMPLETED',
  'DELIVERED',
  'DELIVERY_CONFIRMED',
  'ONLINE',
];

const getStatusLabel = (status: Status) => statusLabels[status] ?? status;

export function StatusBadge({ status }: { status: Status }) {
  const tone = dangerStatuses.includes(status)
    ? 'danger'
    : warningStatuses.includes(status)
      ? 'warning'
      : successStatuses.includes(status)
        ? 'success'
        : 'neutral';

  return (
    <span className={`status-badge status-badge--${tone}`}>
      {getStatusLabel(status)}
    </span>
  );
}
