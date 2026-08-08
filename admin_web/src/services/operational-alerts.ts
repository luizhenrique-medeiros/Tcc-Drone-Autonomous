import type {
  EventSeverity,
  Mission,
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
  mission?: Mission | null;
  telemetry?: TelemetryPoint[];
  events?: SystemEvent[];
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
      impact: 'A missão não foi confirmada e relida no veículo; execução e armamento devem permanecer bloqueados.',
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
      impact: 'O modo observado diverge da condição validada pelo gateway para esta etapa.',
      last_updated_at: event.created_at,
      recommended_action: 'Confirme o modo e a etapa no Mission Planner; não force a continuidade pelo painel.',
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
      impact: 'O gateway pode não conseguir ler o veículo ou executar comandos autorizados.',
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
      impact: 'Saúde, comandos e telemetria podem não refletir o estado físico atual.',
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
  mission,
  telemetry = [],
  events = [],
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
      impact: 'Não há fonte técnica para saúde ou autorização de voo.',
      last_updated_at: now.toISOString(),
      recommended_action: 'Inicie e autentique o gateway no modo esperado e confirme seu heartbeat.',
    });
  } else if (vehicle?.status === 'OFFLINE' || vehicle?.connected === false) {
    add({
      key: 'gateway-disconnected',
      severity: 'ERROR',
      title: 'Gateway desconectado',
      what: `${vehicle.name} está marcado como desconectado.`,
      impact: 'Leituras e comandos podem não representar o veículo físico.',
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
        impact: 'A evidência não pode ser usada para autorizar voo.',
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
        impact: 'O estado físico atual é desconhecido e a autorização deve permanecer bloqueada.',
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
        recommended_action: 'Verifique gateway e link MAVLink; não autorize enquanto estiver ausente.',
      });
    }
    if (!health.gps_fix || health.gps_fix === 'SEM FIX') {
      add({
        key: 'gps-invalid',
        severity: 'ERROR',
        title: 'GPS não confirmado',
        what: health.gps_fix ? `Fix reportado: ${health.gps_fix}.` : 'Fix GPS indisponível.',
        impact: 'Posição, origem e navegação autônoma não são confiáveis.',
        last_updated_at: updatedAt,
        recommended_action: 'Aguarde fix adequado em área aberta e investigue mensagens do autopiloto.',
      });
    }
    if (health.satellites === null || health.satellites < 10) {
      add({
        key: 'satellites-low',
        severity: 'WARNING',
        title: 'Satélites insuficientes',
        what:
          health.satellites === null
            ? 'Quantidade de satélites indisponível.'
            : `${health.satellites} satélites reportados; mínimo visual atual: 10.`,
        impact: 'A precisão de navegação pode ser insuficiente para a missão.',
        last_updated_at: updatedAt,
        recommended_action: 'Aguarde estabilização do GPS e valide o limite efetivo no backend.',
      });
    }
    if (health.ekf_ok !== true) {
      add({
        key: 'ekf-invalid',
        severity: 'ERROR',
        title: 'EKF não confirmado',
        what: health.ekf_ok === false ? 'O gateway reportou EKF inválido.' : 'Estado do EKF indisponível.',
        impact: 'A estimativa de posição e atitude pode não ser segura.',
        last_updated_at: updatedAt,
        recommended_action: 'Investigue a mensagem no Mission Planner sem contornar pre-arm.',
      });
    }
    if (health.battery_percent === null || health.battery_percent < 40) {
      add({
        key: 'battery-low',
        severity: health.battery_percent !== null && health.battery_percent < 25 ? 'CRITICAL' : 'WARNING',
        title: 'Bateria abaixo do mínimo ou indisponível',
        what:
          health.battery_percent === null
            ? 'Percentual da bateria indisponível.'
            : `${Math.round(health.battery_percent)}% reportados; mínimo visual atual: 40%.`,
        impact: 'Não há margem confirmada para executar e retornar com segurança.',
        last_updated_at: updatedAt,
        recommended_action: 'Interrompa a autorização e valide bateria, tensão e reserva operacional.',
      });
    }
    if (!health.flight_mode) {
      add({
        key: 'flight-mode-unknown',
        severity: 'WARNING',
        title: 'Modo de voo indisponível',
        what: 'O gateway não informou o modo atual do autopiloto.',
        impact: 'O operador não consegue confirmar a condição operacional do veículo.',
        last_updated_at: updatedAt,
        recommended_action: 'Confirme o modo no Mission Planner e restabeleça a leitura do gateway.',
      });
    }

    const armedAllowedStatuses: Mission['status'][] = [
      'AUTHORIZED',
      'UPLOADING',
      'UPLOADED',
      'EXECUTING',
      'DESTINATION_REACHED',
      'DELIVERY_CONFIRMED',
      'RETURNING',
    ];
    if (health.armed === true && (!mission || !armedAllowedStatuses.includes(mission.status))) {
      add({
        key: 'unexpected-armed-state',
        severity: 'CRITICAL',
        title: 'Armamento sem etapa operacional compatível',
        what: 'O veículo está armado sem missão autorizada, em upload ou execução conhecida pelo painel.',
        impact: 'Há divergência crítica entre estado físico e autorização administrativa.',
        last_updated_at: updatedAt,
        recommended_action: 'Não envie comandos automáticos; acione imediatamente o operador e o procedimento seguro local.',
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

  if (mission?.authorization && !mission.authorization.consumed_at) {
    const expiresAt = Date.parse(mission.authorization.expires_at);
    if (Number.isFinite(expiresAt) && expiresAt <= now.getTime()) {
      add({
        key: 'authorization-expired',
        severity: 'ERROR',
        title: 'Autorização de voo expirada',
        what: 'A autorização de uso único venceu antes do consumo pelo gateway.',
        impact: 'Upload ou execução não podem prosseguir com esta autorização.',
        last_updated_at: mission.authorization.expires_at,
        recommended_action: 'Atualize saúde e checklist e emita nova autorização para a mesma versão, se ainda segura.',
      });
    }
  }

  if (mission?.status === 'UPLOADING') {
    const updatedAt = Date.parse(mission.updated_at);
    if (Number.isFinite(updatedAt) && now.getTime() - updatedAt > 30_000) {
      add({
        key: 'upload-stale',
        severity: 'WARNING',
        title: 'Upload sem atualização recente',
        what: 'A missão permanece em upload há mais de 30 segundos sem novo estado.',
        impact: 'O envio pode estar travado ou sem ACK do veículo.',
        last_updated_at: mission.updated_at,
        recommended_action: 'Verifique eventos e Mission Planner; não reinicie o upload sem reconciliar o estado.',
      });
    }
  }

  for (const event of events) {
    const candidate = eventCandidate(event);
    if (candidate) add(candidate);
  }

  return dedupeOperationalAlerts(alerts, now, cooldownMs);
};
