import { afterEach, describe, expect, it, vi } from 'vitest';
import { realApi } from '../src/services/real-api';

describe('requisições administrativas críticas', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('envia justificativa e idempotência em abortamento, RTL e comandos de voo', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Falha esperada no teste' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(realApi.abortMission('mission-1', 'Risco na área controlada')).rejects.toThrow();
    await expect(realApi.requestRtl('mission-1', 'Retorno preventivo solicitado')).rejects.toThrow();
    await expect(
      realApi.requestMissionCommand('mission-1', 'START', 'Início explícito pelo operador'),
    ).rejects.toThrow();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const abortInit = fetchMock.mock.calls[0][1] as RequestInit;
    const rtlInit = fetchMock.mock.calls[1][1] as RequestInit;
    const startInit = fetchMock.mock.calls[2][1] as RequestInit;
    expect(JSON.parse(String(abortInit.body))).toEqual({ reason: 'Risco na área controlada' });
    expect(JSON.parse(String(rtlInit.body))).toEqual({ reason: 'Retorno preventivo solicitado' });
    expect(JSON.parse(String(startInit.body))).toEqual({
      reason: 'Início explícito pelo operador',
    });
    expect(String(fetchMock.mock.calls[2][0])).toContain(
      '/admin/missions/mission-1/commands/START',
    );

    const abortHeaders = abortInit.headers as Record<string, string>;
    const rtlHeaders = rtlInit.headers as Record<string, string>;
    expect(abortHeaders['Idempotency-Key'].length).toBeGreaterThanOrEqual(8);
    expect(rtlHeaders['Idempotency-Key'].length).toBeGreaterThanOrEqual(8);
    expect(rtlHeaders['Idempotency-Key']).not.toBe(abortHeaders['Idempotency-Key']);
    const startHeaders = startInit.headers as Record<string, string>;
    expect(startHeaders['Idempotency-Key'].length).toBeGreaterThanOrEqual(8);
  });

  it('envia exatamente as três confirmações humanas auditáveis', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Falha esperada no teste' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      realApi.authorizeFlight('mission-1', {
        vehicle_id: 'vehicle-1',
        operator_name: 'Operador Responsável',
        controlled_area_confirmed: true,
        checklist: {
          area_and_conditions_clear: true,
          aircraft_and_payload_inspected: true,
          operator_ready: true,
        },
      }),
    ).rejects.toThrow();

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({
      vehicle_id: 'vehicle-1',
      operator_name: 'Operador Responsável',
      controlled_area_confirmed: true,
      checklist: {
        area_and_conditions_clear: true,
        aircraft_and_payload_inspected: true,
        operator_ready: true,
      },
    });
  });

  it('reutiliza a chave da tentativa de autorização após resposta ambígua', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Resposta temporariamente indisponível' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const input = {
      vehicle_id: 'vehicle-retry',
      operator_name: 'Operador Responsável',
      controlled_area_confirmed: true as const,
      checklist: {
        area_and_conditions_clear: true,
        aircraft_and_payload_inspected: true,
        operator_ready: true,
      },
    };

    await expect(realApi.authorizeFlight('mission-retry', input)).rejects.toThrow();
    await expect(realApi.authorizeFlight('mission-retry', input)).rejects.toThrow();

    const firstHeaders = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    const secondHeaders = fetchMock.mock.calls[1][1]?.headers as Record<string, string>;
    expect(firstHeaders['Idempotency-Key']).toBe(secondHeaders['Idempotency-Key']);
  });
});
