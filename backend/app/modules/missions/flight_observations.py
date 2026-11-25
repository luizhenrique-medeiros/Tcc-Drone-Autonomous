from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import OperationalSource, OrderStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.delivery_points.service import haversine_distance_m
from app.modules.missions.models import Mission, ObservedFlight
from app.modules.missions.qgroundcontrol_plan import QGC_EXPORT_EVENT
from app.modules.missions.service import (
    _observation_time,
    match_physical_plan,
    reviewed_px4_artifact,
)
from app.modules.orders.models import Order
from app.modules.system_events.models import SystemEvent
from app.modules.system_events.schemas import SystemEventRead
from app.modules.system_events.service import record_event
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle, VehicleHealthSnapshot
from app.modules.vehicles.schemas import Px4FlightObservation, VehicleHealthInput
from app.modules.vehicles.service import health_is_stale

Phase = Literal[
    "WAITING",
    "ARMED",
    "ARMED_ON_GROUND",
    "TAKING_OFF",
    "AIRBORNE",
    "MANUAL",
    "MISSION",
    "PAUSED",
    "RETURNING",
    "LANDING",
    "LANDED",
    "DISARMED",
]
Link = Literal["UNASSOCIATED", "OPERATOR", "VERIFIED", "DIVERGENT"]
_OUTBOUND_MODES = {"MANUAL", "STABILIZED", "STABILIZE", "ALTCTL", "POSCTL", "ACRO", "RATTITUDE"}
_MISSION_MODES = {"MISSION", "AUTO.MISSION"}
_RETURN_MODES = {"RTL", "AUTO.RTL"}
_POINT_RADIUS_M = 8.0
_POSITION_CONFIRMATION = timedelta(seconds=2)
_MAX_POSITION_GAP = timedelta(seconds=5)
_PX4_OBSERVATION_SOURCES = {OperationalSource.HARDWARE_REAL, OperationalSource.SITL}


class TrackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: UUID
    expected_version: int = Field(ge=1)
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class FlightPoint(BaseModel):
    latitude: float
    longitude: float
    recorded_at: datetime


class FlightEvidence(BaseModel):
    source: OperationalSource = OperationalSource.HARDWARE_REAL
    phase: Phase = "WAITING"
    estimated: bool = False
    link: Link = "UNASSOCIATED"
    revision: int | None = None
    mission_sha256: str | None = None
    exported_plan_sha256: str | None = None
    verified_plan_sha256: str | None = None
    associated_at: datetime | None = None
    associated_by: str | None = None
    expected_items: list[int] = Field(default_factory=list)
    mapping_current: bool = False
    destination_sequence: int | None = None
    return_sequence: int | None = None
    native_plan_id: int | None = None
    mission_total: int | None = None
    sequence: int | None = None
    reached_sequences: list[int] = Field(default_factory=list)
    mission_state: int | None = None
    landed_state: int | None = None
    armed: bool | None = None
    mode: str | None = None
    lost: bool = False
    had_gap: bool = False
    last_seen_at: datetime | None = None
    system_id: int | None = None
    component_id: int | None = None
    ground_altitude: float | None = None
    rise_since: datetime | None = None
    near_since: datetime | None = None
    last_position_at: datetime | None = None
    point: FlightPoint | None = None
    altitude_m: float | None = None
    speed_m_s: float | None = None
    distance_m: float | None = None
    takeoff_at: datetime | None = None
    airborne_at: datetime | None = None
    flight_estimated: bool = False
    mission_at: datetime | None = None
    return_at: datetime | None = None
    early_return: bool = False
    land_at: datetime | None = None
    destination: Literal["CONFIRMED", "ESTIMATED"] | None = None
    mission_finished_reported: bool = False
    normal_completion: bool = False


