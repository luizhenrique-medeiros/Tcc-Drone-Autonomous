export type Role = 'ADMIN' | 'CUSTOMER';

export type OrderStatus =
  | 'DRAFT'
  | 'PENDING_ADMIN_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'MISSION_PREPARING'
  | 'MISSION_READY'
  | 'WAITING_FLIGHT_AUTHORIZATION'
  | 'MISSION_UPLOADING'
  | 'IN_TRANSIT'
  | 'AT_DESTINATION'
  | 'DELIVERED'
  | 'RETURNING'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'FAILED';

export type MissionStatus =
  | 'DRAFT'
  | 'PENDING_VALIDATION'
  | 'GENERATED'
  | 'EXPORTED_TO_MISSION_PLANNER'
  | 'UNDER_REVIEW'
  | 'READY_FOR_AUTHORIZATION'
  | 'AUTHORIZED'
  | 'UPLOADING'
  | 'UPLOADED'
  | 'EXECUTING'
  | 'DESTINATION_REACHED'
  | 'DELIVERY_CONFIRMED'
  | 'RETURNING'
  | 'COMPLETED'
  | 'ABORTED'
  | 'FAILED';

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export interface AuthSession {
  access_token: string;
  token_type: 'bearer';
  expires_in?: number;
  user: AdminUser;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface Coordinates {
  latitude: number;
  longitude: number;
  label?: string;
}

export interface DeliveryPoint extends Coordinates {
  searched_address?: string;
  reference_address?: string;
  approximate_latitude?: number;
  approximate_longitude?: number;
  instructions?: string;
  selection_source?: string;
  map_type?: string;
  customer_confirmed: boolean;
  controlled_area_confirmed: boolean;
}

export interface OrderItem {
  id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  subtotal: string;
}

export interface CustomerSummary {
  id: string;
  name: string;
  email: string;
  phone?: string;
}

export interface AdminDecision {
  decision: 'APPROVED' | 'REJECTED';
  reason?: string;
  admin_name: string;
  created_at: string;
}

export interface Order {
  id: string;
  status: OrderStatus;
  customer: CustomerSummary;
  items: OrderItem[];
  delivery_point: DeliveryPoint;
  subtotal: string;
  delivery_fee: string;
  discount: string;
  total: string;
  simulated_payment_method: string;
  created_at: string;
  updated_at: string;
  estimated_distance_m?: number;
  mission_id?: string;
  admin_decision?: AdminDecision;
}

export interface Waypoint extends Coordinates {
  id: string;
  sequence: number;
  command: string;
  altitude_m: number;
  description: string;
}

export interface MissionAuthorization {
  id: string;
  admin_name: string;
  operator_name: string;
  authorized_at: string;
  expires_at: string;
  consumed_at?: string;
}

export interface Mission {
  id: string;
  order_id: string;
  status: MissionStatus;
  version: number;
  altitude_m: number;
  estimated_distance_m: number;
  origin: Coordinates;
  destination: Coordinates;
  waypoints: Waypoint[];
  file_hash?: string;
  exported_at?: string;
  reviewed_at?: string;
  reviewer_name?: string;
  vehicle_id?: string;
  authorization?: MissionAuthorization;
  created_at: string;
  updated_at: string;
}

export interface Vehicle {
  id: string;
  name: string;
  system: string;
  connected: boolean;
  status: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
  last_seen_at: string;
}

export interface VehicleHealth {
  vehicle_id: string;
  connected: boolean;
  heartbeat_ok: boolean;
  flight_mode: string;
  armed: boolean;
  gps_fix: string;
  satellites: number;
  ekf_ok: boolean;
  battery_percent: number;
  battery_voltage?: number;
  origin_known: boolean;
  geofence_enabled: boolean;
  rtl_configured: boolean;
  preflight_ok: boolean;
  preflight_messages: string[];
  measured_at: string;
}

export type EventSeverity = 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface SystemEvent {
  id: string;
  type: string;
  severity: EventSeverity;
  message: string;
  actor?: string;
  order_id?: string;
  mission_id?: string;
  vehicle_id?: string;
  created_at: string;
}

export interface TelemetryPoint extends Coordinates {
  id: string;
  mission_id: string;
  altitude_m: number;
  ground_speed_m_s: number;
  battery_percent: number;
  satellites: number;
  flight_mode: string;
  armed: boolean;
  recorded_at: string;
}

export interface PreflightChecklist {
  mission_reviewed: boolean;
  route_matches_destination: boolean;
  controlled_area_confirmed: boolean;
  weather_checked: boolean;
  payload_secured: boolean;
  people_clear: boolean;
  operator_ready: boolean;
  rtl_area_clear: boolean;
}

export interface FlightAuthorizationInput {
  vehicle_id: string;
  operator_name: string;
  controlled_area_confirmed: true;
  checklist: PreflightChecklist;
}

export interface AdminApi {
  login(input: LoginInput): Promise<AuthSession>;
  me(): Promise<AdminUser>;
  listOrders(status?: OrderStatus): Promise<Order[]>;
  getOrder(id: string): Promise<Order>;
  approveOrder(id: string): Promise<Order>;
  rejectOrder(id: string, reason: string): Promise<Order>;
  prepareMission(orderId: string): Promise<Mission>;
  getMission(id: string): Promise<Mission>;
  markMissionUnderReview(id: string): Promise<Mission>;
  markMissionReviewed(id: string): Promise<Mission>;
  authorizeFlight(id: string, input: FlightAuthorizationInput): Promise<Mission>;
  abortMission(id: string, reason: string): Promise<Mission>;
  requestRtl(id: string, reason: string): Promise<Mission>;
  exportMission(id: string): Promise<void>;
  listVehicles(): Promise<Vehicle[]>;
  getVehicleHealth(id: string): Promise<VehicleHealth>;
  listEvents(): Promise<SystemEvent[]>;
  listTelemetry(missionId?: string): Promise<TelemetryPoint[]>;
}
