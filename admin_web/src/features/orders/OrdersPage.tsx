import { ChevronRight, Search } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Card,
  PageHeader,
  StateView,
  StatusBadge,
} from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { useOperationsStream } from '../../hooks/useOperationsStream';
import { adminApi, type OrderStatus } from '../../services';
import { formatCurrency, formatDateTime, shortId } from '../../utils/format';

type Filter = 'ALL' | 'PENDING' | 'APPROVED' | 'MISSION' | 'ACTIVE' | 'CLOSED';

const filterLabels: Record<Filter, string> = {
  ALL: 'Todos',
  PENDING: 'Aguardando análise',
  APPROVED: 'Aprovados',
  MISSION: 'Revisão e autorização',
  ACTIVE: 'Em operação',
  CLOSED: 'Encerrados',
};

const matchesFilter = (status: OrderStatus, filter: Filter) => {
  if (filter === 'ALL') return true;
  if (filter === 'PENDING') return status === 'PENDING_ADMIN_APPROVAL';
  if (filter === 'APPROVED') return status === 'APPROVED';
  if (filter === 'MISSION') {
    return [
      'MISSION_PREPARING',
      'MISSION_READY',
      'WAITING_FLIGHT_AUTHORIZATION',
      'MISSION_UPLOADING',
    ].includes(status);
  }
  if (filter === 'ACTIVE') {
    return ['IN_TRANSIT', 'AT_DESTINATION', 'DELIVERED', 'RETURNING'].includes(
      status,
    );
  }
  return ['COMPLETED', 'REJECTED', 'CANCELLED', 'FAILED'].includes(status);
};

const filterFromQuery = (value: string | null): Filter => {
  if (value === 'pending') return 'PENDING';
  if (value === 'approved') return 'APPROVED';
  return 'ALL';
};

export function OrdersPage() {
  const [searchParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>(() =>
    filterFromQuery(searchParams.get('status')),
  );
  const [search, setSearch] = useState('');
  const loader = useCallback(() => adminApi.listOrders(), []);
  const { data: orders, isLoading, error, reload } = useAsyncData(loader);
  useOperationsStream(() => void reload());

  const filteredOrders = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('pt-BR');
    return (orders ?? []).filter((order) => {
      const matchesSearch =
        !term ||
        order.id.toLowerCase().includes(term) ||
        order.customer.name.toLocaleLowerCase('pt-BR').includes(term) ||
        (order.delivery_point.label ?? '').toLocaleLowerCase('pt-BR').includes(term);
      return matchesSearch && matchesFilter(order.status, filter);
    });
  }, [filter, orders, search]);

  return (
    <>
      <PageHeader
        eyebrow="Primeira autorização"
        title="Fila de pedidos"
        description="Analise o pedido e o ponto final escolhido pelo cliente. Aprovar o pedido apenas permite preparar a missão; não autoriza o voo."
      />

      <Card className="orders-card">
        <div className="orders-toolbar">
          <div className="input-wrap orders-search">
            <Search size={19} aria-hidden="true" />
            <label className="sr-only" htmlFor="order-search">Buscar pedido</label>
            <input
              className="input"
              id="order-search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Pedido, cliente ou local de entrega"
            />
          </div>
          <label className="sr-only" htmlFor="order-filter">Filtrar pedidos</label>
          <select
            className="select orders-filter"
            id="order-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value as Filter)}
          >
            {Object.entries(filterLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        {isLoading && !orders ? <StateView state="loading" compact /> : null}
        {error && !orders ? (
          <StateView
            state="error"
            compact
            description={error}
            actionLabel="Tentar novamente"
            onAction={() => void reload()}
          />
        ) : null}
        {orders && filteredOrders.length === 0 ? (
          <StateView
            state="empty"
            compact
            title="Nenhum pedido neste filtro"
            description="Ajuste a busca ou selecione outra etapa da operação."
          />
        ) : null}
        {filteredOrders.length > 0 ? (
          <>
            <div className="table-wrap orders-table-wrap">
              <table className="data-table orders-table">
                <thead>
                  <tr>
                    <th>Pedido</th>
                    <th>Cliente</th>
                    <th>Ponto final</th>
                    <th>Total simulado</th>
                    <th>Status</th>
                    <th><span className="sr-only">Abrir</span></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((order) => (
                    <tr key={order.id}>
                      <td>
                        <strong>#{shortId(order.id)}</strong>
                        <small>{formatDateTime(order.created_at)}</small>
                      </td>
                      <td><strong>{order.customer.name}</strong><small>{order.items.length} item(ns)</small></td>
                      <td><strong>{order.delivery_point.label ?? 'Ponto sem rótulo'}</strong><small className="mono">{order.delivery_point.latitude.toFixed(5)}, {order.delivery_point.longitude.toFixed(5)}</small></td>
                      <td><strong>{formatCurrency(order.total)}</strong><small>{order.simulated_payment_method.replaceAll('_', ' ')}</small></td>
                      <td><StatusBadge status={order.status} /></td>
                      <td>
                        <Link className="table-action" to={`/orders/${order.id}`} aria-label={`Abrir pedido ${shortId(order.id)}`}>
                          <ChevronRight size={20} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="orders-mobile-list">
              {filteredOrders.map((order) => (
                <Link className="order-mobile-card" to={`/orders/${order.id}`} key={order.id}>
                  <div className="split"><strong>#{shortId(order.id)}</strong><StatusBadge status={order.status} /></div>
                  <div><strong>{order.customer.name}</strong><span>{order.delivery_point.label}</span></div>
                  <div className="split"><small>{formatDateTime(order.created_at)}</small><strong>{formatCurrency(order.total)}</strong></div>
                </Link>
              ))}
            </div>
          </>
        ) : null}
      </Card>
    </>
  );
}
