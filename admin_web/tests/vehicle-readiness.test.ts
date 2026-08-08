import { describe, expect, it } from 'vitest';
import { getVehicleReadiness } from '../src/features/missions/vehicle-readiness';
import { readyHealth } from './fixtures';

describe('readiness do veículo', () => {
  it('aceita somente snapshot fresco, identificado e completo', () => {
    expect(getVehicleReadiness(readyHealth)).toEqual({ ready: true, blockers: [] });
  });

  it.each([
    [{ source: 'UNKNOWN' as const }, 'Origem técnica desconhecida.'],
    [{ is_stale: true }, 'Snapshot de saúde vencido.'],
    [{ received_at: null }, 'Horário de recebimento indisponível.'],
    [{ connected: null }, 'Veículo desconectado ou sem confirmação.'],
    [{ satellites: null }, 'Satélites abaixo do mínimo ou indisponíveis.'],
    [{ battery_percent: null }, 'Bateria abaixo do mínimo ou indisponível.'],
  ])('bloqueia campo crítico inválido %#', (change, expectedBlocker) => {
    const result = getVehicleReadiness({ ...readyHealth, ...change });
    expect(result.ready).toBe(false);
    expect(result.blockers).toContain(expectedBlocker);
  });
});
