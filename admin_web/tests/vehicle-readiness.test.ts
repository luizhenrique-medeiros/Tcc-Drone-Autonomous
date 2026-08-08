import { describe, expect, it } from 'vitest';
import {
  getAutomaticPreflightChecks,
  getMissionReadiness,
  getVehicleReadiness,
  isGpsFixValid,
} from '../src/features/missions/vehicle-readiness';
import type { VehicleHealth } from '../src/services';
import { readyHealth, readyMission } from './fixtures';

describe('readiness automático da missão', () => {
  it('aceita snapshot fresco, identificado e completo', () => {
    expect(getVehicleReadiness(readyHealth)).toEqual({ ready: true, blockers: [] });
    expect(getMissionReadiness(readyMission, readyHealth)).toMatchObject({
      ready: true,
      blockers: [],
      warnings: [],
    });
  });

  it.each<[Partial<VehicleHealth>, string]>([
    [{ source: 'UNKNOWN' }, 'EVIDENCE'],
    [{ is_stale: true }, 'EVIDENCE'],
    [{ received_at: null }, 'EVIDENCE'],
    [{ connected: null }, 'CONNECTION'],
    [{ heartbeat_ok: null }, 'CONNECTION'],
    [{ gps_fix: null }, 'GPS'],
    [{ satellites: null }, 'GPS'],
    [{ ekf_ok: null }, 'EKF'],
    [{ battery_percent: null }, 'BATTERY'],
    [{ flight_mode: null }, 'VEHICLE_STATE'],
    [{ armed: null }, 'VEHICLE_STATE'],
    [{ origin_known: false }, 'HOME'],
    [{ geofence_enabled: false }, 'GEOFENCE_RTL'],
    [{ rtl_configured: false }, 'GEOFENCE_RTL'],
    [{ preflight_ok: false }, 'PREFLIGHT'],
  ])('mantém o blocker técnico da API para %s', (change, expectedCode) => {
    const health = { ...readyHealth, ...change };
    const result = getMissionReadiness(readyMission, health);
    const check = result.checks.find((item) => item.code === expectedCode);

    expect(result.ready).toBe(false);
    expect(check?.severity).toBe('BLOCKING');
  });

  it('trata SEM FIX como GPS inválido em vez de texto truthy', () => {
    const health = { ...readyHealth, gps_fix: 'SEM FIX' };
    const gpsCheck = getAutomaticPreflightChecks(readyMission, health).find(
      (check) => check.code === 'GPS',
    );

    expect(isGpsFixValid('SEM FIX')).toBe(false);
    expect(isGpsFixValid('3D FIX')).toBe(true);
    expect(gpsCheck).toMatchObject({ severity: 'BLOCKING' });
  });

  it.each([
    [{ battery_percent: 45 }, 'próxima do mínimo'],
    [{ battery_percent: 80, battery_voltage: null }, 'tensão ainda não recebida'],
  ])('classifica aviso real sem bloquear %#', (change, detail) => {
    const result = getMissionReadiness(readyMission, { ...readyHealth, ...change });
    const batteryCheck = result.checks.find((check) => check.code === 'BATTERY');

    expect(result.ready).toBe(true);
    expect(batteryCheck).toMatchObject({ severity: 'WARNING' });
    expect(batteryCheck?.detail).toContain(detail);
  });

  it('consome limites divergentes enviados pelo backend', () => {
    const result = getMissionReadiness(readyMission, {
      ...readyHealth,
      authorization_limits: {
        min_battery_percent: 85,
        battery_warning_percent: 95,
        min_gps_satellites: 16,
      },
    });
    const gpsCheck = result.checks.find((check) => check.code === 'GPS');
    const batteryCheck = result.checks.find((check) => check.code === 'BATTERY');

    expect(result.ready).toBe(false);
    expect(gpsCheck).toMatchObject({ severity: 'BLOCKING' });
    expect(gpsCheck?.detail).toContain('mínimo 16');
    expect(batteryCheck).toMatchObject({ severity: 'BLOCKING' });
    expect(batteryCheck?.detail).toContain('mínimo 85%');
  });

  it('bloqueia com segurança quando um backend legado não informa limites', () => {
    const result = getMissionReadiness(readyMission, {
      ...readyHealth,
      authorization_limits: null,
    });

    expect(result.ready).toBe(false);
    expect(result.blockers).toEqual(
      expect.arrayContaining([
        expect.stringContaining('limite mínimo de satélites não recebido'),
        'Limites operacionais da bateria não recebidos.',
      ]),
    );
  });

  it('bloqueia quando a versão da missão ainda não está preparada', () => {
    const result = getMissionReadiness(
      { ...readyMission, file_hash: undefined },
      readyHealth,
    );

    expect(result.ready).toBe(false);
    expect(result.checks[0]).toMatchObject({
      code: 'MISSION_PREPARED',
      severity: 'BLOCKING',
    });
  });
});
