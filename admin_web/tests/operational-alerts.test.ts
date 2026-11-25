import { describe, expect, it } from 'vitest';
import {
  generateOperationalAlerts,
  type SystemEvent,
  type TelemetryPoint,
  type VehicleHealth,
} from '../src/services';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const now = new Date('2026-08-06T12:10:00Z');

describe('modo bancada nos alertas operacionais', () => {
  const health: VehicleHealth = {
    ...readyHealth,
    source: 'HARDWARE_REAL',
    connection_mode: 'qgroundcontrol_forward',
    mission_upload_enabled: false,
  };
  const warning: SystemEvent = {
    id: 'gps-warning',
    vehicle_id: health.vehicle_id,
    type: 'MAVLINK_STATUSTEXT',
    severity: 'WARNING',
    message: 'Preflight: GPS PDOP too high',
    created_at: now.toISOString(),
  };

  it('oculta o aviso esperado somente quando o operador ativa o modo', () => {
    const events = [warning];
    expect(generateOperationalAlerts({ health, events, now })[0]?.what).toBe(warning.message);
    expect(generateOperationalAlerts({ benchMode: true, health, events, now })).toEqual([]);
    expect(events).toEqual([warning]);
  });

  it.each<Partial<VehicleHealth>>([
    { source: 'SITL' },
    { armed: true },
    { armed: null },
    { connected: false },
    { heartbeat_ok: false },
    { is_stale: true },
    { connection_mode: 'real' },
    { mission_upload_enabled: true },
    { flight_commands_enabled: true },
    { vehicle_arm_enabled: null },
    { mission_start_enabled: true },
  ])('mantém o aviso quando a recepção passiva não está confirmada: %o', (changes) => {
    const alerts = generateOperationalAlerts({
      benchMode: true,
      health: { ...health, ...changes },
      events: [warning],
      now,
    });
    expect(alerts.map((alert) => alert.what)).toContain(warning.message);
  });

  it.each<Partial<SystemEvent>>([
    { severity: 'ERROR' },
    { severity: 'CRITICAL' },
    { type: 'GATEWAY_WARNING' },
    { vehicle_id: undefined },
    { vehicle_id: 'outro-veiculo' },
    { mission_id: 'missao-1' },
    { message: 'Preflight: battery low' },
    { message: 'GPS failure in flight' },
  ])('preserva avisos fora dos testes de GPS desse veículo: %o', (changes) => {
    const event = { ...warning, ...changes };
    const alerts = generateOperationalAlerts({
      benchMode: true,
      health,
      events: [event],
      now,
    });
    expect(alerts[0]?.what).toBe(event.message);
  });
});

describe('gerador puro de alertas operacionais', () => {
  it('relata a disponibilidade da telemetria sem avaliar aptidão para voo', () => {
    const alerts = generateOperationalAlerts({
      health: {
        ...readyHealth,
        source: 'UNKNOWN',
        is_stale: true,
        connected: false,
        heartbeat_ok: false,
        gps_fix: 'SEM FIX',
        satellites: 4,
        ekf_ok: false,
        battery_percent: 20,
        flight_mode: null,
        armed: true,
      },
      now,
    });
    const keys = alerts.map((alert) => alert.key);

    expect(keys).toEqual(expect.arrayContaining([
      'health-source-unknown',
      'health-stale',
      'heartbeat-unavailable',
    ]));
    expect(keys).toHaveLength(3);
    expect(alerts.every((alert) => alert.what && alert.impact && alert.recommended_action)).toBe(true);
  });

  it('cobre indisponibilidade do backend, WebSocket, gateway e telemetria', () => {
    const telemetry: TelemetryPoint = {
      id: 'telemetry-1',
      mission_id: readyMission.id,
      source: 'SITL',
      received_at: '2026-08-06T12:00:00Z',
      is_stale: true,
      latitude: null,
      longitude: null,
      altitude_m: null,
      ground_speed_m_s: null,
      battery_percent: null,
      satellites: null,
      flight_mode: null,
      armed: null,
      recorded_at: '2026-08-06T11:59:59Z',
    };
    const alerts = generateOperationalAlerts({
      backendError: 'Falha HTTP 503',
      streamStatus: 'disconnected',
      vehicle: { ...readyVehicle, connected: false, status: 'OFFLINE' },
      health: readyHealth,
      telemetry: [telemetry],
      now,
    });

    expect(alerts.map((alert) => alert.key)).toEqual(expect.arrayContaining([
      'backend-unavailable',
      'operations-stream-disconnected',
      'gateway-disconnected',
      'telemetry-stale',
    ]));
  });

  it('só cria alertas serial/Mission Planner por eventos e agrupa repetições no cooldown', () => {
    expect(generateOperationalAlerts({ now }).map((alert) => alert.key)).not.toEqual(
      expect.arrayContaining(['serial-link-event', 'mission-planner-event']),
    );

    const events: SystemEvent[] = [
      {
        id: 'event-1',
        type: 'SERIAL_DISCONNECTED',
        severity: 'ERROR',
        message: 'Porta serial indisponível',
        created_at: '2026-08-06T12:09:50Z',
      },
      {
        id: 'event-2',
        type: 'SERIAL_DISCONNECTED',
        severity: 'ERROR',
        message: 'Porta serial ainda indisponível',
        created_at: '2026-08-06T12:09:55Z',
      },
      {
        id: 'event-3',
        type: 'MISSION_PLANNER_WARNING',
        severity: 'WARNING',
        message: 'Mission Planner requer revisão',
        created_at: '2026-08-06T12:09:58Z',
      },
    ];
    const alerts = generateOperationalAlerts({ events, now, cooldownMs: 30_000 });

    expect(alerts.find((alert) => alert.key === 'serial-link-event')?.occurrences).toBe(2);
    expect(alerts.find((alert) => alert.key === 'mission-planner-event')).toBeDefined();
  });

  it('deriva modo inesperado, missão ausente e upload falho somente de eventos explícitos', () => {
    const events: SystemEvent[] = [
      {
        id: 'event-mode',
        type: 'GATEWAY_PREFLIGHT_FAILED',
        severity: 'ERROR',
        message: 'Preflight falhou: FLIGHT_MODE',
        created_at: '2026-08-06T12:09:40Z',
      },
      {
        id: 'event-mission',
        type: 'MISSION_NOT_LOADED',
        severity: 'CRITICAL',
        message: 'Missão não carregada no autopiloto',
        created_at: '2026-08-06T12:09:45Z',
      },
      {
        id: 'event-upload',
        type: 'MISSION_UPLOAD_FAILED',
        severity: 'ERROR',
        message: 'Veículo não confirmou o upload',
        created_at: '2026-08-06T12:09:50Z',
      },
    ];

    const alerts = generateOperationalAlerts({ events, now });
    expect(alerts.map((alert) => alert.key)).toEqual(expect.arrayContaining([
      'flight-mode-unexpected',
      'mission-not-loaded',
      'mission-upload-failed',
    ]));
  });
});
