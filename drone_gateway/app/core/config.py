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
    mavlink_baud_rate: int = Field(
        default=57600,
        ge=1200,
        le=4_000_000,
        validation_alias=AliasChoices("MAVLINK_BAUD", "MAVLINK_BAUD_RATE"),
    )
    mavlink_source_system_id: int = Field(default=254, ge=1, le=255)
    mavlink_target_system_id: int | None = Field(default=None, ge=1, le=255)
    mavlink_target_component_id: int | None = Field(default=None, ge=0, le=255)
    real_hardware_confirmation_required: bool = True
    real_hardware_acknowledged: bool = False
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
    backend_timeout_seconds: float = Field(default=10, gt=0, le=120)
    max_origin_deviation_m: float = Field(default=30, gt=0, le=500)
    required_start_flight_mode: str = "AUTO"
    mission_protocol_retries: int = Field(default=3, ge=1, le=10)
    gateway_journal_path: Path = Path(gettempdir()) / "devcore-drone-gateway-journal.json"

    @field_validator("mavlink_target_system_id", "mavlink_target_component_id", mode="before")
    @classmethod
    def blank_target_id_is_auto(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_real_mode(self) -> "Settings":
        if self.mavlink_mode is MavlinkMode.REAL:
            if self.real_hardware_confirmation_required and not self.real_hardware_acknowledged:
                raise ConfigurationError("MAVLINK_MODE=real exige REAL_HARDWARE_ACKNOWLEDGED=true.")
            if not self.allow_mission_start:
                raise ConfigurationError(
                    "Modo real exige ALLOW_MISSION_START=true como ação operacional explícita."
                )
            if self.gateway_api_key.get_secret_value().startswith("change_me"):
                raise ConfigurationError("Troque GATEWAY_API_KEY antes do modo real.")
        return self
