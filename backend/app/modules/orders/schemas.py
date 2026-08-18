from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import OrderStatus, PaymentMethod
from app.modules.delivery_points.schemas import DeliveryPointRead


class OrderGroup(StrEnum):
    ALL = "all"
    ACTIVE = "active"
    HISTORY = "history"


class OrderMilestoneType(StrEnum):
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_APPROVED = "ORDER_APPROVED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    MISSION_GENERATED = "MISSION_GENERATED"
    FLIGHT_AUTHORIZED = "FLIGHT_AUTHORIZED"
    MISSION_CLAIMED = "MISSION_CLAIMED"
    MISSION_UPLOADING = "MISSION_UPLOADING"
    MISSION_UPLOADED = "MISSION_UPLOADED"
    MISSION_VERIFIED = "MISSION_VERIFIED"
    MISSION_EXECUTING = "MISSION_EXECUTING"
    MISSION_DESTINATION_REACHED = "MISSION_DESTINATION_REACHED"
    MISSION_DELIVERY_CONFIRMED = "MISSION_DELIVERY_CONFIRMED"
    MISSION_RETURNING = "MISSION_RETURNING"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_ABORTED = "MISSION_ABORTED"
    MISSION_FAILED = "MISSION_FAILED"


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=20)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_point_id: UUID | None = None
    saved_location_id: UUID | None = None
    saved_location_review_confirmed: bool | None = None
    saved_location_safe_area_confirmed: bool | None = None
    payment_method: PaymentMethod
    items: list[OrderItemCreate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_delivery_source(self) -> OrderCreate:
        sources = (self.delivery_point_id is not None, self.saved_location_id is not None)
        if sum(sources) != 1:
            raise ValueError("Informe exatamente um entre delivery_point_id e saved_location_id")
        review_fields = {
            "saved_location_review_confirmed",
            "saved_location_safe_area_confirmed",
        }
        if self.delivery_point_id is not None:
            if review_fields.intersection(self.model_fields_set):
                raise ValueError("Confirmações de localização salva não se aplicam ao ponto manual")
            return self
        if not (
            self.saved_location_review_confirmed is True
            and self.saved_location_safe_area_confirmed is True
        ):
            raise ValueError("Revise a localização salva e confirme a segurança da área")
        return self


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    category: str | None = None
    image_url: str | None = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    delivery_point_id: UUID
    status: OrderStatus
    payment_method: PaymentMethod
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total: Decimal
    rejection_reason: str | None
    submitted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]
    delivery_point: DeliveryPointRead | None = None


class OrderMilestoneRead(BaseModel):
    event_type: OrderMilestoneType
    occurred_at: datetime


class OrderDetailRead(OrderRead):
    milestones: list[OrderMilestoneRead]
