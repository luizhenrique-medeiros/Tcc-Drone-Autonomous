import type { Mission, VehicleHealth } from '../../services';

export function canReviseOrigin(mission: Mission, health: VehicleHealth | null) {
  return ['GENERATED', 'EXPORTED_TO_MISSION_PLANNER', 'UNDER_REVIEW', 'READY_FOR_AUTHORIZATION', 'VERIFIED'].includes(mission.status)
    && Boolean(mission.file_hash) && mission.vehicle_id === health?.vehicle_id
    && health !== null && !health.is_stale && health.connected === true
    && health.heartbeat_ok === true && health.armed === false && health.flight_mode === 'STABILIZE'
    && ['SITL', 'HARDWARE_REAL'].includes(health.source)
    && [health.mission_upload_enabled, health.vehicle_arm_enabled,
      health.flight_commands_enabled, health.mission_start_enabled].every((gate) => gate === false);
}
