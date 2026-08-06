import {
  DEMO_EVENTS,
  DEMO_HEALTH,
  DEMO_MISSIONS,
  DEMO_ORDERS,
  DEMO_TELEMETRY,
  DEMO_VEHICLE,
} from '../demo/data';
import { ApiError } from './api-error';
import type {
  AdminApi,
  AdminUser,
  FlightAuthorizationInput,
  Mission,
  Order,
  OrderStatus,
  SystemEvent,
} from './contracts';

const demoUser: AdminUser = {
  id: 'admin-demo-01',
  name: 'Operador Demo',
  email: 'admin@devcore.local',
  role: 'ADMIN',
};

let orders = structuredClone(DEMO_ORDERS);
let missions = structuredClone(DEMO_MISSIONS);
let events = structuredClone(DEMO_EVENTS);

export const resetDemoState = () => {
  orders = structuredClone(DEMO_ORDERS);
  missions = structuredClone(DEMO_MISSIONS);
  events = structuredClone(DEMO_EVENTS);
};

const wait = () => new Promise((resolve) => window.setTimeout(resolve, 180));
const copy = <T>(value: T): T => structuredClone(value);

const findOrder = (id: string) => {
  const order = orders.find((item) => item.id === id);
  if (!order) throw new ApiError('Pedido não encontrado no conjunto demo.', 404);
  return order;
};

const findMission = (id: string) => {
  const mission = missions.find((item) => item.id === id);
  if (!mission) throw new ApiError('Missão não encontrada no conjunto demo.', 404);
  return mission;
};

const addEvent = (event: Omit<SystemEvent, 'id' | 'created_at'>) => {
  events = [
    {
      ...event,
      id: `event-local-${crypto.randomUUID()}`,
      created_at: new Date().toISOString(),
    },
    ...events,
  ];
};

const updateOrder = (order: Order) => {
  orders = orders.map((item) => (item.id === order.id ? order : item));
  return copy(order);
};

const updateMission = (mission: Mission) => {
  missions = missions.map((item) =>
    item.id === mission.id ? mission : item,
  );
  return copy(mission);
};

