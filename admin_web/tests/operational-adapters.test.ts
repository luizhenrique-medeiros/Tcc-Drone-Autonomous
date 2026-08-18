import { describe, expect, it } from 'vitest';
import {
  adaptMission,
  adaptTelemetryPoint,
  adaptVehicle,
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
      connection_state: null,
      connection_endpoint: null,
      serial_port: null,
      heartbeat_age_seconds: null,
      current_latitude: null,
      mission_upload_enabled: null,
      mission_start_enabled: null,
      authorization_limits: null,
    });
  });

  it('preserva identidade de gateway, autopiloto e origem no veículo', () => {
    expect(
      adaptVehicle({
        id: 'vehicle-1',
        identifier: 'pixhawk-6c-1',
        name: 'Drone real',
        autopilot_system: 'ArduPilot',
        autopilot_version: 'ArduCopter 4.6',
        operational_source: 'HARDWARE_REAL',
        gateway_id: 'gateway-real-1',
        status: 'ONLINE',
        last_communication_at: '2026-08-17T12:00:00Z',
      }),
    ).toMatchObject({
      identifier: 'pixhawk-6c-1',
      autopilot_system: 'ArduPilot',
      autopilot_version: 'ArduCopter 4.6',
      operational_source: 'HARDWARE_REAL',
      gateway_id: 'gateway-real-1',
      connected: true,
    });
  });

  it('adapta diagnósticos reais sem preencher campos ausentes', () => {
    expect(
      adaptVehicleHealth({
        ...nullHealth,
        connection_state: 'CONNECTED',
        connection_mode: 'DIRECT',
        connection_topology: 'PIXHAWK_USB_SERIAL',
        connection_endpoint: 'COM7',
        serial_port: 'COM7',
        connection_baud: 57600,
        mavlink_system_id: 1,
        mavlink_component_id: 1,
        heartbeat_age_seconds: 0.4,
        last_heartbeat_at: '2026-08-17T12:00:00Z',
        current_latitude: '-23.11872',
        current_longitude: '-46.58131',
        current_altitude_m: 12.5,
        mission_upload_enabled: false,
        flight_commands_enabled: false,
        mission_start_enabled: false,
        connection_error: null,
      }),
    ).toMatchObject({
      connection_state: 'CONNECTED',
      connection_mode: 'DIRECT',
      connection_topology: 'PIXHAWK_USB_SERIAL',
      connection_endpoint: 'COM7',
      serial_port: 'COM7',
      connection_baud: 57600,
      mavlink_system_id: 1,
      mavlink_component_id: 1,
      heartbeat_age_seconds: 0.4,
      current_latitude: -23.11872,
      current_longitude: -46.58131,
      current_altitude_m: 12.5,
      mission_upload_enabled: false,
      flight_commands_enabled: false,
      mission_start_enabled: false,
      connection_error: null,
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