class ObservedFlightRead(BaseModel):
    id: UUID
    vehicle_id: UUID
    vehicle_name: str | None
    source: OperationalSource
    mission_id: UUID | None
    ended_at: datetime | None
    stale: bool
    phase: Phase
    estimated: bool
    link: Link
    revision: int | None
    associated_at: datetime | None
    associated_by: str | None
    last_seen_at: datetime | None
    armed: bool | None
    mode: str | None
    landed_state: int | None
    mission_state: int | None
    sequence: int | None
    mapping_current: bool
    destination_sequence: int | None
    return_sequence: int | None
    reached_sequences: list[int]
    destination: Literal["CONFIRMED", "ESTIMATED"] | None
    early_return: bool
    mission_finished_reported: bool
    normal_completion: bool
    point: FlightPoint | None
    altitude_m: float | None
    speed_m_s: float | None
    distance_m: float | None
    track: list[list[FlightPoint]]
    events: list[SystemEventRead]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _latest(
    session: Session,
    *,
    vehicle_id: UUID | None = None,
    mission_id: UUID | None = None,
    active: bool = False,
) -> ObservedFlight | None:
    query = select(ObservedFlight)
    if vehicle_id is not None:
        query = query.where(ObservedFlight.vehicle_id == vehicle_id)
    if mission_id is not None:
        query = query.where(ObservedFlight.mission_id == mission_id)
    if active:
        query = query.where(ObservedFlight.ended_at.is_(None))
    return session.scalar(
        query.order_by(ObservedFlight.created_at.desc(), ObservedFlight.id.desc()).limit(1)
    )


def _event(
    session: Session,
    flight: ObservedFlight,
    event_type: str,
    text: str,
    at: datetime,
    *,
    admin: User | None = None,
    **metadata: str | int | bool | None,
) -> None:
    mission = session.get(Mission, flight.mission_id) if flight.mission_id else None
    record_event(
        session,
        event_type=event_type,
        message=text,
        actor_type="ADMIN" if admin else "GATEWAY",
        actor_user_id=admin.id if admin else None,
        order_id=mission.order_id if mission else None,
        mission_id=flight.mission_id,
        vehicle_id=flight.vehicle_id,
        metadata={"flight_id": str(flight.id), "observed_at": at.isoformat(), **metadata},
    )


def _bind(flight: ObservedFlight, state: FlightEvidence, mission: Mission) -> None:
    flight.mission_id = mission.id
    state.revision = mission.version
    state.mission_sha256 = mission.mission_sha256


def track_mission(
    session: Session,
    mission_id: UUID,
    payload: TrackRequest,
    admin: User,
    settings: Settings,
) -> None:
    # Heartbeat ingestion and association lock the vehicle before examining an open flight.
    vehicle = session.get(Vehicle, payload.vehicle_id, with_for_update=True)
    mission = session.get(Mission, mission_id, with_for_update=True)
    if not vehicle or not mission:
        raise NotFoundError("Veículo ou missão não encontrado")
    if (mission.version, mission.mission_sha256) != (
        payload.expected_version,
        payload.expected_sha256,
    ):
        raise ConflictError("A revisão mudou. Atualize o acompanhamento antes de associar.")
    order = session.get(Order, mission.order_id)
    if not order or order.status in {
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.COMPLETED,
    }:
        raise ConflictError("O pedido não está disponível para novo acompanhamento.")
    export = session.scalar(
        select(SystemEvent)
        .where(
            SystemEvent.mission_id == mission.id,
            SystemEvent.event_type == QGC_EXPORT_EVENT,
            SystemEvent.event_metadata["mission_version"].as_integer() == mission.version,
            SystemEvent.event_metadata["mission_sha256"].as_string() == mission.mission_sha256,
        )
        .order_by(SystemEvent.created_at.desc())
        .limit(1)
    )
    if export is None:
        raise ConflictError("Baixe o .plan da revisão atual antes de acompanhar a missão.")
    health = session.scalar(
        select(VehicleHealthSnapshot)
        .where(
            VehicleHealthSnapshot.vehicle_id == vehicle.id,
        )
        .order_by(VehicleHealthSnapshot.captured_at.desc())
        .limit(1)
    )
    if (
        not health
        or vehicle.autopilot_system.upper() != "PX4"
        or health.source not in _PX4_OBSERVATION_SOURCES
        or not health.connected
        or not health.heartbeat
        or health_is_stale(health, settings)
        or not health.mavlink_system_id
        or not health.mavlink_component_id
    ):
        raise ConflictError("Selecione um PX4 real ou SITL com heartbeat recente e IDs MAVLink.")
    active = _latest(session, vehicle_id=vehicle.id, active=True)
    other = _latest(session, mission_id=mission.id, active=True)
    if other is not None and other.vehicle_id != vehicle.id:
        raise ConflictError("A missão já está sendo acompanhada em outro veículo.")
    now = datetime.now(UTC)
    if active is not None and active.mission_id not in {None, mission.id}:
        existing = FlightEvidence.model_validate(active.evidence)
        if existing.armed or existing.airborne_at or existing.takeoff_at:
            raise ConflictError("Este veículo já está sendo acompanhado em outra missão ativa.")
        active.ended_at = now
        _event(
            session,
            active,
            "FLIGHT_ASSOCIATION_REPLACED",
            "Acompanhamento substituído antes do voo.",
            now,
            admin=admin,
        )
        active = None
    flight = active or ObservedFlight(vehicle_id=vehicle.id, evidence={})
    if active is None:
        session.add(flight)
        session.flush()
    state = FlightEvidence.model_validate(flight.evidence)
    if active is not None and state.source != health.source:
        raise ConflictError("A origem da telemetria mudou nesta sessão.")
    if flight.mission_id == mission.id:
        if state.revision == mission.version and state.link in {"OPERATOR", "VERIFIED"}:
            return
        raise ConflictError(
            "A associação anterior deve encerrar antes de acompanhar outra revisão."
        )
    if state.system_id is not None and (state.system_id, state.component_id) != (
        health.mavlink_system_id,
        health.mavlink_component_id,
    ):
        raise ConflictError("A identidade MAVLink da sessão mudou.")
    _bind(flight, state, mission)
    state.link = "OPERATOR"
    state.source = health.source
    state.associated_at = now
    state.associated_by = admin.name
    state.system_id = health.mavlink_system_id
    state.component_id = health.mavlink_component_id
    state.exported_plan_sha256 = str(export.event_metadata["plan_sha256"])
    flight.evidence = state.model_dump(mode="json")
    _event(
        session,
        flight,
        "FLIGHT_ASSOCIATED",
        "Acompanhamento associado pelo administrador.",
        now,
        admin=admin,
        mission_version=mission.version,
        mission_sha256=mission.mission_sha256,
        exported_plan_sha256=state.exported_plan_sha256,
        export_event_id=str(export.id),
        system_id=state.system_id,
        component_id=state.component_id,
    )
    session.commit()


