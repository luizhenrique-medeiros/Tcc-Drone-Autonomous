import type { Mission, Vehicle, VehicleHealth } from '../src/services';

export const readyMission: Mission = {
  id: 'a1234567-1234-4321-8765-123456789abc',
  order_id: 'order-12345678',
  status: 'READY_FOR_AUTHORIZATION',
  version: 2,
  altitude_m: 12,
  estimated_distance_m: 600,
  origin: { latitude: -22.9537, longitude: -46.5428, label: 'Base' },
  destination: { latitude: -22.9513, longitude: -46.5398, label: 'Destino' },
  waypoints: [],
  file_hash: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
  reviewed_at: '2026-08-06T12:00:00Z',
  created_at: '2026-08-06T11:00:00Z',
  updated_at: '2026-08-06T12:00:00Z',
};

export const readyVehicle: Vehicle = {
  id: 'vehicle-ready-01',
  name: 'Drone de teste',
  system: 'Pixhawk 6C',
  connected: true,
  status: 'ONLINE',
  last_seen_at: '2026-08-06T12:00:00Z',
};

export const readyHealth: VehicleHealth = {
  source: 'SITL',
  received_at: '2026-08-06T12:00:01Z',
  is_stale: false,
  vehicle_id: readyVehicle.id,
  connected: true,
  heartbeat_ok: true,
  flight_mode: 'GUIDED',
  armed: false,
  gps_fix: '3D FIX',
  satellites: 14,
  ekf_ok: true,
  battery_percent: 80,
  battery_voltage: 15.4,
  origin_known: true,
  geofence_enabled: true,
  rtl_configured: true,
  preflight_ok: true,
  preflight_messages: [],
  measured_at: '2026-08-06T12:00:00Z',
  authorization_limits: {
    min_battery_percent: 40,
    battery_warning_percent: 50,
    min_gps_satellites: 10,
  },
};
