import { describe, expect, it } from 'vitest';
import {
  adaptTelemetryPoint,
  adaptVehicleHealth,
  type BackendTelemetry,
  type BackendVehicleHealth,
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
