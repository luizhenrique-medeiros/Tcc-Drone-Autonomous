import { Activity, FileClock, RefreshCw, Route } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Button,
  Card,
  PageHeader,
  StateView,
  StatusBadge,
} from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import {
  adminApi,
  type EventSeverity,
  type Mission,
  type Order,
  type SystemEvent,
} from '../../services';
import { formatCurrency, formatDateTime, shortId } from '../../utils/format';

interface HistoryData {
  orders: Order[];
  missions: Mission[];
  events: SystemEvent[];
}

type Tab = 'events' | 'orders' | 'missions';

export function HistoryPage() {
  const [tab, setTab] = useState<Tab>('events');
  const [severity, setSeverity] = useState<EventSeverity | 'ALL'>('ALL');
  const loader = useCallback(async (): Promise<HistoryData> => {
    const [orders, events] = await Promise.all([
      adminApi.listOrders(),
      adminApi.listEvents(),
    ]);
    const missions = (
      await Promise.all(
        orders
          .filter((order) => order.mission_id)
          .map((order) =>
            adminApi.getMission(order.mission_id as string).catch(() => null),
          ),
      )
    ).filter((mission): mission is Mission => mission !== null);
    return { orders, missions, events };
  }, []);
  const { data, isLoading, error, reload } = useAsyncData(loader);

  if (isLoading && !data) return <StateView state="loading" />;
  if (error && !data) {
    return <StateView state="error" description={error} actionLabel="Tentar novamente" onAction={() => void reload()} />;
  }
  if (!data) return null;

  const filteredEvents = data.events.filter(
    (event) => severity === 'ALL' || event.severity === severity,
  );

  return (
    <>
      <PageHeader
        eyebrow="Auditoria operacional"
        title="Histórico e eventos"
        description="Registro cronológico das decisões administrativas, mudanças de missão, alertas e atividades do gateway."
        actions={
          <Button variant="secondary" onClick={() => void reload()} loading={isLoading}>
            <RefreshCw size={17} /> Atualizar
          </Button>
        }
      />
      <div className="history-tabs" role="tablist" aria-label="Tipo de histórico">
        <HistoryTab active={tab === 'events'} onClick={() => setTab('events')} icon={<Activity />} label="Eventos" count={data.events.length} />
        <HistoryTab active={tab === 'orders'} onClick={() => setTab('orders')} icon={<FileClock />} label="Pedidos" count={data.orders.length} />
        <HistoryTab active={tab === 'missions'} onClick={() => setTab('missions')} icon={<Route />} label="Missões" count={data.missions.length} />
      </div>

      {tab === 'events' ? (
        <Card
          title="Trilha de eventos"
          action={
            <select className="select severity-select" value={severity} onChange={(event) => setSeverity(event.target.value as EventSeverity | 'ALL')} aria-label="Filtrar severidade">
              <option value="ALL">Todas as severidades</option>
              <option value="INFO">Informação</option>
              <option value="WARNING">Atenção</option>
              <option value="ERROR">Erro</option>
              <option value="CRITICAL">Crítico</option>
            </select>
          }
        >
          {filteredEvents.length === 0 ? <StateView state="empty" compact title="Nenhum evento neste filtro" /> : (
            <div className="audit-list">
              {filteredEvents.map((event) => (
                <article className={`audit-event audit-event--${event.severity.toLowerCase()}`} key={event.id}>
                  <span className="audit-event__severity">{event.severity}</span>
                  <div className="audit-event__main">
                    <strong>{event.message}</strong>
                    <span>{event.type.replaceAll('_', ' ')}</span>
                    <div className="cluster">
                      {event.actor ? <small>Ator: {event.actor}</small> : null}
                      {event.order_id ? <Link to={`/orders/${event.order_id}`}>Pedido #{shortId(event.order_id)}</Link> : null}
                      {event.mission_id ? <Link to={`/missions/${event.mission_id}`}>Missão #{shortId(event.mission_id)}</Link> : null}
                      {event.vehicle_id ? <small>Veículo: {event.vehicle_id}</small> : null}
                    </div>
                  </div>
                  <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
                </article>
              ))}
            </div>
          )}
        </Card>
      ) : null}

      {tab === 'orders' ? (
        <Card title="Histórico de pedidos">
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Pedido</th><th>Cliente</th><th>Status</th><th>Total simulado</th><th>Atualização</th></tr></thead>
              <tbody>
                {data.orders.map((order) => (
                  <tr key={order.id}>
                    <td><Link to={`/orders/${order.id}`}>#{shortId(order.id)}</Link></td>
                    <td>{order.customer.name}</td>
                    <td><StatusBadge status={order.status} /></td>
                    <td>{formatCurrency(order.total)}</td>
                    <td>{formatDateTime(order.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {tab === 'missions' ? (
        <Card title="Histórico de missões">
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Missão</th><th>Pedido</th><th>Versão</th><th>Status</th><th>Revisão</th><th>Atualização</th></tr></thead>
              <tbody>
                {data.missions.map((mission) => (
                  <tr key={mission.id}>
                    <td><Link to={`/missions/${mission.id}`}>#{shortId(mission.id)}</Link></td>
                    <td><Link to={`/orders/${mission.order_id}`}>#{shortId(mission.order_id)}</Link></td>
                    <td>v{mission.version}</td>
                    <td><StatusBadge status={mission.status} /></td>
                    <td>{mission.reviewed_at ? `${mission.reviewer_name ?? 'Admin'} · ${formatDateTime(mission.reviewed_at)}` : 'Pendente'}</td>
                    <td>{formatDateTime(mission.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </>
  );
}

function HistoryTab({ active, onClick, icon, label, count }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string; count: number }) {
  return (
    <button className={`history-tab ${active ? 'history-tab--active' : ''}`} type="button" role="tab" aria-selected={active} onClick={onClick}>
      {icon}<span>{label}</span><strong>{count}</strong>
    </button>
  );
}
