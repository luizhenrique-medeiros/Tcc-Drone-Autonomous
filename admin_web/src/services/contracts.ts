export type Role = 'ADMIN' | 'CUSTOMER';

export type OperationalSource =
  | 'UNKNOWN'
  | 'SIMULATION'
  | 'SITL'
  | 'HARDWARE_REAL';

export interface OperationalMetadata {
  source: OperationalSource;
  received_at: string | null;
  is_stale: boolean;
}

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
  | 'VERIFIED'
  | 'EXECUTING'
  | 'PAUSED'
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
  administrator_id?: string;
  admin_name: string;
  operator_name: string;
  status?: 'ACTIVE' | 'CONSUMED' | 'EXPIRED' | 'REVOKED';
  mission_version?: number;
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
  identifier: string;
  name: string;
  system: string;
  autopilot_system: string;
  autopilot_version: string | null;
  gateway_id: string;
  operational_source: OperationalSource;
  connected: boolean;
  status: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
  last_seen_at: string;
}

export interface VehicleAuthorizationLimits {
  min_battery_percent: number;
  battery_warning_percent: number;
  min_gps_satellites: number;
}

export interface VehicleHealth extends OperationalMetadata {
  vehicle_id: string;
  connected: boolean | null;
  heartbeat_ok: boolean | null;
  flight_mode: string | null;
  armed: boolean | null;
  gps_fix: string | null;
  satellites: number | null;
  ekf_ok: boolean | null;
  battery_percent: number | null;
  battery_voltage: number | null;
  origin_known: boolean | null;
  current_latitude: number | null;
  current_longitude: number | null;
  current_altitude_m: number | null;
  geofence_enabled: boolean | null;
  rtl_configured: boolean | null;
  preflight_ok: boolean | null;
  preflight_messages: string[];
  measured_at: string | null;
  connection_state: string | null;
  connection_mode: string | null;
  connection_topology: string | null;
  connection_endpoint: string | null;
  serial_port: string | null;
  connection_baud: number | null;
  mavlink_system_id: number | null;
  mavlink_component_id: number | null;
  heartbeat_age_seconds: number | null;
  last_heartbeat_at: string | null;
  mission_upload_enabled: boolean | null;
  flight_commands_enabled: boolean | null;
  mission_start_enabled: boolean | null;
  connection_error: string | null;
  authorization_limits: VehicleAuthorizationLimits | null;
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

export interface TelemetryPoint extends OperationalMetadata {
  id: string;
  mission_id: string;
  latitude: number | null;
  longitude: number | null;
  altitude_m: number | null;
  ground_speed_m_s: number | null;
  battery_percent: number | null;
  satellites: number | null;
  flight_mode: string | null;
  armed: boolean | null;
  recorded_at: string | null;
}

export interface HumanFlightConfirmations {
  area_and_conditions_clear: boolean;
  aircraft_and_payload_inspected: boolean;
  operator_ready: boolean;
}

export interface FlightAuthorizationInput {
  vehicle_id: string;
  operator_name: string;
  controlled_area_confirmed: true;
  checklist: HumanFlightConfirmations;
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
  requestMissionCommand(
    id: string,
    action: 'START' | 'PAUSE' | 'CONTINUE',
    reason: string,
  ): Promise<Mission>;
  exportMission(id: string): Promise<void>;
  listVehicles(): Promise<Vehicle[]>;
  getVehicleHealth(id: string): Promise<VehicleHealth>;
  listEvents(): Promise<SystemEvent[]>;
  listTelemetry(missionId?: string): Promise<TelemetryPoint[]>;
}
