from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import SelectionSource


class DeliveryPointInput(BaseModel):
    searched_address: str | None = Field(default=None, max_length=500)
    address_reference: str | None = Field(default=None, max_length=500)
    selection_source: SelectionSource
    approximate_latitude: float | None = Field(default=None, ge=-90, le=90)
    approximate_longitude: float | None = Field(default=None, ge=-180, le=180)
    final_latitude: float = Field(ge=-90, le=90)
    final_longitude: float = Field(ge=-180, le=180)
    label: str | None = Field(default=None, max_length=120)
    instructions: str | None = Field(default=None, max_length=1000)
    map_provider: str = Field(default="maptiler", max_length=40)
    map_type: str = Field(default="hybrid", max_length=30)
    accuracy_meters: float | None = Field(default=None, ge=0, le=1000)
    region_confirmed: bool
    exact_point_selected: bool
    user_confirmed: bool
    user_confirmed_safe_area: bool

    @model_validator(mode="after")
    def validate_approximate_pair(self) -> DeliveryPointInput:
        if (self.approximate_latitude is None) != (self.approximate_longitude is None):
            raise ValueError("As coordenadas aproximadas devem ser informadas em conjunto")
        return self


class DeliveryPointValidation(BaseModel):
    valid: bool
    within_coverage: bool
    final_latitude: float
    final_longitude: float
    distance_from_approximate_m: Decimal | None
    distance_from_base_m: Decimal
    max_distance_m: Decimal | None
    map_type: str


class DeliveryPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    searched_address: str | None
    address_reference: str | None
    selection_source: SelectionSource
    approximate_latitude: Decimal | None
    approximate_longitude: Decimal | None
    final_latitude: Decimal
    final_longitude: Decimal
    label: str | None
    instructions: str | None
    map_provider: str
    map_type: str
    accuracy_meters: Decimal | None
    region_confirmed: bool
    exact_point_selected: bool
    user_confirmed: bool
    user_confirmed_safe_area: bool
    distance_from_approximate_m: Decimal | None
    distance_from_base_m: Decimal
    created_at: datetime
    updated_at: datetime
