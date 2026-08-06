from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.products.models import Product

DEMO_PRODUCTS = (
    {
        "name": "Pizza de Pepperoni Especial",
        "description": "Pizza de demonstração com pepperoni e queijo.",
        "category": "Pizza",
        "image_url": "/static/products/pizza-pepperoni.png",
        "price": Decimal("49.90"),
    },
    {
        "name": "Kit de Grocerias",
        "description": "Seleção acadêmica de itens de mercearia para entrega.",
        "category": "Grocerias",
        "image_url": "/static/products/groceries.png",
        "price": Decimal("39.90"),
    },
    {
        "name": "Combo Burger",
        "description": "Hambúrguer, batatas e bebida em catálogo simulado.",
        "category": "Burger",
        "image_url": "/static/products/burger.png",
        "price": Decimal("34.90"),
    },
    {
        "name": "Combo Sushi",
        "description": "Combinado de sushi para fins de demonstração.",
        "category": "Sushi",
        "image_url": "/static/products/sushi.png",
        "price": Decimal("54.90"),
    },
)


def seed_demo_products(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Product)):
        return
    session.add_all(Product(**product) for product in DEMO_PRODUCTS)
    session.commit()