def _apply_plan_evidence(
    session: Session,
    vehicle: Vehicle,
    flight: ObservedFlight,
    state: FlightEvidence,
    current: Px4FlightObservation,
    at: datetime,
) -> None:
    if state.link == "DIVERGENT" or current.mission_at is None:
        return
    if state.mission_at and (
        (
            current.native_plan_id is not None
            and state.native_plan_id is not None
            and current.native_plan_id != state.native_plan_id
        )
        or (
            current.mission_total is not None
            and state.mission_total is not None
            and current.mission_total != state.mission_total
        )
        or current.mission_state == 1
    ):
        state.link = "DIVERGENT" if flight.mission_id else "UNASSOCIATED"
        state.reached_sequences = []
        state.destination = None
        state.early_return = False
        state.mission_finished_reported = False
        state.native_plan_id = current.native_plan_id
        state.mission_total = current.mission_total
        _event(
            session, flight, "FLIGHT_PLAN_CHANGED", "O PX4 informou mudança no plano observado.", at
        )
        return
    if (
        state.link != "VERIFIED"
        and current.native_plan_id is not None
        and state.native_plan_id is None
    ):
        match = match_physical_plan(
            session,
            vehicle,
            native_id=current.native_plan_id,
            sequence=current.sequence,
            system_id=state.system_id,
            component_id=state.component_id,
            observed_at=_utc(current.mission_at),
        )
        if match is not None:
            mission, review, verification = match
            if flight.mission_id not in {None, mission.id}:
                state.link = "DIVERGENT"
                state.destination = None
                _event(
                    session,
                    flight,
                    "FLIGHT_PLAN_CHANGED",
                    "O plano verificado pertence a outra missão.",
                    at,
                )
                return
            session.get(Mission, mission.id, with_for_update=True)
            other = _latest(session, mission_id=mission.id, active=True)
            if other is not None and other.vehicle_id != vehicle.id:
                return
            try:
                items = json.loads(reviewed_px4_artifact(mission, review).content)["items"]
            except ConflictError:
                return
            if len(items) == verification.event_metadata[
                "item_count"
            ] and current.mission_total in {None, len(items)}:
                _bind(flight, state, mission)
                state.link = "VERIFIED"
                state.associated_at = state.associated_at or at
                state.verified_plan_sha256 = str(review.event_metadata["plan_sha256"])
                state.expected_items = [item["command"] for item in items]
                destinations = [
                    item["sequence"]
                    for item in items
                    if item["command"] == 16
                    and abs(float(item["params"][4]) - float(mission.destination_latitude))
                    <= 0.000001
                    and abs(float(item["params"][5]) - float(mission.destination_longitude))
                    <= 0.000001
                ]
                state.destination_sequence = destinations[0] if len(destinations) == 1 else None
                state.return_sequence = next(
                    (item["sequence"] for item in items if item["command"] == 20), None
                )
                _event(
                    session,
                    flight,
                    "FLIGHT_PLAN_VERIFIED",
                    "Identificador e itens vinculados à revisão verificada.",
                    at,
                    verified_plan_sha256=state.verified_plan_sha256,
                    native_plan_id=current.native_plan_id,
                    mission_version=mission.version,
                )
    state.native_plan_id = current.native_plan_id or state.native_plan_id
    state.mission_total = current.mission_total or state.mission_total


