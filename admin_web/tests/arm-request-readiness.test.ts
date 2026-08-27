import { describe, expect, it } from 'vitest';
import {
  getArmRequestReadiness,
  getArmTrackingExpectation,
  getArmTrackingOutcome,
  isArmConfirmedByFreshHealth,
} from '../src/features/missions/arm-request-readiness';
import type { GatewayCommand } from '../src/services';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const verifiedMission = {
  ...readyMission,
  status: 'VERIFIED' as const,
  vehicle_id: readyVehicle.id,
};

const armableHealth = {
  ...readyHealth,
  flight_commands_enabled: true,
  mission_start_enabled: true,
  vehicle_arm_enabled: true,
  flight_mode: 'STABILIZE',
  armed: false,
};

const armCommand: GatewayCommand = {
  id: 'command-arm',
  mission_id: verifiedMission.id,
  command: 'ARM',
  reason: 'Teste presencial em area controlada',
  status: 'PENDING',
  gateway_id: null,
  requested_at: '2026-08-21T12:00:00Z',
  acknowledged_at: null,
  completed_at: null,
  result_detail: null,
};

const trackingExpectation = getArmTrackingExpectation(
  armCommand.id,
  verifiedMission,
  readyVehicle,
)!;

const completedArmCommand: GatewayCommand = {
  ...armCommand,
  status: 'COMPLETED',
  gateway_id: readyVehicle.gateway_id,
  acknowledged_at: '2026-08-21T12:00:01Z',
  completed_at: '2026-08-21T12:00:02Z',
};

const postAckArmedHealth = {
  ...armableHealth,
  armed: true,
  received_at: '2026-08-21T12:00:03Z',
  last_heartbeat_at: '2026-08-21T12:00:02Z',
};

describe('barreiras da solicitação de armamento', () => {
  it('libera somente missão verificada com veículo e saúde atuais', () => {
    expect(
      getArmRequestReadiness(verifiedMission, readyVehicle, armableHealth),
    ).toEqual({ ready: true, blockers: [] });
  });

  it('só confirma o ARM correlacionado com health fresco do mesmo veículo e posterior ao ACK', () => {
    expect(
      isArmConfirmedByFreshHealth(
        completedArmCommand,
        trackingExpectation,
        postAckArmedHealth,
      ),
    ).toBe(true);
    expect(
      isArmConfirmedByFreshHealth(
        completedArmCommand,
        trackingExpectation,
        { ...postAckArmedHealth, vehicle_id: 'vehicle-other' },
      ),
    ).toBe(false);
  });

  it.each(['PENDING', 'ACKNOWLEDGED'] as const)(
    'continua aguardando enquanto o comando está %s, mesmo com armed=true',
    (status) => {
      expect(
        getArmTrackingOutcome(
          { ...armCommand, status },
          trackingExpectation,
          postAckArmedHealth,
        ),
      ).toEqual({ state: 'WAITING' });
    },
  );

  it.each([
    ['id de comando', { id: 'command-other' }],
    ['tipo de comando', { command: 'START' as const }],
    ['missão', { mission_id: 'mission-other' }],
    ['gateway ausente após conclusão', { gateway_id: null }],
    ['gateway', { gateway_id: 'gateway-other' }],
  ])('falha fechada quando a correlação por %s diverge', (_, overrides) => {
    expect(
      getArmTrackingOutcome(
        { ...completedArmCommand, ...overrides },
        trackingExpectation,
        postAckArmedHealth,
      ).state,
    ).toBe('FAILED');
  });

  it.each([
    ['ACK ausente', { acknowledged_at: null }],
    ['ACK inválido', { acknowledged_at: 'nao-e-data' }],
    ['conclusão ausente', { completed_at: null }],
    ['conclusão inválida', { completed_at: 'nao-e-data' }],
    [
      'conclusão anterior ao ACK',
      {
        acknowledged_at: '2026-08-21T12:00:02Z',
        completed_at: '2026-08-21T12:00:01Z',
      },
    ],
  ])('rejeita COMPLETED com timestamp %s', (_, overrides) => {
    expect(
      getArmTrackingOutcome(
        { ...completedArmCommand, ...overrides },
        trackingExpectation,
        postAckArmedHealth,
      ).state,
    ).toBe('FAILED');
  });

  it('aceita completed_at igual ao ACK, mas exige health estritamente posterior', () => {
    const simultaneousCompletion = {
      ...completedArmCommand,
      completed_at: completedArmCommand.acknowledged_at,
    };

    expect(
      getArmTrackingOutcome(
        simultaneousCompletion,
        trackingExpectation,
        postAckArmedHealth,
      ),
    ).toEqual({ state: 'CONFIRMED' });
  });

  it.each([
    ['received_at ausente', { received_at: null }],
    ['received_at anterior', { received_at: '2026-08-21T12:00:00Z' }],
    ['received_at igual', { received_at: '2026-08-21T12:00:01Z' }],
    ['heartbeat ausente', { last_heartbeat_at: null }],
    [
      'heartbeat anterior',
      { last_heartbeat_at: '2026-08-21T12:00:00Z' },
    ],
    ['heartbeat igual', { last_heartbeat_at: '2026-08-21T12:00:01Z' }],
  ])('aguarda quando %s não é estritamente pós-ACK', (_, overrides) => {
    expect(
      getArmTrackingOutcome(
        completedArmCommand,
        trackingExpectation,
        { ...postAckArmedHealth, ...overrides },
      ),
    ).toEqual({ state: 'WAITING' });
  });

  it('confirma quando ACK/conclusão são válidos e os dois sinais de health são pós-ACK', () => {
    expect(
      getArmTrackingOutcome(
        completedArmCommand,
        trackingExpectation,
        postAckArmedHealth,
      ),
    ).toEqual({ state: 'CONFIRMED' });
  });

  it('interrompe imediatamente em FAILED e preserva result_detail', () => {
    expect(
      getArmTrackingOutcome(
        {
          ...armCommand,
          status: 'FAILED',
          result_detail: 'COMMAND_ACK recusou o armamento',
        },
        trackingExpectation,
        armableHealth,
      ),
    ).toEqual({
      state: 'FAILED',
      detail: 'COMMAND_ACK recusou o armamento',
    });
  });

  it.each([
    {
      mission: { ...verifiedMission, status: 'UPLOADED' as const },
      vehicle: readyVehicle,
      health: armableHealth,
      blocker: /missão precisa estar verificada/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, mission_start_enabled: false },
      blocker: /ALLOW_MISSION_START está desabilitado/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, vehicle_arm_enabled: false },
      blocker: /gate dedicado de armamento está desabilitado/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, is_stale: true },
      blocker: /snapshot vencido/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, connected: false, heartbeat_ok: false },
      blocker: /veículo desconectado/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, flight_mode: 'GUIDED' },
      blocker: /modo STABILIZE precisa estar confirmado/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, armed: true },
      blocker: /veículo já está armado/i,
    },
    {
      mission: verifiedMission,
      vehicle: readyVehicle,
      health: { ...armableHealth, preflight_ok: false },
      blocker: /preflight não confirmado/i,
    },
    {
      mission: { ...verifiedMission, vehicle_id: 'vehicle-other' },
      vehicle: readyVehicle,
      health: armableHealth,
      blocker: /veículo vinculado à missão não está disponível/i,
    },
  ])('falha de forma conservadora para cada barreira', ({
    mission,
    vehicle,
    health,
    blocker,
  }) => {
    const result = getArmRequestReadiness(mission, vehicle, health);

    expect(result.ready).toBe(false);
    expect(result.blockers.join(' ')).toMatch(blocker);
  });
});
