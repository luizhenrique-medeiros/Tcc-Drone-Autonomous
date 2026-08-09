from fastapi import APIRouter

from app.api.v1.routers import (
    admin,
    auth,
    delivery_points,
    gateway,
    maps,
    orders,
    products,
    saved_locations,
    websockets,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(maps.router)
api_router.include_router(delivery_points.router)
api_router.include_router(saved_locations.router)
api_router.include_router(orders.router)
api_router.include_router(admin.router)
api_router.include_router(gateway.router)
api_router.include_router(websockets.router)
