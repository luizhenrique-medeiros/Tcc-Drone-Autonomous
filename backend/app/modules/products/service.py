from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.products.models import Product

DEMO_PRODUCTS = (
    {
        "name": "Pizza de Pepperoni Especial",
        "description": "Pizza de demonstração com pepperoni e queijo.",
        "category": "Pizza",
        "image_url": None,
        "price": Decimal("49.90"),
    },
    {
        "name": "Kit de Grocerias",
        "description": "Seleção acadêmica de itens de mercearia para entrega.",
        "category": "Grocerias",
        "image_url": None,
        "price": Decimal("39.90"),
    },
    {
        "name": "Combo Burger",
        "description": "Hambúrguer, batatas e bebida em catálogo simulado.",
        "category": "Burger",
        "image_url": None,
        "price": Decimal("34.90"),
    },
    {
        "name": "Combo Sushi",
        "description": "Combinado de sushi para fins de demonstração.",
        "category": "Sushi",
        "image_url": None,
        "price": Decimal("54.90"),
    },
)


def seed_demo_products(session: Session) -> None:
    changed = False
    for product_data in DEMO_PRODUCTS:
        product = session.scalar(select(Product).where(Product.name == product_data["name"]))
        if product is None:
            session.add(Product(**product_data))
            changed = True
        elif product.image_url and product.image_url.startswith("/static/products/"):
            product.image_url = None
            changed = True
    if changed:
        session.commit()
