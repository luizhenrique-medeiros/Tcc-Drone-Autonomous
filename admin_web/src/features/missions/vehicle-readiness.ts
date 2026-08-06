import type { VehicleHealth } from '../../services';

export const isVehicleReadyForAuthorization = (health: VehicleHealth | null) =>
  Boolean(
    health?.connected &&
      health.heartbeat_ok &&
      !health.armed &&
      health.satellites >= 10 &&
      health.ekf_ok &&
      health.battery_percent >= 40 &&
      health.origin_known &&
      health.geofence_enabled &&
      health.rtl_configured &&
      health.preflight_ok,
  );
