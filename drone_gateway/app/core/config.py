from enum import StrEnum
from pathlib import Path
from tempfile import gettempdir

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigurationError


class MavlinkMode(StrEnum):
    SIMULATION = "simulation"
    SITL = "sitl"
    REAL = "real"
    DIRECT = "direct"
    MISSION_PLANNER_FORWARD = "mission_planner_forward"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    api_base_url: str = "http://localhost:8000"
    gateway_api_key: SecretStr = SecretStr("change_me_gateway_key")
    gateway_id: str = "dev-gateway-01"
    vehicle_identifier: str = "academic-vehicle-01"
    vehicle_name: str = "Drone acadêmico"
    autopilot_system: str = "ARDUPILOT"

    mavlink_mode: MavlinkMode = MavlinkMode.SIMULATION
    mavlink_connection: str = "udp:127.0.0.1:14550"
    mavlink_forward_connection: str = "udpin:127.0.0.1:14551"
    mavlink_baud_rate: int = Field(
        default=57600,
        ge=1200,
        le=4_000_000,
        validation_alias=AliasChoices("MAVLINK_BAUD", "MAVLINK_BAUD_RATE"),
    )
    mavlink_source_system_id: int = Field(default=254, ge=1, le=255)
    mavlink_source_component_id: int = Field(default=190, ge=1, le=255)
    mavlink_target_system_id: int | None = Field(default=None, ge=1, le=255)
    mavlink_target_component_id: int | None = Field(default=None, ge=0, le=255)
    mavlink_dialect: str = "ardupilotmega"
    mavlink2_enabled: bool = True
    real_hardware_confirmation_required: bool = True
    real_hardware_acknowledged: bool = False
    allow_mission_upload: bool = False
    allow_flight_commands: bool = False
    allow_mission_start: bool = False

    base_latitude: float = Field(default=-23.1175, ge=-90, le=90)
    base_longitude: float = Field(default=-46.5502, ge=-180, le=180)
    default_takeoff_altitude_m: float = Field(default=10, gt=0, le=120)
    max_mission_distance_m: float = Field(default=500, gt=0)
    min_battery_percent: float = Field(default=40, ge=0, le=100)
    min_gps_satellites: int = Field(default=10, ge=0, le=100)
    heartbeat_timeout_seconds: float = Field(default=10, gt=0, le=120)
    mission_command_timeout_seconds: float = Field(default=15, gt=0, le=120)
    telemetry_persist_interval_seconds: float = Field(default=2, gt=0, le=60)
    gateway_poll_interval_seconds: float = Field(default=2, gt=0, le=60)
    gateway_command_max_age_seconds: float = Field(default=60, gt=0, le=3600)
    mavlink_reconnect_initial_seconds: float = Field(default=1, gt=0, le=60)
    mavlink_reconnect_max_seconds: float = Field(default=10, gt=0, le=300)
    mavlink_telemetry_stale_seconds: float = Field(
        default=5,
        gt=0,
        le=120,
        validation_alias=AliasChoices("MAVLINK_TELEMETRY_STALE", "MAVLINK_TELEMETRY_STALE_SECONDS"),
    )
    mavlink_message_interval_timeout_seconds: float = Field(default=1.5, gt=0, le=10)
    gcs_heartbeat_interval_seconds: float = Field(default=1, gt=0, le=10)
    backend_timeout_seconds: float = Field(default=10, gt=0, le=120)
    max_origin_deviation_m: float = Field(default=30, gt=0, le=500)
    required_start_flight_mode: str = "AUTO"
    mission_protocol_retries: int = Field(default=3, ge=1, le=10)
    mission_protocol_step_timeout_seconds: float = Field(default=1.5, gt=0, le=15)
    gateway_journal_path: Path = Path(gettempdir()) / "devcore-drone-gateway-journal.json"
    log_level: str = "INFO"

    @property
    def is_hardware_mode(self) -> bool:
        return self.mavlink_mode in {
            MavlinkMode.REAL,
            MavlinkMode.DIRECT,
            MavlinkMode.MISSION_PLANNER_FORWARD,
        }

    @property
    def connection_topology(self) -> str:
        if self.mavlink_mode is MavlinkMode.DIRECT:
            return MavlinkMode.DIRECT.value
        if self.mavlink_mode is MavlinkMode.MISSION_PLANNER_FORWARD:
            return MavlinkMode.MISSION_PLANNER_FORWARD.value
        if self.mavlink_mode is MavlinkMode.SITL:
            return MavlinkMode.SITL.value
        if self.mavlink_mode is MavlinkMode.SIMULATION:
            return MavlinkMode.SIMULATION.value
        return (
            MavlinkMode.MISSION_PLANNER_FORWARD.value
            if self.mavlink_connection.lower().startswith(("udp:", "udpin:"))
            else MavlinkMode.DIRECT.value
        )

    @property
    def effective_mavlink_connection(self) -> str:
        if self.mavlink_mode is MavlinkMode.MISSION_PLANNER_FORWARD:
            return self.mavlink_forward_connection
        return self.mavlink_connection

    @property
    def sanitized_connection(self) -> str:
        connection = self.effective_mavlink_connection.strip()
        if "?" in connection:
            connection = connection.split("?", maxsplit=1)[0]
        if "@" in connection:
            prefix, endpoint = connection.rsplit("@", maxsplit=1)
            scheme = prefix.split(":", maxsplit=1)[0]
            connection = f"{scheme}:{endpoint}"
        return connection

    @field_validator("mavlink_target_system_id", "mavlink_target_component_id", mode="before")
    @classmethod
    def blank_target_id_is_auto(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL inválido")
        return normalized

    @model_validator(mode="after")
    def validate_mavlink_safety(self) -> "Settings":
        if self.mavlink_reconnect_initial_seconds > self.mavlink_reconnect_max_seconds:
            raise ConfigurationError(
                "MAVLINK_RECONNECT_INITIAL_SECONDS não pode exceder MAVLINK_RECONNECT_MAX_SECONDS."
            )
        if self.allow_mission_start and not self.allow_flight_commands:
            raise ConfigurationError("ALLOW_MISSION_START=true exige ALLOW_FLIGHT_COMMANDS=true.")
        connection = self.effective_mavlink_connection.lower().strip()
        network_prefixes = ("udp:", "udpin:", "udpout:", "tcp:", "tcpin:")
        if self.mavlink_mode is MavlinkMode.DIRECT and connection.startswith(network_prefixes):
            raise ConfigurationError("MAVLINK_MODE=direct exige uma porta serial.")
        if self.mavlink_mode is MavlinkMode.MISSION_PLANNER_FORWARD and not connection.startswith(
            "udpin:"
        ):
            raise ConfigurationError(
                "MAVLINK_MODE=mission_planner_forward exige uma conexão udpin."
            )
        if (
            self.mavlink_mode is MavlinkMode.MISSION_PLANNER_FORWARD
            and self.mavlink_connection.lower().strip().startswith(network_prefixes)
        ):
            raise ConfigurationError(
                "MAVLINK_MODE=mission_planner_forward exige MAVLINK_CONNECTION com a porta "
                "serial upstream que pertence ao Mission Planner."
            )
        dangerous_operation_enabled = (
            self.allow_mission_upload or self.allow_flight_commands or self.allow_mission_start
        )
        if self.is_hardware_mode and dangerous_operation_enabled:
            if self.real_hardware_confirmation_required and not self.real_hardware_acknowledged:
                raise ConfigurationError(
                    "Upload/comandos em hardware exigem REAL_HARDWARE_ACKNOWLEDGED=true."
                )
            if self.gateway_api_key.get_secret_value().startswith("change_me"):
                raise ConfigurationError(
                    "Troque GATEWAY_API_KEY antes de habilitar upload/comandos em hardware."
                )
        return self
