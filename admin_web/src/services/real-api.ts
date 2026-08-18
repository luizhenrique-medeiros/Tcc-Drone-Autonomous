import { ApiError } from './api-error';
import { appConfig } from './config';
import type {
  AdminApi,
  AdminUser,
  AuthSession,
  EventSeverity,
  FlightAuthorizationInput,
  LoginInput,
  Mission,
  MissionAuthorization,
  MissionStatus,
  OperationalMetadata,
  OperationalSource,
  Order,
  OrderStatus,
  SystemEvent,
  TelemetryPoint,
  Vehicle,
  VehicleHealth,
  Waypoint,
} from './contracts';
import { sessionToken } from './session';

interface ApiErrorBody {
  code?: string;
  detail?: string;
  fields?: Record<string, string | string[]>;
}

export interface BackendAdminOrder {
  id: string;
  status: OrderStatus;
  subtotal: string | number;
  delivery_fee: string | number;
  discount: string | number;
  total: string | number;
  simulated_payment_method: string;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
  estimated_distance_m: number;
  mission_id?: string | null;
  customer: { id: string; name: string; email: string; phone?: string | null };
  items: Array<{
    id: string;
    product_name: string;
    unit_price: string | number;
    quantity: number;
    subtotal: string | number;
  }>;
  delivery_point: {
    latitude: number;
    longitude: number;
    label?: string | null;
    searched_address?: string | null;
    reference_address?: string | null;
    approximate_latitude?: number | null;
    approximate_longitude?: number | null;
    instructions?: string | null;
    selection_source: string;
    map_type: string;
    customer_confirmed: boolean;
    controlled_area_confirmed: boolean;
  };
  admin_decision?: {
    decision: 'APPROVED' | 'REJECTED';
    reason?: string | null;
    admin_name: string;
    created_at: string;
  } | null;
}

interface RawWaypoint {
  id: string;
  sequence: number;
  command: number;
  latitude: string | number;
  longitude: string | number;
  altitude_m: string | number;
  label: string;
}

interface RawMissionAuthorization {
  id: string;
  administrator_id: string;
  administrator_name: string;
  operator_name: string;
  status: 'ACTIVE' | 'CONSUMED' | 'EXPIRED' | 'REVOKED';
  mission_version: number;
  issued_at: string;
  expires_at: string;
  used_at?: string | null;
}

export interface RawMission {
  id: string;
  order_id: string;
  vehicle_id?: string | null;
  status: MissionStatus;
  origin_latitude: string | number;
  origin_longitude: string | number;
  destination_latitude: string | number;
  destination_longitude: string | number;
  takeoff_altitude_m: string | number;
  estimated_distance_m: string | number;
  mission_sha256: string;
  version: number;
  exported_at?: string | null;
  reviewed_by_id?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
  created_at: string;
  updated_at: string;
  waypoints: RawWaypoint[];
  authorization?: RawMissionAuthorization | null;
}

interface RawAuthorizationResult {
  mission: RawMission;
  authorization: {
    id: string;
    status: string;
    mission_version: number;
    issued_at: string;
    expires_at: string;
  };
}

interface RawVehicle {
  id: string;
  identifier: string;
  name: string;
  autopilot_system: string;
  autopilot_version?: string | null;
  operational_source?: string | null;
  gateway_id: string;
  status: 'UNKNOWN' | 'OFFLINE' | 'ONLINE' | 'BUSY' | 'ERROR';
  last_communication_at?: string | null;
}

