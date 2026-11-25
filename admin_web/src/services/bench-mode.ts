import type { VehicleHealth } from './contracts';

export const isBenchObservation = (
  enabled: boolean,
  health?: VehicleHealth | null,
) =>
  enabled &&
  health?.source === 'HARDWARE_REAL' &&
  health.connected === true &&
  health.heartbeat_ok === true &&
  health.is_stale === false &&
  health.armed === false &&
  (health.connection_mode === 'qgroundcontrol_forward' ||
    health.connection_mode === 'mavlink_router') &&
  health.mission_upload_enabled === false &&
  health.flight_commands_enabled === false &&
  health.vehicle_arm_enabled === false &&
  health.mission_start_enabled === false;

export const isBenchGpsWarning = (message: string) =>
  /^Preflight:\s*GPS\s+(?:PDOP too high|fix too low|no fix)$/i.test(message.trim());