export const demoApi: AdminApi = {
  async login(input) {
    await wait();
    if (
      input.email !== 'admin@devcore.local' ||
      input.password !== 'demo-admin'
    ) {
      throw new ApiError(
        'No modo demo, use admin@devcore.local e demo-admin.',
        401,
      );
    }
    return {
      access_token: 'demo-session-no-backend',
      token_type: 'bearer',
      expires_in: 3600,
      user: copy(demoUser),
    };
  },
  async me() {
    await wait();
    return copy(demoUser);
  },
  async listOrders(status?: OrderStatus) {
    await wait();
    return copy(status ? orders.filter((item) => item.status === status) : orders);
  },
  async getOrder(id) {
    await wait();
    return copy(findOrder(id));
  },
  async approveOrder(id) {
    await wait();
    const current = findOrder(id);
    if (current.status !== 'PENDING_ADMIN_APPROVAL') {
      throw new ApiError('Este pedido não está aguardando aprovação.', 409);
    }
    const order: Order = {
      ...current,
      status: 'APPROVED',
      updated_at: new Date().toISOString(),
      admin_decision: {
        decision: 'APPROVED',
        admin_name: demoUser.name,
        created_at: new Date().toISOString(),
      },
    };
    addEvent({
      type: 'ORDER_APPROVED',
      severity: 'INFO',
      message: 'Pedido aprovado no modo demonstração.',
      actor: demoUser.name,
      order_id: id,
    });
    return updateOrder(order);
  },
  async rejectOrder(id, reason) {
    await wait();
    if (reason.trim().length < 10) {
      throw new ApiError('Informe um motivo com pelo menos 10 caracteres.', 422);
    }
    const current = findOrder(id);
    if (current.status !== 'PENDING_ADMIN_APPROVAL') {
      throw new ApiError('Este pedido não está aguardando decisão.', 409);
    }
    const order: Order = {
      ...current,
      status: 'REJECTED',
      updated_at: new Date().toISOString(),
      admin_decision: {
        decision: 'REJECTED',
        reason: reason.trim(),
        admin_name: demoUser.name,
        created_at: new Date().toISOString(),
      },
    };
    addEvent({
      type: 'ORDER_REJECTED',
      severity: 'WARNING',
      message: `Pedido rejeitado: ${reason.trim()}`,
      actor: demoUser.name,
      order_id: id,
    });
    return updateOrder(order);
  },
  async prepareMission(orderId) {
    await wait();
    const order = findOrder(orderId);
    if (order.status !== 'APPROVED') {
      throw new ApiError('A missão exige um pedido aprovado.', 409);
    }
    const id = `mission-demo-${crypto.randomUUID()}`;
    const template = DEMO_MISSIONS[0];
    const mission: Mission = {
      ...copy(template),
      id,
      order_id: order.id,
      status: 'GENERATED',
      version: 1,
      destination: {
        latitude: order.delivery_point.latitude,
        longitude: order.delivery_point.longitude,
        label: order.delivery_point.label,
      },
      estimated_distance_m: (order.estimated_distance_m ?? 400) * 2,
      exported_at: undefined,
      reviewed_at: undefined,
      reviewer_name: undefined,
      file_hash: 'sha256:demo-local',
      authorization: undefined,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    missions = [mission, ...missions];
    updateOrder({
      ...order,
      status: 'MISSION_READY',
      mission_id: id,
      updated_at: new Date().toISOString(),
    });
    addEvent({
      type: 'MISSION_GENERATED',
      severity: 'INFO',
      message: 'Missão de demonstração gerada para revisão.',
      actor: demoUser.name,
      order_id: order.id,
      mission_id: id,
    });
    return copy(mission);
  },
  async getMission(id) {
    await wait();
    return copy(findMission(id));
  },
  async markMissionUnderReview(id) {
    await wait();
    const current = findMission(id);
    const mission: Mission = {
      ...current,
      status: 'UNDER_REVIEW',
      exported_at: current.exported_at ?? new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    addEvent({
      type: 'MISSION_OPENED_IN_PLANNER',
      severity: 'INFO',
      message: 'Abertura no Mission Planner registrada no modo demo.',
      actor: demoUser.name,
      mission_id: id,
    });
    return updateMission(mission);
  },
  async markMissionReviewed(id) {
    await wait();
    const current = findMission(id);
    if (current.status !== 'UNDER_REVIEW') {
      throw new ApiError('Registre primeiro a abertura no Mission Planner.', 409);
    }
    const mission: Mission = {
      ...current,
      status: 'READY_FOR_AUTHORIZATION',
      reviewed_at: new Date().toISOString(),
      reviewer_name: demoUser.name,
      updated_at: new Date().toISOString(),
    };
    updateOrder({
      ...findOrder(current.order_id),
      status: 'WAITING_FLIGHT_AUTHORIZATION',
      updated_at: new Date().toISOString(),
    });
    return updateMission(mission);
  },
  async authorizeFlight(id, input: FlightAuthorizationInput) {
    await wait();
    const current = findMission(id);
    if (current.status !== 'READY_FOR_AUTHORIZATION') {
      throw new ApiError('A missão ainda não está pronta para autorização.', 409);
    }
    if (Object.values(input.checklist).some((value) => !value)) {
      throw new ApiError('Todos os itens do checklist são obrigatórios.', 422);
    }
    const now = new Date();
    const mission: Mission = {
      ...current,
      status: 'AUTHORIZED',
      vehicle_id: input.vehicle_id,
      authorization: {
        id: `auth-demo-${crypto.randomUUID()}`,
        admin_name: demoUser.name,
        operator_name: input.operator_name,
        authorized_at: now.toISOString(),
        expires_at: new Date(now.getTime() + 5 * 60_000).toISOString(),
      },
      updated_at: now.toISOString(),
    };
    addEvent({
      type: 'FLIGHT_AUTHORIZED',
      severity: 'WARNING',
      message: 'Autorização de voo criada no modo demonstração; nenhum veículo foi acionado.',
      actor: demoUser.name,
      mission_id: id,
      vehicle_id: input.vehicle_id,
    });
    return updateMission(mission);
  },
  async abortMission(id, reason) {
    await wait();
    const current = findMission(id);
    if (reason.trim().length < 10) {
      throw new ApiError('Informe uma justificativa para abortar.', 422);
    }
    return updateMission({
      ...current,
      status: 'ABORTED',
      updated_at: new Date().toISOString(),
    });
  },
  async requestRtl(id, reason) {
    await wait();
    if (reason.trim().length < 10) {
      throw new ApiError('Informe uma justificativa para solicitar RTL.', 422);
    }
    const current = findMission(id);
    addEvent({
      type: 'RTL_REQUESTED',
      severity: 'CRITICAL',
      message: `RTL solicitado no modo demo: ${reason.trim()}`,
      actor: demoUser.name,
      mission_id: id,
      vehicle_id: current.vehicle_id,
    });
    return copy(current);
  },
  async exportMission(id) {
    await wait();
    const mission = findMission(id);
    const rows = [
      'QGC WPL 110',
      ...mission.waypoints.map(
        (waypoint) =>
          `${waypoint.sequence}\t0\t3\t16\t0\t0\t0\t0\t${waypoint.latitude}\t${waypoint.longitude}\t${waypoint.altitude_m}\t1`,
      ),
    ];
    const url = URL.createObjectURL(
      new Blob([rows.join('\n')], { type: 'text/plain;charset=utf-8' }),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = `missao-demo-${id}.waypoints`;
    link.click();
    URL.revokeObjectURL(url);
  },
  async listVehicles() {
    await wait();
    return [copy(DEMO_VEHICLE)];
  },
  async getVehicleHealth(id) {
    await wait();
    if (id !== DEMO_VEHICLE.id) {
      throw new ApiError('Veículo não encontrado no modo demo.', 404);
    }
    return copy(DEMO_HEALTH);
  },
  async listEvents() {
    await wait();
    return copy(events);
  },
  async listTelemetry(missionId) {
    await wait();
    return copy(
      missionId
        ? DEMO_TELEMETRY.filter((item) => item.mission_id === missionId)
        : DEMO_TELEMETRY,
    );
  },
};
