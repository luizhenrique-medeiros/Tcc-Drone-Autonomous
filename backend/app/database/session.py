from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database.base import Base


def _build_engine() -> Engine:
    url = get_settings().sqlalchemy_database_url
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def import_models() -> None:
    # Imports register every modular mapping in Base.metadata.
    from app.modules.approvals import models as _approvals  # noqa: F401
    from app.modules.delivery_points import models as _delivery_points  # noqa: F401
    from app.modules.idempotency import models as _idempotency  # noqa: F401
    from app.modules.missions import models as _missions  # noqa: F401
    from app.modules.orders import models as _orders  # noqa: F401
    from app.modules.products import models as _products  # noqa: F401
    from app.modules.system_events import models as _events  # noqa: F401
    from app.modules.telemetry import models as _telemetry  # noqa: F401
    from app.modules.users import models as _users  # noqa: F401
    from app.modules.vehicles import models as _vehicles  # noqa: F401


def initialize_database() -> None:
    import_models()
    settings = get_settings()
    if settings.auto_create_schema and settings.app_env in {"development", "test"}:
        Base.metadata.create_all(bind=engine)


def database_is_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OSError:
        return False
    except Exception:  # SQLAlchemy wraps driver-specific readiness failures.
        return False
