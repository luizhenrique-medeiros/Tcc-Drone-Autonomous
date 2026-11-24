import type { VehicleHealth } from '../../services';

export const px4PrearmDetail = (health: VehicleHealth) => {
  const ok = health.px4_diagnostics?.current_mode_prearm_ok;
  if (health.is_stale || ok == null || !health.flight_mode) return null;
  return `PX4 informou que ${ok ? 'é possível armar' : 'o armamento está indisponível'} no modo ${health.flight_mode}.`;
};

export const px4RtlDetail = (health: VehicleHealth) => {
  const data = health.px4_diagnostics;
  if (health.is_stale || !data) return null;
  const fields = [
    data.rtl_type == null ? null : `tipo ${data.rtl_type}`,
    data.rtl_return_alt_m == null ? null : `altitude de retorno ${data.rtl_return_alt_m} m`,
    data.rtl_descend_alt_m == null ? null : `altitude de descida ${data.rtl_descend_alt_m} m`,
    data.rtl_land_delay_s == null ? null : data.rtl_land_delay_s === -1
      ? 'espera indefinida'
      : `espera antes do pouso ${data.rtl_land_delay_s} s`,
    data.rtl_cone_angle_deg == null ? null : `ângulo do cone ${data.rtl_cone_angle_deg}°`,
    data.rtl_min_distance_m == null ? null : `raio próximo ao destino ${data.rtl_min_distance_m} m`,
  ].filter(Boolean);
  return fields.length ? `Parâmetros recebidos do PX4 (${fields.join(' · ')}).` : null;
};
