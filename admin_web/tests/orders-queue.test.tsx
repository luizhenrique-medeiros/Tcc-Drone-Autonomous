import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEMO_ORDERS } from '../src/demo/data';
import { OrdersPage } from '../src/features/orders/OrdersPage';
import { adminApi } from '../src/services';

describe('fila administrativa', () => {
  afterEach(() => vi.restoreAllMocks());

  it('exibe pedidos reais do cliente API com status e ponto final', async () => {
    vi.spyOn(adminApi, 'listOrders').mockResolvedValue(DEMO_ORDERS.slice(0, 2));
    render(
      <MemoryRouter>
        <OrdersPage />
      </MemoryRouter>,
    );

    expect(await screen.findAllByText('Amanda Costa')).not.toHaveLength(0);
    expect(screen.getAllByText('Área gramada — portão sul').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Aguardando aprovação').length).toBeGreaterThan(0);
  });

  it('mantém estado de erro com tentativa novamente', async () => {
    vi.spyOn(adminApi, 'listOrders').mockRejectedValue(new Error('API indisponível'));
    render(
      <MemoryRouter>
        <OrdersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('API indisponível')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument();
  });
});
