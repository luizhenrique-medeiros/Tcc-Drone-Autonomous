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

  it('usa endpoint e payload dedicados para armamento padrão', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Resposta temporariamente indisponível' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const input = {
      reason: 'Operação presencial em área controlada',
      area_clear_confirmed: true as const,
      operator_present_confirmed: true as const,
      safety_switch_ready_confirmed: true as const,
    };

    await expect(realApi.armMission('mission-arm', input)).rejects.toThrow();
    await expect(realApi.armMission('mission-arm', input)).rejects.toThrow();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      '/admin/missions/mission-arm/arm',
    );
    const firstRequest = fetchMock.mock.calls[0][1] as RequestInit;
    const secondRequest = fetchMock.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(firstRequest.body))).toEqual(input);
    expect(
      (firstRequest.headers as Record<string, string>)['Idempotency-Key'],
    ).toBe(
      (secondRequest.headers as Record<string, string>)['Idempotency-Key'],
    );
  });

  it('adapta o comando retornado pelo armamento e consulta seu status exato', async () => {
    const rawMission = {
      id: 'mission-arm-result',
      order_id: 'order-arm-result',
      vehicle_id: 'vehicle-arm-result',
      status: 'VERIFIED',
      origin_latitude: '-23.11872',
      origin_longitude: '-46.58131',
      destination_latitude: '-23.11900',
      destination_longitude: '-46.58200',
      takeoff_altitude_m: '10',
      estimated_distance_m: '120',
      mission_sha256: 'hash-arm-result',
      version: 1,
      created_at: '2026-08-21T12:00:00Z',
      updated_at: '2026-08-21T12:00:00Z',
      waypoints: [],
    };
    const pendingCommand = {
      id: 'command-arm-result',
      mission_id: rawMission.id,
      command: 'ARM',
      reason: 'Operação presencial em área controlada',
      status: 'PENDING',
      gateway_id: null,
      requested_at: '2026-08-21T12:00:01Z',
      acknowledged_at: null,
      completed_at: null,
      result_detail: null,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({ mission: rawMission, command: pendingCommand }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          ...pendingCommand,
          status: 'ACKNOWLEDGED',
          gateway_id: 'gateway-1',
          acknowledged_at: '2026-08-21T12:00:02Z',
        }),
      });
    vi.stubGlobal('fetch', fetchMock);
    const input = {
      reason: pendingCommand.reason,
      area_clear_confirmed: true as const,
      operator_present_confirmed: true as const,
      safety_switch_ready_confirmed: true as const,
    };

    const armResult = await realApi.armMission(rawMission.id, input);
    const trackedCommand = await realApi.getMissionCommand(
      rawMission.id,
      armResult.command.id,
    );

    expect(armResult.mission.id).toBe(rawMission.id);
    expect(armResult.command).toMatchObject({
      id: pendingCommand.id,
      status: 'PENDING',
    });
    expect(trackedCommand).toMatchObject({
      id: pendingCommand.id,
      status: 'ACKNOWLEDGED',
      gateway_id: 'gateway-1',
    });
    expect(String(fetchMock.mock.calls[1][0])).toContain(
      `/admin/missions/${rawMission.id}/commands/${pendingCommand.id}`,
    );
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBeUndefined();
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
