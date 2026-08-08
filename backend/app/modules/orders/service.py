from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.enums import AdminDecisionType, EventSeverity, OrderStatus, UserRole
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError
from app.modules.approvals.models import AdminDecision
from app.modules.delivery_points.models import DeliveryPoint
from app.modules.delivery_points.schemas import DeliveryPointRead
from app.modules.missions.models import Mission
from app.modules.orders.admin_schemas import (
    AdminCustomerSummary,
    AdminDecisionRead,
    AdminDeliveryPointRead,
    AdminOrderItemRead,
    AdminOrderRead,
)
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import (
    OrderCreate,
    OrderDetailRead,
    OrderGroup,
    OrderItemRead,
    OrderMilestoneRead,
    OrderMilestoneType,
    OrderRead,
)
from app.modules.products.models import Product
from app.modules.system_events.models import SystemEvent
from app.modules.system_events.service import record_event
from app.modules.users.models import User

TERMINAL_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
    }
)

CUSTOMER_ORDER_MILESTONE_TYPES: tuple[OrderMilestoneType, ...] = tuple(OrderMilestoneType)
CUSTOMER_ORDER_MILESTONE_EVENT_TYPES: tuple[str, ...] = tuple(
    milestone_type.value for milestone_type in CUSTOMER_ORDER_MILESTONE_TYPES
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_order(
    session: Session,
    customer: User,
    payload: OrderCreate,
    delivery_fee: Decimal,
    *,
    commit: bool = True,
) -> Order:
    point = session.get(DeliveryPoint, payload.delivery_point_id)
    if not point or point.user_id != customer.id:
        raise NotFoundError("Ponto de entrega não encontrado")
    if not (
        point.region_confirmed
        and point.exact_point_selected
        and point.user_confirmed
        and point.user_confirmed_safe_area
    ):
        raise ConflictError("O ponto de entrega não possui confirmação final válida")
    product_ids = [item.product_id for item in payload.items]
    if len(product_ids) != len(set(product_ids)):
        raise ConflictError("Não repita o mesmo produto; ajuste a quantidade")
    products = {
        product.id: product
        for product in session.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    }
    if len(products) != len(product_ids):
        raise NotFoundError("Um ou mais produtos não foram encontrados")

    items: list[OrderItem] = []
    subtotal = Decimal("0")
    for requested in payload.items:
        product = products[requested.product_id]
        if not product.available:
            raise ConflictError(f"O produto {product.name} não está disponível")
        line_total = _money(product.price * requested.quantity)
        subtotal += line_total
        items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=requested.quantity,
                line_total=line_total,
            )
        )
    subtotal = _money(subtotal)
    # Promoção acadêmica reproduzível; não representa cobrança real.
    discount = _money(subtotal * Decimal("0.20"))
    total = _money(subtotal + delivery_fee - discount)
    order = Order(
        customer_id=customer.id,
        delivery_point_id=point.id,
        status=OrderStatus.DRAFT,
        payment_method=payload.payment_method,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        discount=discount,
        total=total,
        items=items,
    )
    session.add(order)
    session.flush()
    record_event(
        session,
        actor_type="CUSTOMER",
        actor_user_id=customer.id,
        order_id=order.id,
        event_type="ORDER_CREATED",
        message="Pedido de demonstração criado como rascunho",
    )
    session.flush()
    if commit:
        session.commit()
        session.refresh(order)
    return order


def get_order_for_user(session: Session, order_id: UUID, user: User) -> Order:
    order = session.get(Order, order_id)
    if not order or (user.role == UserRole.CUSTOMER and order.customer_id != user.id):
        raise NotFoundError("Pedido não encontrado")
    return order


