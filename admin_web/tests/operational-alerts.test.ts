import { describe, expect, it } from 'vitest';
import {
  generateOperationalAlerts,
  type SystemEvent,
  type TelemetryPoint,
} from '../src/services';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const now = new Date('2026-08-06T12:10:00Z');

describe('gerador puro de alertas operacionais', () => {
  it('cobre falhas de saúde, origem, heartbeat, navegação, bateria e armamento', () => {
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
      'gps-invalid',
      'satellites-low',
      'ekf-invalid',
      'battery-low',
      'flight-mode-unknown',
      'unexpected-armed-state',
    ]));
    expect(alerts.every((alert) => alert.what && alert.impact && alert.recommended_action)).toBe(true);
  });

  it('cobre backend, WebSocket, gateway, telemetria, autorização e upload vencidos', () => {
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
      mission: {
        ...readyMission,
        status: 'UPLOADING',
        updated_at: '2026-08-06T12:00:00Z',
        authorization: {
          id: 'authorization-1',
          admin_name: 'Admin',
          operator_name: 'Operador',
          authorized_at: '2026-08-06T11:50:00Z',
          expires_at: '2026-08-06T12:05:00Z',
        },
      },
      telemetry: [telemetry],
      now,
    });

    expect(alerts.map((alert) => alert.key)).toEqual(expect.arrayContaining([
      'backend-unavailable',
      'operations-stream-disconnected',
      'gateway-disconnected',
      'telemetry-stale',
      'authorization-expired',
      'upload-stale',
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
