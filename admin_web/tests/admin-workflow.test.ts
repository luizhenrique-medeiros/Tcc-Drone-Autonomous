import { beforeEach, describe, expect, it } from 'vitest';
import { DEMO_ORDERS, DEMO_VEHICLE } from '../src/demo/data';
import { demoApi, resetDemoState } from '../src/services/demo-api';
import type { HumanFlightConfirmations } from '../src/services';

const completeChecklist: HumanFlightConfirmations = {
  area_and_conditions_clear: true,
  aircraft_and_payload_inspected: true,
  operator_ready: true,
};

describe('decisões administrativas em duas etapas', () => {
  beforeEach(resetDemoState);

  it('aprova e rejeita pedidos em ações distintas e exige motivo', async () => {
    const approved = await demoApi.approveOrder(DEMO_ORDERS[0].id);
    expect(approved.status).toBe('APPROVED');

    await expect(
      demoApi.rejectOrder(DEMO_ORDERS[1].id, 'curto'),
    ).rejects.toThrow('pelo menos 10 caracteres');
    const rejected = await demoApi.rejectOrder(
      DEMO_ORDERS[1].id,
      'Área com pessoas dentro do perímetro seguro.',
    );
    expect(rejected.status).toBe('REJECTED');
    expect(rejected.admin_decision?.reason).toContain('perímetro');
  });

  it('não mistura revisão de missão com autorização e bloqueia reenvio', async () => {
    const approved = await demoApi.approveOrder(DEMO_ORDERS[0].id);
    expect(approved.status).toBe('APPROVED');
    const generated = await demoApi.prepareMission(approved.id);
    expect(generated.status).toBe('GENERATED');

    const underReview = await demoApi.markMissionUnderReview(generated.id);
    expect(underReview.status).toBe('UNDER_REVIEW');
    expect(underReview.authorization).toBeUndefined();

    const reviewed = await demoApi.markMissionReviewed(generated.id);
    expect(reviewed.status).toBe('READY_FOR_AUTHORIZATION');
    const authorized = await demoApi.authorizeFlight(generated.id, {
      vehicle_id: DEMO_VEHICLE.id,
      operator_name: 'Operador Responsável',
      controlled_area_confirmed: true,
      checklist: completeChecklist,
    });
    expect(authorized.status).toBe('AUTHORIZED');
    expect(authorized.authorization?.operator_name).toBe('Operador Responsável');

    await expect(
      demoApi.authorizeFlight(generated.id, {
        vehicle_id: DEMO_VEHICLE.id,
        operator_name: 'Operador Responsável',
        controlled_area_confirmed: true,
        checklist: completeChecklist,
      }),
    ).rejects.toThrow('ainda não está pronta');
  });
});
