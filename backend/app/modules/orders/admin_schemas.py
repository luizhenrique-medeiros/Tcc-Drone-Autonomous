from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import AdminDecisionType, OrderStatus


class ApproveOrderRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class RejectOrderRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class AdminCustomerSummary(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str | None = None


class AdminDeliveryPointRead(BaseModel):
    latitude: float
    longitude: float
    label: str | None
    searched_address: str | None
    reference_address: str | None
    approximate_latitude: float | None
    approximate_longitude: float | None
    instructions: str | None
    selection_source: str
    map_type: str
    customer_confirmed: bool
    controlled_area_confirmed: bool


class AdminOrderItemRead(BaseModel):
    id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class AdminDecisionRead(BaseModel):
    decision: AdminDecisionType
    reason: str | None
    admin_name: str
    created_at: datetime


class AdminOrderRead(BaseModel):
    id: UUID
    status: OrderStatus
    customer: AdminCustomerSummary
    items: list[AdminOrderItemRead]
    delivery_point: AdminDeliveryPointRead
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total: Decimal
    simulated_payment_method: str
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    estimated_distance_m: float
    mission_id: UUID | None
    admin_decision: AdminDecisionRead | None