export interface BackendVehicleHealth {
  vehicle_id: string;
  connected: boolean | null;
  heartbeat: boolean | null;
  gps_fix_type: number | null;
  satellites: number | null;
  ekf_ok: boolean | null;
  battery_percent: number | null;
  battery_voltage?: number | null;
  flight_mode: string | null;
  armed: boolean | null;
  preflight_ok: boolean | null;
  rtl_configured: boolean | null;
  geofence_enabled: boolean | null;
  origin_latitude?: string | number | null;
  origin_longitude?: string | number | null;
  current_latitude?: string | number | null;
  current_longitude?: string | number | null;
  current_altitude_m?: number | null;
  connection_state?: string | null;
  connection_mode?: string | null;
  connection_topology?: string | null;
  connection_endpoint?: string | null;
  serial_port?: string | null;
  connection_baud?: number | null;
  mavlink_system_id?: number | null;
  mavlink_component_id?: number | null;
  heartbeat_age_seconds?: number | null;
  last_heartbeat_at?: string | null;
  mission_upload_enabled?: boolean | null;
  flight_commands_enabled?: boolean | null;
  mission_start_enabled?: boolean | null;
  connection_error?: string | null;
  preflight_messages?: string[] | null;
  captured_at: string | null;
  source?: string | null;
  received_at?: string | null;
  is_stale?: boolean | null;
  authorization_limits?: {
    min_battery_percent: number;
    battery_warning_percent: number;
    min_gps_satellites: number;
  } | null;
}

interface RawEvent {
  id: string;
  actor_type?: string;
  order_id?: string | null;
  mission_id?: string | null;
  vehicle_id?: string | null;
  event_type: string;
  severity: EventSeverity;
  message: string;
  created_at: string;
}

export interface BackendTelemetry {
  id: string;
  mission_id: string;
  latitude: string | number | null;
  longitude: string | number | null;
  relative_altitude_m: number | null;
  ground_speed_m_s: number | null;
  battery_percent: number | null;
  satellites: number | null;
  flight_mode: string | null;
  armed: boolean | null;
  recorded_at: string | null;
  source?: string | null;
  received_at?: string | null;
  is_stale?: boolean | null;
}

const numberFromApi = (value: string | number | null | undefined) =>
  value === null || value === undefined ? undefined : Number(value);