def _sample_position(
    state: FlightEvidence,
    snapshot: VehicleHealthSnapshot,
    current: Px4FlightObservation,
    mission: Mission | None,
    at: datetime,
) -> datetime | None:
    state.altitude_m = snapshot.current_altitude_m
    state.speed_m_s = snapshot.current_ground_speed_m_s
    state.point = None
    state.distance_m = None
    if snapshot.current_latitude is None or snapshot.current_longitude is None:
        return None
    position_at = _utc(current.position_at) if current.position_at else None
    if position_at and not at - _MAX_POSITION_GAP <= position_at <= at + timedelta(seconds=2):
        state.altitude_m = None
        state.speed_m_s = None
        return None
    latitude, longitude = float(snapshot.current_latitude), float(snapshot.current_longitude)
    state.point = FlightPoint(latitude=latitude, longitude=longitude, recorded_at=position_at or at)
    valid_fix = snapshot.gps_fix_type is None or snapshot.gps_fix_type >= 3
    if mission is not None and state.link != "DIVERGENT" and valid_fix:
        state.distance_m = float(
            haversine_distance_m(
                latitude,
                longitude,
                float(mission.destination_latitude),
                float(mission.destination_longitude),
            )
        )
    return position_at if valid_fix else None


def _estimate_airborne(
    state: FlightEvidence,
    snapshot: VehicleHealthSnapshot,
    position_at: datetime | None,
    landed_state: int | None,
) -> bool:
    if landed_state is not None or not snapshot.armed or state.ground_altitude is None:
        state.rise_since = None
        return False
    if (
        position_at is None
        or snapshot.current_altitude_m is None
        or snapshot.current_altitude_m - state.ground_altitude < 3
        or (snapshot.current_ground_speed_m_s or 0) < 1.5
    ):
        state.rise_since = None
        return False
    if state.last_position_at and position_at - state.last_position_at > _MAX_POSITION_GAP:
        state.rise_since = None
    state.rise_since = state.rise_since or position_at
    return position_at - state.rise_since >= _POSITION_CONFIRMATION


def _phase(
    session: Session,
    flight: ObservedFlight,
    state: FlightEvidence,
    phase: Phase,
    at: datetime,
    text: str,
    *,
    estimated: bool = False,
) -> None:
    if state.phase != phase:
        _event(session, flight, f"FLIGHT_{phase}", text, at, estimated=estimated)
    state.phase = phase
    state.estimated = estimated


