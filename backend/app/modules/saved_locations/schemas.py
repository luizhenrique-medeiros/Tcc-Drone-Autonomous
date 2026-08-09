from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LOCATION_EVIDENCE_FIELDS = frozenset(
    {
        "final_latitude",
        "final_longitude",
        "map_provider",
        "map_type",
        "region_confirmed",
        "exact_point_selected",
        "user_confirmed",
        "user_confirmed_safe_area",
    }
)


def _normalize_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Informe o nome da localização")
    if len(normalized) > 40:
        raise ValueError("O nome da localização deve ter no máximo 40 caracteres")
    return normalized


def _normalize_map_provider(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Informe o provedor do mapa")
    return normalized


def _normalize_map_type(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Informe o tipo do mapa")
    return normalized


class SavedLocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    final_latitude: float = Field(ge=-90, le=90)
    final_longitude: float = Field(ge=-180, le=180)
    address_reference: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, max_length=1000)
    accuracy_meters: float | None = Field(default=None, ge=0, le=1000)
    map_provider: str = Field(min_length=1, max_length=40)
    map_type: str = Field(min_length=1, max_length=30)
    region_confirmed: bool
    exact_point_selected: bool
    user_confirmed: bool
    user_confirmed_safe_area: bool

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_name(value)

    @field_validator("map_provider")
    @classmethod
    def normalize_map_provider(cls, value: str) -> str:
        return _normalize_map_provider(value)

    @field_validator("map_type")
    @classmethod
    def normalize_map_type(cls, value: str) -> str:
        return _normalize_map_type(value)


class SavedLocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    final_latitude: float | None = Field(default=None, ge=-90, le=90)
    final_longitude: float | None = Field(default=None, ge=-180, le=180)
    address_reference: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, max_length=1000)
    accuracy_meters: float | None = Field(default=None, ge=0, le=1000)
    map_provider: str | None = Field(default=None, min_length=1, max_length=40)
    map_type: str | None = Field(default=None, min_length=1, max_length=30)
    region_confirmed: bool | None = None
    exact_point_selected: bool | None = None
    user_confirmed: bool | None = None
    user_confirmed_safe_area: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("O nome da localização não pode ser nulo")
        return _normalize_name(value)

    @field_validator("map_provider")
    @classmethod
    def normalize_map_provider(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("O provedor do mapa não pode ser nulo")
        return _normalize_map_provider(value)

    @field_validator("map_type")
    @classmethod
    def normalize_map_type(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("O tipo do mapa não pode ser nulo")
        return _normalize_map_type(value)

    @model_validator(mode="after")
    def validate_update(self) -> SavedLocationUpdate:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        latitude_sent = "final_latitude" in self.model_fields_set
        longitude_sent = "final_longitude" in self.model_fields_set
        if latitude_sent != longitude_sent:
            raise ValueError("As coordenadas finais devem ser informadas em conjunto")
        if latitude_sent and (self.final_latitude is None or self.final_longitude is None):
            raise ValueError("As coordenadas finais não podem ser nulas")
        return self


class SavedLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    final_latitude: Decimal
    final_longitude: Decimal
    address_reference: str | None
    instructions: str | None
    accuracy_meters: Decimal | None
    map_provider: str
    map_type: str
    region_confirmed: bool
    exact_point_selected: bool
    user_confirmed: bool
    user_confirmed_safe_area: bool
    created_at: datetime
    updated_at: datetime