def list_orders_for_customer(
    session: Session,
    customer: User,
    group: OrderGroup,
    limit: int,
    offset: int,
) -> list[Order]:
    query = select(Order).where(
        Order.customer_id == customer.id,
        Order.status != OrderStatus.DRAFT,
    )
    if group is OrderGroup.ACTIVE:
        query = query.where(~Order.status.in_(TERMINAL_ORDER_STATUSES))
    elif group is OrderGroup.HISTORY:
        query = query.where(Order.status.in_(TERMINAL_ORDER_STATUSES))

    active_priority = case(
        (Order.status.in_(TERMINAL_ORDER_STATUSES), 1),
        else_=0,
    )
    return list(
        session.scalars(
            query.order_by(
                active_priority.asc(),
                Order.created_at.desc(),
                Order.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )


def submit_order(session: Session, order: Order, customer: User, *, commit: bool = True) -> Order:
    if order.customer_id != customer.id:
        raise NotFoundError("Pedido não encontrado")
    if order.status != OrderStatus.DRAFT:
        raise InvalidStateError("Somente pedidos em rascunho podem ser enviados")
    if not order.items:
        raise InvalidStateError("O pedido precisa conter ao menos um item")
    order.status = OrderStatus.PENDING_ADMIN_APPROVAL
    order.submitted_at = datetime.now(UTC)
    record_event(
        session,
        actor_type="CUSTOMER",
        actor_user_id=customer.id,
        order_id=order.id,
        event_type="ORDER_SUBMITTED",
        message="Pedido enviado para aprovação administrativa",
    )
    session.flush()
    if commit:
        session.commit()
        session.refresh(order)
    return order


def cancel_order(session: Session, order: Order, customer: User) -> Order:
    if order.customer_id != customer.id:
        raise NotFoundError("Pedido não encontrado")
    if order.status not in {OrderStatus.DRAFT, OrderStatus.PENDING_ADMIN_APPROVAL}:
        raise InvalidStateError("Este pedido não pode mais ser cancelado pelo cliente")
    order.status = OrderStatus.CANCELLED
    record_event(
        session,
        actor_type="CUSTOMER",
        actor_user_id=customer.id,
        order_id=order.id,
        event_type="ORDER_CANCELLED",
        message="Pedido cancelado pelo cliente",
        severity=EventSeverity.WARNING,
    )
    session.commit()
    session.refresh(order)
    return order


def approve_order(session: Session, order: Order, admin: User, reason: str | None) -> Order:
    if order.status != OrderStatus.PENDING_ADMIN_APPROVAL:
        raise InvalidStateError("Somente pedidos pendentes podem ser aprovados")
    order.status = OrderStatus.APPROVED
    session.add(
        AdminDecision(
            order_id=order.id,
            administrator_id=admin.id,
            decision=AdminDecisionType.APPROVED,
            reason=reason,
        )
    )
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=order.id,
        event_type="ORDER_APPROVED",
        message="Pedido aprovado; o voo ainda não está autorizado",
        metadata={"reason": reason},
    )
    session.commit()
    session.refresh(order)
    return order


def reject_order(session: Session, order: Order, admin: User, reason: str) -> Order:
    if order.status != OrderStatus.PENDING_ADMIN_APPROVAL:
        raise InvalidStateError("Somente pedidos pendentes podem ser rejeitados")
    clean_reason = reason.strip()
    if len(clean_reason) < 3:
        raise ConflictError("Informe o motivo da rejeição")
    order.status = OrderStatus.REJECTED
    order.rejection_reason = clean_reason
    session.add(
        AdminDecision(
            order_id=order.id,
            administrator_id=admin.id,
            decision=AdminDecisionType.REJECTED,
            reason=clean_reason,
        )
    )
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=order.id,
        event_type="ORDER_REJECTED",
        message="Pedido rejeitado pela análise administrativa",
        severity=EventSeverity.WARNING,
        metadata={"reason": clean_reason},
    )
    session.commit()
    session.refresh(order)
    return order


