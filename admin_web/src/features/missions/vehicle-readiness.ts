import type { Mission, VehicleHealth } from '../../services';

export type AutomaticPreflightSeverity = 'PASS' | 'WARNING' | 'BLOCKING';

export interface AutomaticPreflightCheck {
  code: string;
  label: string;
  severity: AutomaticPreflightSeverity;
  detail: string;
}

export interface VehicleReadiness {
  ready: boolean;
  blockers: string[];
}

export interface MissionReadiness extends VehicleReadiness {
  checks: AutomaticPreflightCheck[];
  warnings: string[];
}

const result = (
  code: string,
  label: string,
  severity: AutomaticPreflightSeverity,
  detail: string,
): AutomaticPreflightCheck => ({ code, label, severity, detail });

export const isGpsFixValid = (fix: string | null | undefined) =>
  fix?.trim().toUpperCase().startsWith('3D') === true;

const getVehicleAutomaticChecks = (
  health: VehicleHealth | null,
): AutomaticPreflightCheck[] => {
  if (!health) {
    return [
      result('EVIDENCE', 'Origem e atualização', 'BLOCKING', 'Leitura de saúde indisponível.'),
      result('CONNECTION', 'Conexão / heartbeat', 'BLOCKING', 'Veículo sem leitura.'),
      result('GPS', 'GPS / satélites', 'BLOCKING', 'GPS ainda não recebido.'),
      result('EKF', 'EKF', 'BLOCKING', 'Estado do EKF ainda não recebido.'),
      result('BATTERY', 'Bateria', 'BLOCKING', 'Bateria ainda não recebida.'),
      result('VEHICLE_STATE', 'Modo / armamento', 'BLOCKING', 'Estado do veículo indisponível.'),
      result('HOME', 'Home', 'BLOCKING', 'Home ainda não recebida.'),
      result('GEOFENCE_RTL', 'Geofence / RTL', 'BLOCKING', 'Proteções ainda não recebidas.'),
      result('PREFLIGHT', 'Preflight do veículo', 'BLOCKING', 'Preflight ainda não recebido.'),
    ];
  }

  const evidenceFailures: string[] = [];
  if (health.source === 'UNKNOWN') evidenceFailures.push('origem técnica desconhecida');
  if (health.is_stale) evidenceFailures.push('snapshot vencido');
  if (!health.received_at) evidenceFailures.push('horário de recebimento ausente');

  const connectionFailures: string[] = [];
  if (health.connected !== true) connectionFailures.push('veículo desconectado');
  if (health.heartbeat_ok !== true) connectionFailures.push('heartbeat ausente');

  const gpsFailures: string[] = [];
  if (!isGpsFixValid(health.gps_fix)) gpsFailures.push('fix 3D indisponível');
  if (health.satellites === null) {
    gpsFailures.push('satélites não recebidos');
  } else if (!health.authorization_limits) {
    gpsFailures.push('limite mínimo de satélites não recebido');
  } else if (
    health.satellites < health.authorization_limits.min_gps_satellites
  ) {
    gpsFailures.push(
      `${health.satellites} satélites; mínimo ${health.authorization_limits.min_gps_satellites}`,
    );
  }

  let batterySeverity: AutomaticPreflightSeverity = 'PASS';
  let batteryDetail = `${health.battery_percent}% · ${health.battery_voltage ?? '--'} V`;
  if (health.battery_percent === null) {
    batterySeverity = 'BLOCKING';
    batteryDetail = 'Percentual de bateria ainda não recebido.';
  } else if (!health.authorization_limits) {
    batterySeverity = 'BLOCKING';
    batteryDetail = 'Limites operacionais da bateria não recebidos.';
  } else if (
    health.battery_percent < health.authorization_limits.min_battery_percent
  ) {
    batterySeverity = 'BLOCKING';
    batteryDetail = `${health.battery_percent}% · mínimo ${health.authorization_limits.min_battery_percent}%.`;
  } else if (
    health.battery_percent < health.authorization_limits.battery_warning_percent
  ) {
    batterySeverity = 'WARNING';
    batteryDetail = `${health.battery_percent}% · próxima do mínimo de ${health.authorization_limits.min_battery_percent}%.`;
  } else if (health.battery_voltage === null) {
    batterySeverity = 'WARNING';
    batteryDetail = `${health.battery_percent}% · tensão ainda não recebida.`;
  }

  const vehicleStateFailures: string[] = [];
  if (health.armed !== false) vehicleStateFailures.push('veículo não confirmado como desarmado');
  if (!health.flight_mode?.trim()) vehicleStateFailures.push('modo de voo indisponível');

  const protectionsFailures: string[] = [];
  if (health.geofence_enabled !== true) protectionsFailures.push('geofence não confirmada');
  if (health.rtl_configured !== true) protectionsFailures.push('RTL não confirmado');

  const preflightDetail =
    health.preflight_messages.length > 0
      ? health.preflight_messages.join(' ')
      : health.preflight_ok === true
        ? 'Veículo reportou preflight válido.'
        : 'Preflight não confirmado como válido.';

  return [
    result(
      'EVIDENCE',
      'Origem e atualização',
      evidenceFailures.length === 0 ? 'PASS' : 'BLOCKING',
      evidenceFailures.length === 0
        ? `${health.source} · snapshot atual.`
        : `${evidenceFailures.join('; ')}.`,
    ),
    result(
      'CONNECTION',
      'Conexão / heartbeat',
      connectionFailures.length === 0 ? 'PASS' : 'BLOCKING',
      connectionFailures.length === 0
        ? 'Conexão ativa e heartbeat dentro do prazo.'
        : `${connectionFailures.join('; ')}.`,
    ),
    result(
      'GPS',
      'GPS / satélites',
      gpsFailures.length === 0 ? 'PASS' : 'BLOCKING',
      gpsFailures.length === 0
        ? `${health.gps_fix} · ${health.satellites} satélites.`
        : `${gpsFailures.join('; ')}.`,
    ),
    result(
      'EKF',
      'EKF',
      health.ekf_ok === true ? 'PASS' : 'BLOCKING',
      health.ekf_ok === true ? 'Estimativa de estado válida.' : 'EKF não confirmado como válido.',
    ),
    result('BATTERY', 'Bateria', batterySeverity, batteryDetail),
    result(
      'VEHICLE_STATE',
      'Modo / armamento',
      vehicleStateFailures.length === 0 ? 'PASS' : 'BLOCKING',
      vehicleStateFailures.length === 0
        ? `${health.flight_mode} · veículo desarmado.`
        : `${vehicleStateFailures.join('; ')}.`,
    ),
    result(
      'HOME',
      'Home',
      health.origin_known === true ? 'PASS' : 'BLOCKING',
      health.origin_known === true ? 'Posição de origem conhecida.' : 'Home não confirmada.',
    ),
    result(
      'GEOFENCE_RTL',
      'Geofence / RTL',
      protectionsFailures.length === 0 ? 'PASS' : 'BLOCKING',
      protectionsFailures.length === 0
        ? 'Geofence habilitada e RTL configurado.'
        : `${protectionsFailures.join('; ')}.`,
    ),
    result(
      'PREFLIGHT',
      'Preflight do veículo',
      health.preflight_ok === true ? 'PASS' : 'BLOCKING',
      preflightDetail,
    ),
  ];
};