const nullableNumberFromApi = (
  value: string | number | null | undefined,
): number | null => {
  if (value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const operationalSources = new Set<OperationalSource>([
  'UNKNOWN',
  'SIMULATION',
  'SITL',
  'HARDWARE_REAL',
]);

const adaptOperationalMetadata = (raw: {
  source?: string | null;
  received_at?: string | null;
  is_stale?: boolean | null;
}): OperationalMetadata => ({
  source: operationalSources.has(raw.source as OperationalSource)
    ? (raw.source as OperationalSource)
    : 'UNKNOWN',
  received_at: raw.received_at ?? null,
  // Contratos antigos ou incompletos nunca podem ser considerados frescos.
  is_stale: raw.is_stale !== false,
});

const commandLabels: Record<number, string> = {
  16: 'WAYPOINT',
  20: 'RTL',
  21: 'LAND',
  22: 'TAKEOFF',
  93: 'DELAY',
};

const adaptWaypoint = (raw: RawWaypoint): Waypoint => ({
  id: raw.id,
  sequence: raw.sequence,
  command: commandLabels[raw.command] ?? `MAV_CMD ${raw.command}`,
  latitude: Number(raw.latitude),
  longitude: Number(raw.longitude),
  altitude_m: Number(raw.altitude_m),
  description: raw.label,
});

const adaptMissionAuthorization = (
  raw: RawMissionAuthorization,
): MissionAuthorization => ({
  id: raw.id,
  administrator_id: raw.administrator_id,
  admin_name: raw.administrator_name,
  operator_name: raw.operator_name,
  status: raw.status,
  mission_version: raw.mission_version,
  authorized_at: raw.issued_at,
  expires_at: raw.expires_at,
  consumed_at: raw.used_at ?? undefined,
});

export const adaptMission = (raw: RawMission): Mission => ({
  id: raw.id,
  order_id: raw.order_id,
  status: raw.status,
  version: raw.version,
  altitude_m: Number(raw.takeoff_altitude_m),
  estimated_distance_m: Number(raw.estimated_distance_m),
  origin: {
    latitude: Number(raw.origin_latitude),
    longitude: Number(raw.origin_longitude),
    label: 'Base de operações',
  },
  destination: {
    latitude: Number(raw.destination_latitude),
    longitude: Number(raw.destination_longitude),
    label: 'Ponto final do cliente',
  },
  waypoints: raw.waypoints.map(adaptWaypoint),
  file_hash: raw.mission_sha256,
  exported_at: raw.exported_at ?? undefined,
  reviewed_at: raw.reviewed_at ?? undefined,
  reviewer_name: raw.reviewed_by_id
    ? `Admin #${raw.reviewed_by_id.slice(0, 8).toUpperCase()}`
    : undefined,
  vehicle_id: raw.vehicle_id ?? undefined,
  authorization: raw.authorization
    ? adaptMissionAuthorization(raw.authorization)
    : undefined,
  created_at: raw.created_at,
  updated_at: raw.updated_at,
});

export const adaptAdminOrder = (raw: BackendAdminOrder): Order => {
  const point = raw.delivery_point;
  return {
    id: raw.id,
    status: raw.status,
    customer: {
      id: raw.customer.id,
      name: raw.customer.name,
      email: raw.customer.email,
      phone: raw.customer.phone ?? undefined,
    },
    items: raw.items.map((item) => ({
      id: item.id,
      product_name: item.product_name,
      quantity: item.quantity,
      unit_price: String(item.unit_price),
      subtotal: String(item.subtotal),
    })),
    delivery_point: {
      latitude: Number(point.latitude),
      longitude: Number(point.longitude),
      label: point.label ?? undefined,
      searched_address: point.searched_address ?? undefined,
      reference_address: point.reference_address ?? undefined,
      approximate_latitude: numberFromApi(point.approximate_latitude),
      approximate_longitude: numberFromApi(point.approximate_longitude),
      instructions: point.instructions ?? undefined,
      selection_source: point.selection_source,
      map_type: point.map_type,
      customer_confirmed: point.customer_confirmed,
      controlled_area_confirmed: point.controlled_area_confirmed,
    },
    subtotal: String(raw.subtotal),
    delivery_fee: String(raw.delivery_fee),
    discount: String(raw.discount),
    total: String(raw.total),
    simulated_payment_method: raw.simulated_payment_method,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    estimated_distance_m: raw.estimated_distance_m,
    mission_id: raw.mission_id ?? undefined,
    admin_decision: raw.admin_decision
      ? {
          decision: raw.admin_decision.decision,
          reason: raw.admin_decision.reason ?? undefined,
          admin_name: raw.admin_decision.admin_name,
          created_at: raw.admin_decision.created_at,
        }
      : undefined,
  };
};

export const adaptVehicle = (raw: RawVehicle): Vehicle => ({
  id: raw.id,
  identifier: raw.identifier,
  name: raw.name,
  system: `${raw.autopilot_system} · ${raw.identifier}`,
  autopilot_system: raw.autopilot_system,
  autopilot_version: raw.autopilot_version ?? null,
  gateway_id: raw.gateway_id,
  operational_source: operationalSources.has(
    raw.operational_source as OperationalSource,
  )
    ? (raw.operational_source as OperationalSource)
    : 'UNKNOWN',
  connected: raw.status === 'ONLINE' || raw.status === 'BUSY',
  status:
    raw.status === 'ONLINE' || raw.status === 'BUSY'
      ? 'ONLINE'
      : raw.status === 'OFFLINE'
        ? 'OFFLINE'
        : 'DEGRADED',
  last_seen_at: raw.last_communication_at ?? '',
});

const gpsFixLabel = (fixType: number | null) => {
  if (fixType === null) return null;
  return fixType >= 4
    ? '3D + DGPS'
    : fixType >= 3
      ? '3D FIX'
      : fixType === 2
        ? '2D FIX'
        : 'SEM FIX';
};

export const adaptVehicleHealth = (
  raw: BackendVehicleHealth,
): VehicleHealth => ({
  ...adaptOperationalMetadata(raw),
  vehicle_id: raw.vehicle_id,
  connected: raw.connected,
  heartbeat_ok: raw.heartbeat,
  flight_mode: raw.flight_mode,
  armed: raw.armed,
  gps_fix: gpsFixLabel(raw.gps_fix_type),
  satellites: raw.satellites,
  ekf_ok: raw.ekf_ok,
  battery_percent: raw.battery_percent,
  battery_voltage: raw.battery_voltage ?? null,
  origin_known:
    raw.origin_latitude !== null &&
    raw.origin_latitude !== undefined &&
    raw.origin_longitude !== null &&
    raw.origin_longitude !== undefined
      ? true
      : null,
  current_latitude: nullableNumberFromApi(raw.current_latitude),
  current_longitude: nullableNumberFromApi(raw.current_longitude),
  current_altitude_m: raw.current_altitude_m ?? null,
  geofence_enabled: raw.geofence_enabled,
  rtl_configured: raw.rtl_configured,
  preflight_ok: raw.preflight_ok,
  preflight_messages:
    raw.preflight_messages ??
    (raw.preflight_ok === false
      ? ['O gateway reportou falha nas verificações pré-voo.']
      : []),
  measured_at: raw.captured_at,
  connection_state: raw.connection_state ?? null,
  connection_mode: raw.connection_mode ?? null,
  connection_topology: raw.connection_topology ?? null,
  connection_endpoint: raw.connection_endpoint ?? null,
  serial_port: raw.serial_port ?? null,
  connection_baud: raw.connection_baud ?? null,
  mavlink_system_id: raw.mavlink_system_id ?? null,
  mavlink_component_id: raw.mavlink_component_id ?? null,
  heartbeat_age_seconds: raw.heartbeat_age_seconds ?? null,
  last_heartbeat_at: raw.last_heartbeat_at ?? null,
  mission_upload_enabled: raw.mission_upload_enabled ?? null,
  flight_commands_enabled: raw.flight_commands_enabled ?? null,
  mission_start_enabled: raw.mission_start_enabled ?? null,
  connection_error: raw.connection_error ?? null,
  authorization_limits: raw.authorization_limits ?? null,
});

export const adaptTelemetryPoint = (
  point: BackendTelemetry,
): TelemetryPoint => ({
  ...adaptOperationalMetadata(point),
  id: point.id,
  mission_id: point.mission_id,
  latitude: nullableNumberFromApi(point.latitude),
  longitude: nullableNumberFromApi(point.longitude),
  altitude_m: point.relative_altitude_m,
  ground_speed_m_s: point.ground_speed_m_s,
  battery_percent: point.battery_percent,
  satellites: point.satellites,
  flight_mode: point.flight_mode,
  armed: point.armed,
  recorded_at: point.recorded_at,
});

const apiRequest = async <T>(
  path: string,
  init: RequestInit = {},
): Promise<T> => {
  const token = sessionToken.get();
  let response: Response;
  try {
    response = await fetch(`${appConfig.apiBaseUrl}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(
      'Não foi possível conectar à API. Verifique o backend e a configuração da URL.',
    );
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Respostas sem JSON ainda são convertidas para um erro previsível.
    }
    if (response.status === 401) sessionToken.clear();
    throw new ApiError(
      body.detail ?? `A API respondeu com erro ${response.status}.`,
      response.status,
      body.code,
      body.fields,
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
};

export const createRequestId = () =>
  globalThis.crypto?.randomUUID?.() ??
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

const post = <T>(path: string, body: object = {}) =>
  apiRequest<T>(path, { method: 'POST', body: JSON.stringify(body) });

const postCritical = <T>(
  path: string,
  body: object = {},
  requestId: string = createRequestId(),
) => {
  return apiRequest<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'Idempotency-Key': requestId },
  });
};

const flightAuthorizationRequestIds = new Map<string, string>();

export const realApi: AdminApi = {
  login: async (input: LoginInput) => {
    const response = await post<AuthSession>('/auth/login', input);
    return response;
  },
  me: () => apiRequest<AdminUser>('/auth/me'),
  listOrders: async (status?: OrderStatus) =>
    (
      await apiRequest<BackendAdminOrder[]>(
        `/admin/orders${status ? `?status=${encodeURIComponent(status)}` : ''}`,
      )
    ).map(adaptAdminOrder),
  getOrder: async (id: string) =>
    adaptAdminOrder(await apiRequest<BackendAdminOrder>(`/admin/orders/${id}`)),
  approveOrder: async (id: string) =>
    adaptAdminOrder(
      await postCritical<BackendAdminOrder>(`/admin/orders/${id}/approve`, {}),
    ),
  rejectOrder: async (id: string, reason: string) =>
    adaptAdminOrder(
      await postCritical<BackendAdminOrder>(`/admin/orders/${id}/reject`, { reason }),
    ),
  prepareMission: async (orderId: string) =>
    adaptMission(
      await postCritical<RawMission>(`/admin/orders/${orderId}/prepare-mission`, {}),
    ),
  getMission: async (id: string) =>
    adaptMission(await apiRequest<RawMission>(`/admin/missions/${id}`)),
  markMissionUnderReview: async (id: string) =>
    adaptMission(
      await postCritical<RawMission>(`/admin/missions/${id}/mark-under-review`, {}),
    ),
  markMissionReviewed: async (id: string) =>
    adaptMission(
      await postCritical<RawMission>(`/admin/missions/${id}/mark-reviewed`, {
        notes: 'Rota revisada visualmente no Mission Planner pelo painel administrativo.',
      }),
    ),
  authorizeFlight: async (id: string, input: FlightAuthorizationInput) => {
    const requestId =
      flightAuthorizationRequestIds.get(id) ?? createRequestId();
    flightAuthorizationRequestIds.set(id, requestId);
    const response = await postCritical<RawAuthorizationResult>(
      `/admin/missions/${id}/authorize-flight`,
      {
        vehicle_id: input.vehicle_id,
        operator_name: input.operator_name,
        controlled_area_confirmed: input.controlled_area_confirmed,
        checklist: input.checklist,
      },
      requestId,
    );
    flightAuthorizationRequestIds.delete(id);
    return adaptMission(response.mission);
  },
  abortMission: async (id: string, reason: string) =>
    adaptMission(
      await postCritical<RawMission>(`/admin/missions/${id}/abort`, { reason }),
    ),
  requestRtl: async (id: string, reason: string) =>
    adaptMission(
      await postCritical<RawMission>(`/admin/missions/${id}/request-rtl`, {
        reason,
      }),
    ),
  requestMissionCommand: async (id, action, reason) =>
    adaptMission(
      await postCritical<RawMission>(
        `/admin/missions/${id}/commands/${action}`,
        { reason },
      ),
    ),
  exportMission: async (id: string) => {
    const token = sessionToken.get();
    const response = await fetch(
      `${appConfig.apiBaseUrl}/admin/missions/${id}/export`,
      {
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    if (!response.ok) {
      throw new ApiError('Não foi possível exportar a missão.', response.status);
    }
    const blobUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = `missao-${id}.waypoints`;
    link.click();
    URL.revokeObjectURL(blobUrl);
  },
  listVehicles: async () =>
    (await apiRequest<RawVehicle[]>('/admin/vehicles')).map(adaptVehicle),
  getVehicleHealth: async (id: string) =>
    adaptVehicleHealth(
      await apiRequest<BackendVehicleHealth>(`/admin/vehicles/${id}/health`),
    ),
  listEvents: async () =>
    (await apiRequest<RawEvent[]>('/admin/events')).map(
      (event): SystemEvent => ({
        id: event.id,
        type: event.event_type,
        severity: event.severity,
        message: event.message,
        actor: event.actor_type,
        order_id: event.order_id ?? undefined,
        mission_id: event.mission_id ?? undefined,
        vehicle_id: event.vehicle_id ?? undefined,
        created_at: event.created_at,
      }),
    ),
  listTelemetry: async (missionId?: string) => {
    if (!missionId) return [];
    return (
      await apiRequest<BackendTelemetry[]>(
        `/admin/missions/${encodeURIComponent(missionId)}/telemetry?limit=200`,
      )
    ).map(adaptTelemetryPoint);
  },
};