def orders_to_read(session: Session, orders: list[Order]) -> list[OrderRead]:
    if not orders:
        return []
    points = {
        point.id: point
        for point in session.scalars(
            select(DeliveryPoint).where(
                DeliveryPoint.id.in_({order.delivery_point_id for order in orders})
            )
        ).all()
    }
    products = {
        product.id: product
        for product in session.scalars(
            select(Product).where(
                Product.id.in_({item.product_id for order in orders for item in order.items})
            )
        ).all()
    }
    results: list[OrderRead] = []
    for order in orders:
        result = OrderRead.model_validate(order)
        result.items = [
            OrderItemRead.model_validate(item).model_copy(
                update={
                    "category": products[item.product_id].category,
                    "image_url": products[item.product_id].image_url,
                }
            )
            if item.product_id in products
            else OrderItemRead.model_validate(item)
            for item in order.items
        ]
        point = points.get(order.delivery_point_id)
        if point:
            result.delivery_point = DeliveryPointRead.model_validate(point)
        results.append(result)
    return results


def order_to_read(session: Session, order: Order) -> OrderRead:
    return orders_to_read(session, [order])[0]


def order_detail_to_read(session: Session, order: Order) -> OrderDetailRead:
    result = order_to_read(session, order)
    events = session.scalars(
        select(SystemEvent)
        .where(
            SystemEvent.order_id == order.id,
            SystemEvent.event_type.in_(CUSTOMER_ORDER_MILESTONE_EVENT_TYPES),
        )
        .order_by(SystemEvent.created_at.asc(), SystemEvent.id.asc())
    ).all()
    seen_event_types: set[str] = set()
    milestones: list[OrderMilestoneRead] = []
    for event in events:
        if event.event_type in seen_event_types:
            continue
        seen_event_types.add(event.event_type)
        milestones.append(
            OrderMilestoneRead(
                event_type=OrderMilestoneType(event.event_type),
                occurred_at=event.created_at,
            )
        )
    return OrderDetailRead(**result.model_dump(), milestones=milestones)


def admin_order_to_read(session: Session, order: Order) -> AdminOrderRead:
    customer = session.get(User, order.customer_id)
    point = session.get(DeliveryPoint, order.delivery_point_id)
    if not customer or not point:
        raise NotFoundError("Dados relacionados do pedido não foram encontrados")
    decision = session.scalar(
        select(AdminDecision)
        .where(AdminDecision.order_id == order.id)
        .order_by(AdminDecision.created_at.desc())
        .limit(1)
    )
    decision_read = None
    if decision:
        decision_admin = session.get(User, decision.administrator_id)
        decision_read = AdminDecisionRead(
            decision=decision.decision,
            reason=decision.reason,
            admin_name=decision_admin.name if decision_admin else "Administrador",
            created_at=decision.created_at,
        )
    mission = session.scalar(select(Mission).where(Mission.order_id == order.id))
    return AdminOrderRead(
        id=order.id,
        status=order.status,
        customer=AdminCustomerSummary(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
        ),
        items=[
            AdminOrderItemRead(
                id=item.id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.line_total,
            )
            for item in order.items
        ],
        delivery_point=AdminDeliveryPointRead(
            latitude=float(point.final_latitude),
            longitude=float(point.final_longitude),
            label=point.label,
            searched_address=point.searched_address,
            reference_address=point.address_reference,
            approximate_latitude=(
                float(point.approximate_latitude)
                if point.approximate_latitude is not None
                else None
            ),
            approximate_longitude=(
                float(point.approximate_longitude)
                if point.approximate_longitude is not None
                else None
            ),
            instructions=point.instructions,
            selection_source=point.selection_source.value,
            map_type=point.map_type,
            customer_confirmed=point.user_confirmed,
            controlled_area_confirmed=point.user_confirmed_safe_area,
        ),
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        discount=order.discount,
        total=order.total,
        simulated_payment_method=order.payment_method.value,
        rejection_reason=order.rejection_reason,
        created_at=order.created_at,
        updated_at=order.updated_at,
        estimated_distance_m=float(point.distance_from_base_m),
        mission_id=mission.id if mission else None,
        admin_decision=decision_read,
    )
