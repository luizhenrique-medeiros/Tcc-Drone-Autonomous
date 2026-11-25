import { isBenchGpsWarning, isBenchObservation } from './bench-mode';
import type {
  EventSeverity,
  SystemEvent,
  TelemetryPoint,
  Vehicle,
  VehicleHealth,
} from './contracts';

export type OperationalAlertSeverity = 'WARNING' | 'ERROR' | 'CRITICAL';

export interface OperationalAlert {
  key: string;
  severity: OperationalAlertSeverity;
  title: string;
  what: string;
  impact: string;
  last_updated_at: string | null;
  recommended_action: string;
  occurrences: number;
  cooldown_until: string | null;
}

export interface OperationalAlertInput {
  backendError?: string;
  streamStatus?:
    | 'disabled'
    | 'connecting'
    | 'authenticating'
    | 'connected'
    | 'reconnecting'
    | 'disconnected';
  vehicle?: Vehicle | null;
  health?: VehicleHealth | null;
  telemetry?: TelemetryPoint[];
  events?: SystemEvent[];
  benchMode?: boolean;
  expectVehicle?: boolean;
  now?: Date;
  cooldownMs?: number;
}

type AlertCandidate = Omit<OperationalAlert, 'occurrences' | 'cooldown_until'>;

const severityRank: Record<OperationalAlertSeverity, number> = {
  WARNING: 1,
  ERROR: 2,
  CRITICAL: 3,
};

const eventSeverity = (
  severity: EventSeverity,
): OperationalAlertSeverity | null => {
  if (severity === 'CRITICAL') return 'CRITICAL';
  if (severity === 'ERROR') return 'ERROR';
  if (severity === 'WARNING') return 'WARNING';
  return null;
};

