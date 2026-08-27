import type {
  GatewayCommand,
  Mission,
  Vehicle,
  VehicleHealth,
} from '../../services';
import { getVehicleReadiness } from './vehicle-readiness';

export interface ArmRequestReadiness {
  ready: boolean;
  blockers: string[];
}

export interface ArmTrackingExpectation {
  commandId: string;
  missionId: string;
  vehicleId: string;
  gatewayId: string | null;
}

export type ArmTrackingOutcome =
  | { state: 'WAITING' }
  | { state: 'CONFIRMED' }
  | { state: 'FAILED'; detail: string };

export const getArmTrackingOutcome = (
  command: GatewayCommand,
  expectation: ArmTrackingExpectation,
  health: VehicleHealth | null,
): ArmTrackingOutcome => {
  if (command.id !== expectation.commandId) {
    return {
      state: 'FAILED',
      detail: 'A API retornou um comando diferente daquele solicitado.',
    };
  }
  if (command.command !== 'ARM') {
    return {
      state: 'FAILED',
      detail: 'A API retornou um tipo de comando diferente de ARM.',
    };
  }
  if (command.mission_id !== expectation.missionId) {
    return {
      state: 'FAILED',
      detail: 'O comando retornado pertence a outra missão.',
    };
  }
  if (
    command.status === 'COMPLETED' &&
    expectation.gatewayId &&
    command.gateway_id !== expectation.gatewayId
  ) {
    return {
      state: 'FAILED',
      detail: 'O comando foi associado a outro gateway.',
    };
  }

  if (command.status === 'FAILED') {
    return {
      state: 'FAILED',
      detail:
        command.result_detail?.trim() ||
        'O gateway informou falha no comando de armamento sem fornecer detalhes.',
    };
  }

  if (command.status !== 'COMPLETED') return { state: 'WAITING' };

  const acknowledgedAt = command.acknowledged_at
    ? Date.parse(command.acknowledged_at)
    : Number.NaN;
  const completedAt = command.completed_at
    ? Date.parse(command.completed_at)
    : Number.NaN;
  if (!Number.isFinite(acknowledgedAt) || !Number.isFinite(completedAt)) {
    return {
      state: 'FAILED',
      detail:
        'O comando COMPLETED não possui timestamps válidos de ACK e conclusão.',
    };
  }
  if (completedAt < acknowledgedAt) {
    return {
      state: 'FAILED',
      detail: 'A conclusão do comando foi registrada antes do ACK.',
    };
  }

  if (
    !health ||
    health.vehicle_id !== expectation.vehicleId ||
    health.armed !== true ||
    health.is_stale !== false ||
    health.connected !== true ||
    health.heartbeat_ok !== true
  ) {
    return { state: 'WAITING' };
  }

  const healthReceivedAt = health.received_at
    ? Date.parse(health.received_at)
    : Number.NaN;
  const lastHeartbeatAt = health.last_heartbeat_at
    ? Date.parse(health.last_heartbeat_at)
    : Number.NaN;
  if (
    !Number.isFinite(healthReceivedAt) ||
    !Number.isFinite(lastHeartbeatAt) ||
    healthReceivedAt <= acknowledgedAt ||
    lastHeartbeatAt <= acknowledgedAt
  ) {
    return { state: 'WAITING' };
  }

  return { state: 'CONFIRMED' };
};

export const getArmTrackingExpectation = (
  commandId: string,
  mission: Mission,
  vehicle: Vehicle | null,
): ArmTrackingExpectation | null => {
  if (!mission.vehicle_id || vehicle?.id !== mission.vehicle_id) return null;
  return {
    commandId,
    missionId: mission.id,
    vehicleId: mission.vehicle_id,
    gatewayId: vehicle.gateway_id || null,
  };
};

export const isArmConfirmedByFreshHealth = (
  command: GatewayCommand,
  expectation: ArmTrackingExpectation,
  health: VehicleHealth | null,
) => getArmTrackingOutcome(command, expectation, health).state === 'CONFIRMED';

export const getArmRequestReadiness = (
  mission: Mission,
  vehicle: Vehicle | null,
  health: VehicleHealth | null,
): ArmRequestReadiness => {
  const blockers: string[] = [];

  if (mission.status !== 'VERIFIED') {
    blockers.push('A missão precisa estar verificada antes do armamento.');
  }
  if (!mission.vehicle_id) {
    blockers.push('A missão não possui veículo vinculado.');
  } else if (!vehicle || vehicle.id !== mission.vehicle_id) {
    blockers.push('O veículo vinculado à missão não está disponível no painel.');
  }

  if (!health) {
    blockers.push('A leitura de saúde do veículo está indisponível.');
  } else {
    if (mission.vehicle_id && health.vehicle_id !== mission.vehicle_id) {
      blockers.push('A leitura de saúde pertence a outro veículo.');
    }
    if (health.flight_commands_enabled !== true) {
      blockers.push('ALLOW_FLIGHT_COMMANDS está desabilitado no gateway.');
    }
    if (health.mission_start_enabled !== true) {
      blockers.push('ALLOW_MISSION_START está desabilitado no gateway.');
    }
    if (health.vehicle_arm_enabled !== true) {
      blockers.push('O gate dedicado de armamento está desabilitado no gateway.');
    }
    if (!['SITL', 'HARDWARE_REAL'].includes(health.source)) {
      blockers.push('O armamento exige origem operacional SITL ou hardware real.');
    }
    if (health.flight_mode?.trim().toUpperCase() !== 'STABILIZE') {
      blockers.push('O modo STABILIZE precisa estar confirmado antes do armamento.');
    }
    if (health.armed === true) {
      blockers.push('O veículo já está armado.');
    }

    const healthBlockers = getVehicleReadiness(health).blockers.filter(
      (blocker) =>
        !(health.armed === true && blocker.includes('desarmado')),
    );
    blockers.push(...healthBlockers);
  }

  return { ready: blockers.length === 0, blockers: [...new Set(blockers)] };
};
