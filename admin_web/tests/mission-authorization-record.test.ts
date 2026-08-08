import { describe, expect, it } from 'vitest';
import {
  authorizationTitle,
  authorizationUsageMessage,
} from '../src/features/missions/authorization-presentation';
import type { MissionAuthorization } from '../src/services';

const authorization = (
  status: NonNullable<MissionAuthorization['status']>,
): MissionAuthorization => ({
  id: `authorization-${status.toLowerCase()}`,
  administrator_id: 'admin-real-1',
  admin_name: 'Ana Administradora',
  operator_name: 'Carlos Operador',
  status,
  mission_version: 2,
  authorized_at: '2026-08-06T12:01:00Z',
  expires_at: '2026-08-06T12:06:00Z',
});

describe('registro persistido da autorização', () => {
  it.each([
    ['EXPIRED', 'Autorização expirada'],
    ['REVOKED', 'Autorização revogada'],
  ] as const)('exibe %s sem alegar que aguarda consumo', (status, title) => {
    const record = authorization(status);

    expect(authorizationTitle(record)).toBe(title);
    expect(authorizationUsageMessage(record)).toBe(
      'Não está mais válida para uso.',
    );
    expect(authorizationUsageMessage(record)).not.toContain('Aguardando consumo');
  });

  it('diferencia autorização ativa e consumida', () => {
    expect(authorizationUsageMessage(authorization('ACTIVE'))).toBe(
      'Aguardando consumo pelo gateway',
    );
    const consumed = {
      ...authorization('CONSUMED'),
      consumed_at: '2026-08-06T12:02:00Z',
    };
    expect(authorizationTitle(consumed)).toBe(
      'Autorização consumida pelo gateway',
    );
    expect(authorizationUsageMessage(consumed)).toContain('Consumida em');
  });
});