const timestampMs = (value: string | null) => {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const dedupeOperationalAlerts = (
  candidates: AlertCandidate[],
  now = new Date(),
  cooldownMs = 30_000,
): OperationalAlert[] => {
  const grouped = new Map<string, AlertCandidate[]>();
  for (const candidate of candidates) {
    grouped.set(candidate.key, [...(grouped.get(candidate.key) ?? []), candidate]);
  }

  return [...grouped.values()]
    .map((group) => {
      const ordered = [...group].sort((a, b) => {
        const severityDifference = severityRank[b.severity] - severityRank[a.severity];
        return severityDifference || timestampMs(b.last_updated_at) - timestampMs(a.last_updated_at);
      });
      const selected = ordered[0];
      const latestTimestamp = Math.max(...group.map((item) => timestampMs(item.last_updated_at)));
      const occurrences = group.filter(
        (item) => latestTimestamp - timestampMs(item.last_updated_at) <= cooldownMs,
      ).length;
      return {
        ...selected,
        last_updated_at:
          latestTimestamp > 0 ? new Date(latestTimestamp).toISOString() : selected.last_updated_at,
        occurrences,
        cooldown_until:
          latestTimestamp > 0
            ? new Date(latestTimestamp + cooldownMs).toISOString()
            : new Date(now.getTime() + cooldownMs).toISOString(),
      };
    })
    .sort((a, b) => {
      const severityDifference = severityRank[b.severity] - severityRank[a.severity];
      return severityDifference || timestampMs(b.last_updated_at) - timestampMs(a.last_updated_at);
    });
};

const eventCandidate = (event: SystemEvent): AlertCandidate | null => {
  const severity = eventSeverity(event.severity);
  if (!severity) return null;
  const searchable = `${event.type} ${event.message}`.toUpperCase();
  const eventType = event.type.toUpperCase();

  const uploadFailed =
    eventType === 'MISSION_UPLOAD_FAILED' ||
    (eventType === 'ACTIVE_MISSION_FAILED' && searchable.includes('UPLOAD'));
  if (uploadFailed) {
    return {
      key: 'mission-upload-failed',
      severity,
      title: 'Falha no upload da missão',
      what: event.message,
      impact: 'O evento indica que a gravação não foi confirmada no veículo.',
      last_updated_at: event.created_at,
      recommended_action: 'Revise o ACK e os eventos MAVLink; reconcilie o estado antes de qualquer nova tentativa.',
    };
  }

  const missionNotLoaded =
    eventType === 'MISSION_NOT_LOADED' ||
    searchable.includes('MISSION NOT LOADED') ||
    searchable.includes('MISSÃO NÃO CARREGADA') ||
    searchable.includes('MISSAO NAO CARREGADA') ||
    searchable.includes('MISSÃO NÃO FOI CARREGADA');
  if (missionNotLoaded) {
    return {
      key: 'mission-not-loaded',
      severity,
      title: 'Missão não carregada no veículo',
      what: event.message,
      impact: 'O plano esperado não está confirmado no autopiloto e não pode ser tratado como executável.',
      last_updated_at: event.created_at,
      recommended_action: 'Compare versão e hash, confirme a leitura após upload e mantenha o veículo desarmado.',
    };
  }

  const unexpectedMode =
    eventType === 'FLIGHT_MODE_UNEXPECTED' ||
    eventType === 'UNEXPECTED_FLIGHT_MODE' ||
    searchable.includes('FLIGHT_MODE') ||
    searchable.includes('MODO INESPERADO') ||
    searchable.includes('UNEXPECTED MODE');
  if (unexpectedMode) {
    return {
      key: 'flight-mode-unexpected',
      severity,
      title: 'Modo de voo inesperado',
      what: event.message,
      impact: 'O evento registra uma divergência no modo observado.',
      last_updated_at: event.created_at,
      recommended_action: 'Confira as mensagens do veículo na estação de controle.',
    };
  }

  if (searchable.includes('MISSION_PLANNER')) {
    return {
      key: 'mission-planner-event',
      severity,
      title: 'Evento do Mission Planner',
      what: event.message,
      impact: 'A revisão ou supervisão externa da missão pode estar comprometida.',
      last_updated_at: event.created_at,
      recommended_action: 'Abra o Mission Planner e confirme conexão, mensagens e versão da missão.',
    };
  }
  if (searchable.includes('SERIAL')) {
    return {
      key: 'serial-link-event',
      severity,
      title: 'Evento de conexão serial',
      what: event.message,
      impact: 'O gateway pode deixar de receber dados do veículo.',
      last_updated_at: event.created_at,
      recommended_action: 'Verifique porta, cabo, permissões e configuração do gateway sem armar o veículo.',
    };
  }
  if (searchable.includes('GATEWAY') && searchable.includes('DISCONNECT')) {
    return {
      key: 'gateway-disconnected',
      severity,
      title: 'Gateway desconectado',
      what: event.message,
      impact: 'A telemetria pode não refletir o estado físico atual.',
      last_updated_at: event.created_at,
      recommended_action: 'Confirme o processo do gateway e o link MAVLink antes de operar.',
    };
  }
  return {
    key: `event-${event.type}`,
    severity,
    title: event.type.replaceAll('_', ' '),
    what: event.message,
    impact: 'O evento requer avaliação do operador antes de continuar o fluxo.',
    last_updated_at: event.created_at,
    recommended_action: 'Abra a trilha de eventos e siga o procedimento operacional aplicável.',
  };
};

export const generateOperationalAlerts = ({
  backendError,
  streamStatus,
  vehicle,
  health,
  telemetry = [],
  events = [],
  benchMode = false,
  expectVehicle = false,
  now = new Date(),
  cooldownMs = 30_000,
}: OperationalAlertInput): OperationalAlert[] => {
  const alerts: AlertCandidate[] = [];
  const add = (alert: AlertCandidate) => alerts.push(alert);

  if (backendError) {
    add({
      key: 'backend-unavailable',
      severity: 'ERROR',
      title: 'Backend indisponível',
      what: backendError,
      impact: 'Os dados exibidos podem ser antigos e ações administrativas não são confiáveis.',
      last_updated_at: now.toISOString(),
      recommended_action: 'Verifique `/ready`, rede e configuração da API antes de tentar novamente.',
    });
  }

  if (streamStatus === 'disconnected' || streamStatus === 'reconnecting') {
    add({
      key: 'operations-stream-disconnected',
      severity: streamStatus === 'disconnected' ? 'ERROR' : 'WARNING',
      title: 'Canal em tempo real indisponível',
      what:
        streamStatus === 'disconnected'
          ? 'O limite de reconexões do WebSocket foi atingido.'
          : 'O WebSocket está tentando restabelecer uma sessão autenticada.',
      impact: 'Atualizações dependem temporariamente do polling e podem chegar com atraso.',
      last_updated_at: now.toISOString(),
      recommended_action: 'Confirme API, token e proxy WebSocket; recarregue após corrigir a conexão.',
    });
  }

  if (expectVehicle && !vehicle) {
    add({
      key: 'gateway-disconnected',
      severity: 'ERROR',
      title: 'Veículo ou gateway indisponível',
      what: 'Nenhum veículo foi retornado pela API administrativa.',
      impact: 'A telemetria do veículo está indisponível.',
      last_updated_at: now.toISOString(),
      recommended_action: 'Inicie e autentique o gateway no modo esperado e confirme seu heartbeat.',
    });
  } else if (vehicle?.status === 'OFFLINE' || vehicle?.connected === false) {
    add({
      key: 'gateway-disconnected',
      severity: 'ERROR',
      title: 'Gateway desconectado',
      what: `${vehicle.name} está marcado como desconectado.`,
      impact: 'O painel pode mostrar apenas a última leitura disponível.',
      last_updated_at: vehicle.last_seen_at || null,
      recommended_action: 'Verifique processo do gateway, rede e conexão MAVLink antes de operar.',
    });
  }

  if (health) {
    const updatedAt = health.received_at ?? health.measured_at;
    if (health.source === 'UNKNOWN') {
      add({
        key: 'health-source-unknown',
        severity: 'ERROR',
        title: 'Origem da saúde desconhecida',
        what: 'A API não identificou se a leitura veio de simulação, SITL ou hardware real.',
        impact: 'A origem da telemetria não pôde ser identificada.',
        last_updated_at: updatedAt,
        recommended_action: 'Corrija a identificação de origem no gateway e publique um novo snapshot.',
      });
    }
    if (health.is_stale) {
      add({
        key: 'health-stale',
        severity: 'ERROR',
        title: 'Saúde do veículo vencida',
        what: 'O último snapshot ultrapassou o limite de frescor do backend.',
        impact: 'A amostra pode não representar o estado físico atual.',
        last_updated_at: updatedAt,
        recommended_action: 'Restabeleça heartbeat e aguarde um snapshot novo antes de continuar.',
      });
    }
    if (health.connected !== true || health.heartbeat_ok !== true) {
      add({
        key: 'heartbeat-unavailable',
        severity: 'ERROR',
        title: 'Heartbeat indisponível',
        what: 'Conexão ou heartbeat não estão confirmados.',
        impact: 'O painel não consegue confirmar presença e estado atual do veículo.',
        last_updated_at: updatedAt,
        recommended_action: 'Verifique o gateway e o link MAVLink.',
      });
    }
  }

  const latestTelemetry = [...telemetry].sort(
    (a, b) => timestampMs(b.recorded_at) - timestampMs(a.recorded_at),
  )[0];
  if (latestTelemetry?.is_stale) {
    add({
      key: 'telemetry-stale',
      severity: 'ERROR',
      title: 'Telemetria vencida',
      what: 'A última amostra disponível foi marcada como vencida pelo backend.',
      impact: 'Posição, bateria e progresso não representam necessariamente o estado atual.',
      last_updated_at: latestTelemetry.received_at ?? latestTelemetry.recorded_at,
      recommended_action: 'Use a estação de solo como referência e restabeleça gateway/backend antes de continuar.',
    });
  }

  const benchObservation = isBenchObservation(benchMode, health);
  for (const event of events) {
    if (
      benchObservation &&
      event.vehicle_id === health?.vehicle_id &&
      !event.mission_id &&
      event.type === 'MAVLINK_STATUSTEXT' &&
      event.severity === 'WARNING' &&
      isBenchGpsWarning(event.message)
    ) continue;
    const candidate = eventCandidate(event);
    if (candidate) add(candidate);
  }

  return dedupeOperationalAlerts(alerts, now, cooldownMs);
};
