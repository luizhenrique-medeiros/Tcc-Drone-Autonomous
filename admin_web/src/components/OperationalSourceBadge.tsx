import type { OperationalMetadata, OperationalSource } from '../services';
import { formatDateTime } from '../utils/format';

const sourceLabels: Record<OperationalSource, string> = {
  UNKNOWN: 'ORIGEM DESCONHECIDA',
  SIMULATION: 'SIMULAÇÃO',
  SITL: 'SITL',
  HARDWARE_REAL: 'HARDWARE REAL',
};

export function OperationalSourceBadge({
  source,
  received_at,
  is_stale,
}: OperationalMetadata) {
  return (
    <span
      className={`source-badge source-badge--${source.toLowerCase()} ${
        is_stale ? 'source-badge--stale' : ''
      }`}
      title={`Recebido em ${formatDateTime(received_at)}`}
    >
      {sourceLabels[source]}
      {is_stale ? ' · VENCIDO' : ''}
    </span>
  );
}