def _update_phase(
    session: Session,
    flight: ObservedFlight,
    state: FlightEvidence,
    current: Px4FlightObservation,
    at: datetime,
    *,
    rising: bool,
) -> None:
    if state.armed is False and state.phase == "DISARMED" and current.landed_state is None:
        return
    has_air_evidence = current.landed_state in {2, 4} or state.airborne_at is not None or rising
    if rising and state.airborne_at is None:
        state.flight_estimated = True
        state.takeoff_at = at
        _phase(
            session,
            flight,
            state,
            "TAKING_OFF",
            at,
            "Decolagem estimada pela posição e velocidade.",
            estimated=True,
        )
    if current.landed_state == 3:
        state.takeoff_at = state.takeoff_at or at
        _phase(session, flight, state, "TAKING_OFF", at, "PX4 informou decolagem.")
        return
    if current.landed_state == 1:
        if state.airborne_at or state.takeoff_at:
            state.land_at = state.land_at or at
            _phase(
                session, flight, state, "LANDED", at, "PX4 informou aeronave em solo após o voo."
            )
        elif state.armed:
            _phase(session, flight, state, "ARMED_ON_GROUND", at, "Aeronave armada em solo.")
        return
    if has_air_evidence and state.land_at is None:
        if current.landed_state in {2, 4}:
            state.flight_estimated = False
        if state.airborne_at is None:
            state.airborne_at = at
            _phase(
                session,
                flight,
                state,
                "AIRBORNE",
                at,
                "Aeronave observada em voo.",
                estimated=state.flight_estimated,
            )
        mode = (state.mode or "").upper()
        if (
            state.mission_at
            and current.mission_state == 5
            and state.link != "DIVERGENT"
            and (state.link != "VERIFIED" or state.mapping_current)
        ):
            if not state.mission_finished_reported:
                _event(
                    session,
                    flight,
                    "FLIGHT_MISSION_COMPLETE_REPORTED",
                    "PX4 informou itens da missão concluídos.",
                    at,
                )
            state.mission_finished_reported = True
        returning_item = (
            state.mapping_current
            and state.return_sequence is not None
            and current.sequence == state.return_sequence
            and mode in _MISSION_MODES
            and current.mission_state in {None, 3}
            and current.mission_mode != 2
        )
        if current.landed_state == 4 or mode in {"LAND", "AUTO.LAND"}:
            _phase(
                session,
                flight,
                state,
                "LANDING",
                at,
                "PX4 informou pouso em andamento."
                if current.landed_state == 4
                else "Modo de pouso informado pelo PX4.",
                estimated=state.flight_estimated,
            )
        elif mode in _RETURN_MODES or returning_item:
            if not state.return_at:
                state.return_at = at
                sequence = current.sequence
                state.early_return = (
                    state.mapping_current
                    and not state.had_gap
                    and state.mission_at is not None
                    and state.destination is None
                    and state.destination_sequence is not None
                    and sequence is not None
                    and sequence < state.destination_sequence
                    and state.destination_sequence not in state.reached_sequences
                )
            _phase(
                session,
                flight,
                state,
                "RETURNING",
                at,
                "Retorno antecipado observado." if state.early_return else "Retorno observado.",
                estimated=state.flight_estimated,
            )
        elif (
            state.mission_at
            and current.mission_state == 4
            and mode in (_MISSION_MODES | {"LOITER", "HOLD"})
        ):
            _phase(
                session,
                flight,
                state,
                "PAUSED",
                at,
                "PX4 informou missão pausada.",
                estimated=state.flight_estimated,
            )
        elif (
            state.armed
            and mode in _MISSION_MODES
            and current.mission_mode != 2
            and current.mission_state not in {1, 2, 4, 5}
        ):
            state.mission_at = state.mission_at or at
            _phase(
                session,
                flight,
                state,
                "MISSION",
                at,
                "Execução da missão observada.",
                estimated=state.flight_estimated,
            )
        elif mode in _OUTBOUND_MODES:
            _phase(
                session,
                flight,
                state,
                "MANUAL",
                at,
                "Voo em modo manual ou assistido.",
                estimated=state.flight_estimated,
            )
        else:
            _phase(
                session,
                flight,
                state,
                "AIRBORNE",
                at,
                "Aeronave em voo.",
                estimated=state.flight_estimated,
            )


