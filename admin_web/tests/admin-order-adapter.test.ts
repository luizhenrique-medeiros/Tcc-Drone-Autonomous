import { describe, expect, it } from 'vitest';
import {
  adaptAdminOrder,
  type BackendAdminOrder,
} from '../src/services/real-api';

const backendFixture: BackendAdminOrder = {
  id: 'order-1',
  status: 'PENDING_ADMIN_APPROVAL',
  customer: {
    id: 'customer-1',
    name: 'Amanda Costa',
    email: 'amanda@example.local',
    phone: null,
  },
  items: [
    {
      id: 'item-1',
      product_name: 'Pizza demonstração',
      quantity: 1,
      unit_price: '49.90',
      subtotal: '49.90',
    },
  ],
  delivery_point: {
    latitude: -22.95272,
    longitude: -46.54121,
    label: 'Área gramada',
    searched_address: 'Av. dos Imigrantes',
    reference_address: 'Portão sul',
    approximate_latitude: -22.9532,
    approximate_longitude: -46.5418,
    instructions: 'Aguardar operador.',
    selection_source: 'MANUAL_MAP_SELECTION',
    map_type: 'satellite',
    customer_confirmed: true,
    controlled_area_confirmed: true,
  },
  subtotal: '49.90',
  delivery_fee: '7.50',
  discount: '9.98',
  total: '47.42',
  simulated_payment_method: 'PIX',
  rejection_reason: null,
  created_at: '2026-08-06T12:00:00Z',
  updated_at: '2026-08-06T12:00:00Z',
  estimated_distance_m: 382,
  mission_id: null,
  admin_decision: null,
};

describe('adapter do contrato administrativo real', () => {
  it('preserva cliente, ponto final e campos operacionais sem inventar PII', () => {
    const order = adaptAdminOrder(backendFixture);
    expect(order.customer).toEqual({
      id: 'customer-1',
      name: 'Amanda Costa',
      email: 'amanda@example.local',
      phone: undefined,
    });
    expect(order.delivery_point).toMatchObject({
      latitude: -22.95272,
      longitude: -46.54121,
      customer_confirmed: true,
    });
    expect(order.simulated_payment_method).toBe('PIX');
    expect(order.mission_id).toBeUndefined();
  });
});
