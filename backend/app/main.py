from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, DomainError
from app.database.session import (
    SessionLocal,
    database_is_ready,
    initialize_database,
)
from app.modules.auth.service import seed_initial_admin
from app.modules.products.service import seed_demo_products


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    with SessionLocal() as session:
        seed_demo_products(session)
        seed_initial_admin(session, get_settings())
    yield


settings = get_settings()
app = FastAPI(
    title="Drone Delivery API",
    version="0.1.0",
    description=(
        "API do protótipo acadêmico. Produtos e pagamento são simulados; "
        "aprovação, missão, autorização e telemetria possuem contratos reais."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Gateway-API-Key",
        "X-Request-ID",
    ],
    expose_headers=["Idempotency-Replayed", "X-Mission-SHA256", "Content-Disposition"],
)
app.include_router(api_router)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.detail, "fields": exc.fields},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"] if part != "body")
        fields[location or "request"] = error["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "detail": "A requisição contém dados inválidos",
            "fields": fields,
        },
    )


@app.get("/health", tags=["Operação"], summary="Verificar processo")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready", tags=["Operação"], summary="Verificar banco")
def ready() -> JSONResponse:
    is_ready = database_is_ready()
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready", "database": is_ready},
    )