def observe_heartbeat(
    session: Session,
    vehicle: Vehicle,
    snapshot: VehicleHealthSnapshot,
    payload: VehicleHealthInput,
    settings: Settings,
) -> None:
    if snapshot.source not in _PX4_OBSERVATION_SOURCES:
        return
    flight = _latest(session, vehicle_id=vehicle.id, active=True)
    at = _utc(snapshot.received_at)
    if not snapshot.connected or not snapshot.heartbeat or health_is_stale(snapshot, settings):
        if flight is not None:
            state = FlightEvidence.model_validate(flight.evidence)
            if state.last_seen_at and not state.lost and at > state.last_seen_at:
                state.lost = True
                _event(
                    session, flight, "FLIGHT_LINK_LOST", "Telemetria do veículo interrompida.", at
                )
                flight.evidence = state.model_dump(mode="json")
        return
    if vehicle.autopilot_system.upper() != "PX4" or snapshot.armed is None:
        return
    system, component = snapshot.mavlink_system_id, snapshot.mavlink_component_id
    if not system or not component:
        return
    observed_at = _utc(snapshot.last_heartbeat_at) if snapshot.last_heartbeat_at else at
    if flight is None:
        if not snapshot.armed:
            return
        previous = _latest(session, vehicle_id=vehicle.id)
        if previous and previous.ended_at and observed_at <= _utc(previous.ended_at):
            return
        flight = ObservedFlight(
            vehicle_id=vehicle.id,
            evidence=FlightEvidence(source=snapshot.source).model_dump(mode="json"),
        )
        session.add(flight)
        session.flush()
    state = FlightEvidence.model_validate(flight.evidence)
    if state.last_seen_at and observed_at <= state.last_seen_at:
        return
    if state.source != snapshot.source or (
        state.system_id is not None and (system, component) != (state.system_id, state.component_id)
    ):
        if state.link != "DIVERGENT":
            state.link = "DIVERGENT"
            state.lost = True
            _event(
                session,
                flight,
                "FLIGHT_IDENTITY_CHANGED",
                "O encaminhamento passou a informar outra identidade MAVLink.",
                at,
            )
            flight.evidence = state.model_dump(mode="json")
        return
    state.system_id, state.component_id = system, component
    gap = bool(
        state.lost
        or (
            state.last_seen_at is not None
            and observed_at - state.last_seen_at
            > timedelta(seconds=settings.heartbeat_timeout_seconds)
        )
    )
    if gap:
        if not state.lost:
            _event(session, flight, "FLIGHT_LINK_LOST", "Intervalo de telemetria detectado.", at)
        _event(
            session,
            flight,
            "FLIGHT_LINK_RESTORED",
            "Telemetria retomada com o estado atual recebido.",
            at,
        )
        state.lost = False
        state.had_gap = True
        state.rise_since = state.near_since = None
        if not state.airborne_at:
            state.ground_altitude = None
    previous_armed = state.armed
    state.armed = snapshot.armed
    state.mode = snapshot.flight_mode
    state.last_seen_at = observed_at
    current = payload.px4_flight or Px4FlightObservation()
    if current.mission_at and not at - _MAX_POSITION_GAP <= _utc(
        current.mission_at
    ) <= at + timedelta(seconds=2):
        current = Px4FlightObservation(
            landed_state=current.landed_state, position_at=current.position_at
        )
    state.landed_state = current.landed_state
    state.mission_state = current.mission_state

    if (
        not state.airborne_at
        and current.landed_state in {None, 1}
        and (not snapshot.armed or current.landed_state == 1)
    ):
        state.ground_altitude = snapshot.current_altitude_m
    if previous_armed is None and snapshot.armed and state.ground_altitude is None and not gap:
        state.ground_altitude = session.scalar(
            select(VehicleHealthSnapshot.current_altitude_m)
            .where(
                VehicleHealthSnapshot.vehicle_id == vehicle.id,
                VehicleHealthSnapshot.armed.is_(False),
                VehicleHealthSnapshot.connected.is_(True),
                VehicleHealthSnapshot.mavlink_system_id == system,
                VehicleHealthSnapshot.mavlink_component_id == component,
                VehicleHealthSnapshot.received_at >= at - _MAX_POSITION_GAP,
                VehicleHealthSnapshot.received_at < at,
            )
            .order_by(VehicleHealthSnapshot.received_at.desc())
            .limit(1)
        )
    if snapshot.armed and previous_armed is not True:
        _phase(session, flight, state, "ARMED", at, "Armamento observado no heartbeat.")

    mission = session.get(Mission, flight.mission_id) if flight.mission_id else None
    if mission and (mission.version, mission.mission_sha256) != (
        state.revision,
        state.mission_sha256,
    ):
        if state.link != "DIVERGENT":
            _event(
                session,
                flight,
                "FLIGHT_REVISION_CHANGED",
                "A revisão do pedido mudou durante o acompanhamento.",
                at,
            )
        state.link = "DIVERGENT"
    position_at = _sample_position(state, snapshot, current, mission, at)
    rising = _estimate_airborne(state, snapshot, position_at, current.landed_state)
    mode = (state.mode or "").upper()
    if state.mission_at or (
        snapshot.armed
        and mode in _MISSION_MODES
        and (current.landed_state == 2 or rising or state.airborne_at is not None)
        and current.mission_state not in {1, 2}
    ):
        _apply_plan_evidence(session, vehicle, flight, state, current, at)
        state.sequence = current.sequence
    state.mapping_current = (
        state.link == "VERIFIED"
        and current.native_plan_id is not None
        and current.native_plan_id == state.native_plan_id
    )
    _update_phase(session, flight, state, current, at, rising=rising)
    if (
        state.link in {"OPERATOR", "VERIFIED"}
        and state.phase == "MISSION"
        and state.destination is None
    ):
        if (
            position_at is not None
            and state.distance_m is not None
            and state.distance_m <= _POINT_RADIUS_M
            and state.last_position_at is not None
            and position_at - state.last_position_at <= _MAX_POSITION_GAP
        ):
            state.near_since = state.near_since or position_at
            if position_at - state.near_since >= _POSITION_CONFIRMATION:
                state.destination = "ESTIMATED"
                _event(
                    session,
                    flight,
                    "FLIGHT_DESTINATION_ESTIMATED",
                    "Proximidade do destino observada por posição.",
                    at,
                    estimated=True,
                )
        else:
            state.near_since = None
    else:
        state.near_since = None
    state.last_position_at = position_at

    if not snapshot.armed and previous_armed is True:
        _phase(session, flight, state, "DISARMED", at, "Desarmamento observado no heartbeat.")
    if not snapshot.armed and (
        state.land_at or (previous_armed is True and not state.airborne_at and not state.takeoff_at)
    ):
        flight.ended_at = at
        state.normal_completion = bool(
            state.land_at
            and state.link == "VERIFIED"
            and state.destination == "CONFIRMED"
            and state.mission_finished_reported
            and not state.early_return
        )
        if state.land_at:
            _event(
                session,
                flight,
                "FLIGHT_ENDED",
                "Voo encerrado com conclusão normal verificada."
                if state.normal_completion
                else "Voo encerrado.",
                at,
                normal_completion=state.normal_completion,
            )
    flight.evidence = state.model_dump(mode="json")