export const getAutomaticPreflightChecks = (
  mission: Mission,
  health: VehicleHealth | null,
): AutomaticPreflightCheck[] => {
  const missionPrepared =
    mission.status === 'READY_FOR_AUTHORIZATION' &&
    Boolean(mission.reviewed_at) &&
    Boolean(mission.file_hash);

  return [
    result(
      'MISSION_PREPARED',
      'Missão preparada',
      missionPrepared ? 'PASS' : 'BLOCKING',
      missionPrepared
        ? `Versão ${mission.version} revisada e vinculada ao artefato atual.`
        : 'A missão precisa estar revisada, versionada e pronta para autorização.',
    ),
    ...getVehicleAutomaticChecks(health),
  ];
};

const summarize = (checks: AutomaticPreflightCheck[]): MissionReadiness => {
  const blockingChecks = checks.filter((check) => check.severity === 'BLOCKING');
  const warningChecks = checks.filter((check) => check.severity === 'WARNING');
  return {
    checks,
    ready: blockingChecks.length === 0,
    blockers: blockingChecks.map((check) => check.detail),
    warnings: warningChecks.map((check) => check.detail),
  };
};

export const getMissionReadiness = (
  mission: Mission,
  health: VehicleHealth | null,
): MissionReadiness => summarize(getAutomaticPreflightChecks(mission, health));

export const getVehicleReadiness = (
  health: VehicleHealth | null,
): VehicleReadiness => {
  const blockingChecks = getVehicleAutomaticChecks(health).filter(
    (check) => check.severity === 'BLOCKING',
  );
  return {
    ready: blockingChecks.length === 0,
    blockers: blockingChecks.map((check) => check.detail),
  };
};

export const isVehicleReadyForAuthorization = (health: VehicleHealth | null) =>
  getVehicleReadiness(health).ready;
