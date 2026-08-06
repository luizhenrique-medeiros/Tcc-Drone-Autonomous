from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.exceptions import NotFoundError
from app.modules.products.models import Product
from app.modules.products.schemas import ProductRead

router = APIRouter(prefix="/products", tags=["Produtos"])


@router.get("", response_model=list[ProductRead], summary="Listar produtos de demonstração")
def list_products(
    session: DatabaseSession,
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Product]:
    return list(
        session.scalars(
            select(Product)
            .where(Product.available.is_(True))
            .order_by(Product.category, Product.name)
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/{product_id}", response_model=ProductRead, summary="Detalhar produto")
def get_product(product_id: UUID, session: DatabaseSession, _user: CurrentUser) -> Product:
    product = session.get(Product, product_id)
    if not product:
        raise NotFoundError("Produto não encontrado")
    return product
