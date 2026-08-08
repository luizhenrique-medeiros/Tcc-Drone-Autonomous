from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_name: str = "drone-delivery"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str | None = None
    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "drone_delivery"
    database_user: str = "drone_user"
    database_password: str = "change_me"
    auto_create_schema: bool = True

    jwt_secret: str = "development-only-change-me"
    jwt_expire_minutes: int = Field(default=60, ge=5, le=1440)
    admin_initial_email: str | None = None
    admin_initial_password: str | None = None
    admin_initial_name: str = "Administrador"

    gateway_api_key: str = "development-gateway-key"
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:8081,http://127.0.0.1:8081"
    )

    map_provider: Literal["maptiler"] = "maptiler"
    maptiler_server_api_key: str | None = None
    maps_search_country: str | None = None
    maps_default_latitude: float = Field(default=-23.1175, ge=-90, le=90)
    maps_default_longitude: float = Field(default=-46.5502, ge=-180, le=180)

    default_takeoff_altitude_m: float = Field(default=10, gt=0, le=120)
    max_mission_distance_m: float = Field(default=500, gt=0, le=10000)
    delivery_fee: float = Field(default=7.5, ge=0)
    min_battery_percent: float = Field(default=40, ge=0, le=100)
    min_gps_satellites: int = Field(default=10, ge=0, le=100)
    heartbeat_timeout_seconds: int = Field(default=10, ge=1, le=300)
    flight_authorization_ttl_seconds: int = Field(default=300, ge=30, le=1800)
    telemetry_persist_interval_seconds: int = Field(default=2, ge=1, le=60)

    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"development", "test", "demo", "production"}:
            raise ValueError("APP_ENV deve ser development, test, demo ou production")
        return normalized

    @field_validator("maps_search_country", mode="before")
    @classmethod
    def normalize_optional_country(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        if normalized and (len(normalized) != 2 or not normalized.isalpha()):
            raise ValueError("MAPS_SEARCH_COUNTRY deve ser um código ISO de duas letras")
        return normalized or None

    @field_validator("maptiler_server_api_key", mode="before")
    @classmethod
    def normalize_optional_maptiler_key(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if "://" in normalized or "key=" in normalized.lower():
            raise ValueError(
                "MAPTILER_SERVER_API_KEY deve conter somente a chave, não a URL completa"
            )
        return normalized

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> Settings:
        if self.app_env in {"demo", "production"}:
            if self.jwt_secret == "development-only-change-me":
                raise ValueError("JWT_SECRET deve ser configurado em demo/production")
            if self.gateway_api_key == "development-gateway-key":
                raise ValueError("GATEWAY_API_KEY deve ser configurada em demo/production")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
