import { describe, expect, it } from 'vitest';
import {
  adaptMission,
  adaptTelemetryPoint,
  adaptVehicleHealth,
  type BackendTelemetry,
  type BackendVehicleHealth,
  type RawMission,
} from '../src/services/real-api';

const nullHealth: BackendVehicleHealth = {
  vehicle_id: 'vehicle-1',
  connected: null,
  heartbeat: null,
  gps_fix_type: null,
  satellites: null,
  ekf_ok: null,
  battery_percent: null,
  battery_voltage: null,
  flight_mode: null,
  armed: null,
  preflight_ok: null,
  rtl_configured: null,
  geofence_enabled: null,
  captured_at: null,
};

describe('adaptação de dados operacionais', () => {
  it('preserva ausências e trata contrato legado como origem desconhecida e vencida', () => {
    expect(adaptVehicleHealth(nullHealth)).toMatchObject({
      source: 'UNKNOWN',
      received_at: null,
      is_stale: true,
      connected: null,
      heartbeat_ok: null,
      battery_percent: null,
      origin_known: null,
      measured_at: null,
      authorization_limits: null,
    });
  });

  it('preserva os limites operacionais publicados pelo backend', () => {
    const authorizationLimits = {
      min_battery_percent: 73,
      battery_warning_percent: 83,
      min_gps_satellites: 19,
    };

    expect(
      adaptVehicleHealth({
        ...nullHealth,
        authorization_limits: authorizationLimits,
      }).authorization_limits,
    ).toEqual(authorizationLimits);
  });

  it('preserva a autorização persistida ao adaptar uma missão recarregada', () => {
    const raw: RawMission = {
      id: 'mission-1',
      order_id: 'order-1',
      vehicle_id: 'vehicle-1',
      status: 'UPLOADING',
      origin_latitude: '-22.9537',
      origin_longitude: '-46.5428',
      destination_latitude: '-22.9513',
      destination_longitude: '-46.5398',
      takeoff_altitude_m: '12',
      estimated_distance_m: '600',
      mission_sha256:
        '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      version: 2,
      reviewed_by_id: 'admin-reviewer',
      reviewed_at: '2026-08-06T12:00:00Z',
      created_at: '2026-08-06T11:00:00Z',
      updated_at: '2026-08-06T12:06:00Z',
      waypoints: [],
      authorization: {
        id: 'authorization-1',
        administrator_id: 'admin-real-1',
        administrator_name: 'Ana Administradora',
        operator_name: 'Carlos Operador',
        status: 'CONSUMED',
        mission_version: 2,
        issued_at: '2026-08-06T12:01:00Z',
        expires_at: '2026-08-06T12:06:00Z',
        used_at: '2026-08-06T12:02:00Z',
      },
    };

    expect(adaptMission(raw).authorization).toEqual({
      id: 'authorization-1',
      administrator_id: 'admin-real-1',
      admin_name: 'Ana Administradora',
      operator_name: 'Carlos Operador',
      status: 'CONSUMED',
      mission_version: 2,
      authorized_at: '2026-08-06T12:01:00Z',
      expires_at: '2026-08-06T12:06:00Z',
      consumed_at: '2026-08-06T12:02:00Z',
    });
  });

  it('preserva metadados explícitos e normaliza números de telemetria', () => {
    const raw: BackendTelemetry = {
      id: 'telemetry-1',
      mission_id: 'mission-1',
      source: 'HARDWARE_REAL',
      received_at: '2026-08-06T12:00:01Z',
      is_stale: false,
      latitude: '-22.9513',
      longitude: '-46.5398',
      relative_altitude_m: null,
      ground_speed_m_s: null,
      battery_percent: null,
      satellites: null,
      flight_mode: null,
      armed: null,
      recorded_at: null,
    };

    expect(adaptTelemetryPoint(raw)).toEqual({
      id: 'telemetry-1',
      mission_id: 'mission-1',
      source: 'HARDWARE_REAL',
      received_at: '2026-08-06T12:00:01Z',
      is_stale: false,
      latitude: -22.9513,
      longitude: -46.5398,
      altitude_m: null,
      ground_speed_m_s: null,
      battery_percent: null,
      satellites: null,
      flight_mode: null,
      armed: null,
      recorded_at: null,
    });
  });
});