def observe_reached(
    session: Session, vehicle: Vehicle, observation: SystemEvent, settings: Settings
) -> None:
    if (
        observation.event_type != "MAVLINK_MISSION_ITEM_REACHED"
        or vehicle.operational_source not in _PX4_OBSERVATION_SOURCES
    ):
        return
    flight = _latest(session, vehicle_id=vehicle.id, active=True)
    if flight is None:
        return
    state = FlightEvidence.model_validate(flight.evidence)
    if state.source != vehicle.operational_source:
        return
    at = _observation_time(observation)
    metadata = observation.event_metadata
    sequence = metadata.get("sequence")
    if (
        state.link not in {"OPERATOR", "VERIFIED"}
        or not state.mission_at
        or state.lost
        or not state.last_seen_at
        or not at
        or at < state.mission_at - timedelta(seconds=1)
        or abs(at - state.last_seen_at) > timedelta(seconds=settings.heartbeat_timeout_seconds)
        or (state.return_at and at > state.return_at and sequence != state.return_sequence)
        or state.land_at is not None
        or type(sequence) is not int
        or sequence < 0
        or (state.mission_total is not None and sequence >= state.mission_total)
        or sequence in state.reached_sequences
        or (metadata.get("system_id"), metadata.get("component_id"))
        != (state.system_id, state.component_id)
    ):
        return
    native_id = metadata.get("native_plan_id")
    if state.native_plan_id is not None and native_id != state.native_plan_id:
        return
    if state.link == "VERIFIED" and sequence >= len(state.expected_items):
        return
    state.reached_sequences = sorted([*state.reached_sequences, sequence])
    _event(
        session,
        flight,
        "FLIGHT_ITEM_REACHED",
        f"PX4 informou item MAVLink {sequence} alcançado.",
        at,
        sequence=sequence,
    )
    if state.link == "VERIFIED" and sequence == state.destination_sequence:
        state.destination = "CONFIRMED"
        state.early_return = False
        _event(
            session,
            flight,
            "FLIGHT_DESTINATION_CONFIRMED",
            "Waypoint de destino confirmado pelo PX4.",
            at,
            sequence=sequence,
        )
    flight.evidence = state.model_dump(mode="json")


