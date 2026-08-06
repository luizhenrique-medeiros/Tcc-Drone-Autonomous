from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import OrderStatus, PaymentMethod
from app.modules.delivery_points.schemas import DeliveryPointRead


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=20)


class OrderCreate(BaseModel):
    delivery_point_id: UUID
    payment_method: PaymentMethod
    items: list[OrderItemCreate] = Field(min_length=1, max_length=20)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


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
