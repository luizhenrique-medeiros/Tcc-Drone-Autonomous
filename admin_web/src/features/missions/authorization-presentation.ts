import type { Mission } from '../../services';
import { formatDateTime } from '../../utils/format';

type MissionAuthorization = NonNullable<Mission['authorization']>;

export const hasCurrentClaimAuthorization = (mission: Mission) => {
  const authorization = mission.authorization;
  return Boolean(
    authorization?.status === 'CONSUMED' &&
      authorization.consumed_at &&
      authorization.mission_version === mission.version &&
      Date.parse(authorization.expires_at) > Date.now(),
  );
};

export const canAuthorizeMission = (mission: Mission) =>
  mission.status === 'READY_FOR_AUTHORIZATION' ||
  (mission.status === 'VERIFIED' && !hasCurrentClaimAuthorization(mission));

export const authorizationTitle = (authorization: MissionAuthorization) => {
  const status =
    authorization.status ??
    (authorization.consumed_at ? 'CONSUMED' : 'ACTIVE');
  return {
    ACTIVE: 'Autorização de uso único emitida',
    CONSUMED: 'Autorização consumida pelo gateway',
    EXPIRED: 'Autorização expirada',
    REVOKED: 'Autorização revogada',
  }[status];
};

export const authorizationUsageMessage = (
  authorization: MissionAuthorization,
) => {
  if (authorization.consumed_at) {
    return `Consumida em ${formatDateTime(authorization.consumed_at)}`;
  }
  if (
    authorization.status === 'EXPIRED' ||
    authorization.status === 'REVOKED'
  ) {
    return 'Não está mais válida para uso.';
  }
  return 'Aguardando consumo pelo gateway';
};
