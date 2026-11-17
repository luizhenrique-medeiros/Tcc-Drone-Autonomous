import { describe, expect, it } from 'vitest';
import { canAuthorizeMission, hasCurrentClaimAuthorization } from '../src/features/missions/authorization-presentation';
import { getArmRequestReadiness } from '../src/features/missions/arm-request-readiness';
import { getMissionReadiness } from '../src/features/missions/vehicle-readiness';
import { currentClaimAuthorization, readyHealth, readyMission, readyVehicle } from './fixtures';

const verified = { ...readyMission, status: 'VERIFIED' as const, vehicle_id: readyVehicle.id, authorization: currentClaimAuthorization };

describe('renovacao da autorizacao verificada', () => {
  it('preserva preparo e oferece renovacao somente apos expirar', () => {
    expect(getMissionReadiness(verified, readyHealth).ready).toBe(true);
    expect(hasCurrentClaimAuthorization(verified)).toBe(true);
    expect(canAuthorizeMission(verified)).toBe(false);
    const expired = { ...verified, authorization: { ...currentClaimAuthorization, expires_at: new Date(Date.now() - 1).toISOString() } };
    expect(canAuthorizeMission(expired)).toBe(true);
    expect(getArmRequestReadiness(expired, readyVehicle, readyHealth).blockers).toContain('Renove a autorização da missão antes de solicitar armamento.');
  });
  it('nao aceita autorizacao ausente, revogada, sem consumo ou de outra versao', () => {
    expect(hasCurrentClaimAuthorization({ ...verified, authorization: undefined })).toBe(false);
    for (const change of [{ status: 'REVOKED' as const }, { consumed_at: undefined }, { mission_version: 999 }, { expires_at: 'invalid' }]) {
      expect(hasCurrentClaimAuthorization({ ...verified, authorization: { ...currentClaimAuthorization, ...change } })).toBe(false);
    }
    expect(canAuthorizeMission({ ...verified, status: 'EXECUTING' })).toBe(false);
  });
});