def _track(
    session: Session, flight: ObservedFlight, state: FlightEvidence
) -> list[list[FlightPoint]]:
    if not state.airborne_at:
        return []
    newest = flight.ended_at or state.last_seen_at
    samples = session.scalars(
        select(VehicleHealthSnapshot)
        .where(
            VehicleHealthSnapshot.vehicle_id == flight.vehicle_id,
            VehicleHealthSnapshot.source == state.source,
            VehicleHealthSnapshot.received_at >= state.airborne_at,
            VehicleHealthSnapshot.received_at
            <= (newest or state.airborne_at) + timedelta(seconds=2),
            VehicleHealthSnapshot.mavlink_system_id == state.system_id,
            VehicleHealthSnapshot.mavlink_component_id == state.component_id,
        )
        .order_by(VehicleHealthSnapshot.received_at.desc())
        .limit(600)
    ).all()
    segments: list[list[FlightPoint]] = []
    segment: list[FlightPoint] = []
    for sample in reversed(samples):
        received = _utc(sample.received_at)
        if (
            not sample.connected
            or not sample.heartbeat
            or sample.current_latitude is None
            or sample.current_longitude is None
            or (sample.gps_fix_type is not None and sample.gps_fix_type < 3)
        ):
            if segment:
                segments.append(segment)
                segment = []
            continue
        if segment and received - segment[-1].recorded_at > _MAX_POSITION_GAP:
            segments.append(segment)
            segment = []
        segment.append(
            FlightPoint(
                latitude=float(sample.current_latitude),
                longitude=float(sample.current_longitude),
                recorded_at=received,
            )
        )
    if segment:
        segments.append(segment)
    return segments


def read_flight(
    session: Session,
    settings: Settings,
    *,
    vehicle_id: UUID | None = None,
    mission_id: UUID | None = None,
) -> ObservedFlightRead | None:
    flight = _latest(session, vehicle_id=vehicle_id, mission_id=mission_id)
    if flight is None:
        return None
    state = FlightEvidence.model_validate(flight.evidence)
    mission = session.get(Mission, flight.mission_id) if flight.mission_id else None
    vehicle = session.get(Vehicle, flight.vehicle_id)
    if mission and (mission.version, mission.mission_sha256) != (
        state.revision,
        state.mission_sha256,
    ):
        state.link = "DIVERGENT"
    stale = flight.ended_at is None and bool(
        state.lost
        or (
            state.last_seen_at
            and datetime.now(UTC) - state.last_seen_at
            > timedelta(seconds=settings.heartbeat_timeout_seconds)
        )
    )
    events = session.scalars(
        select(SystemEvent)
        .where(
            SystemEvent.vehicle_id == flight.vehicle_id,
            SystemEvent.event_metadata["flight_id"].as_string() == str(flight.id),
        )
        .order_by(SystemEvent.created_at.desc(), SystemEvent.id.desc())
        .limit(80)
    ).all()
    if state.link == "DIVERGENT":
        state.sequence = state.destination_sequence = state.return_sequence = None
        state.mapping_current = False
        state.destination = None
        state.distance_m = None
        state.reached_sequences = []
        state.normal_completion = state.early_return = False
    return ObservedFlightRead(
        id=flight.id,
        vehicle_id=flight.vehicle_id,
        vehicle_name=vehicle.name if vehicle else None,
        mission_id=flight.mission_id,
        ended_at=_utc(flight.ended_at) if flight.ended_at else None,
        stale=stale,
        track=_track(session, flight, state),
        events=[SystemEventRead.model_validate(event) for event in reversed(events)],
        **state.model_dump(
            include=set(ObservedFlightRead.model_fields) & set(FlightEvidence.model_fields)
        ),
    )
