import type { VehicleHealth } from '../../services';

export interface VehicleReadiness {
  ready: boolean;
  blockers: string[];
}

export const getVehicleReadiness = (
  health: VehicleHealth | null,
): VehicleReadiness => {
  if (!health) return { ready: false, blockers: ['Leitura de saúde indisponível.'] };

  const blockers: string[] = [];
  if (health.source === 'UNKNOWN') blockers.push('Origem técnica desconhecida.');
  if (health.is_stale) blockers.push('Snapshot de saúde vencido.');
  if (!health.received_at) blockers.push('Horário de recebimento indisponível.');
  if (health.connected !== true) blockers.push('Veículo desconectado ou sem confirmação.');
  if (health.heartbeat_ok !== true) blockers.push('Heartbeat ausente ou desconhecido.');
  if (health.armed !== false) blockers.push('Armamento não confirmado como desativado.');
  if (!health.flight_mode) blockers.push('Modo de voo indisponível.');
  if (!health.gps_fix) blockers.push('Fix GPS indisponível.');
  if (health.satellites === null || health.satellites < 10) {
    blockers.push('Satélites abaixo do mínimo ou indisponíveis.');
  }
  if (health.ekf_ok !== true) blockers.push('EKF não confirmado como válido.');
  if (health.battery_percent === null || health.battery_percent < 40) {
    blockers.push('Bateria abaixo do mínimo ou indisponível.');
  }
  if (health.origin_known !== true) blockers.push('Origem não confirmada.');
  if (health.geofence_enabled !== true) blockers.push('Geofence não confirmada.');
  if (health.rtl_configured !== true) blockers.push('RTL não confirmado.');
  if (health.preflight_ok !== true) blockers.push('Preflight não confirmado.');

  return { ready: blockers.length === 0, blockers };
};

export const isVehicleReadyForAuthorization = (health: VehicleHealth | null) =>
  getVehicleReadiness(health).ready;
