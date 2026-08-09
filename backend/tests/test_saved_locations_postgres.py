from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import UserRole
from app.modules.saved_locations.models import SavedLocation
from app.modules.saved_locations.schemas import SavedLocationCreate
from app.modules.saved_locations.service import (
    SavedLocationLimitReachedError,
    create_saved_location,
)
from app.modules.users.models import User

POSTGRES_TEST_URL = os.getenv("SAVED_LOCATIONS_POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="SAVED_LOCATIONS_POSTGRES_TEST_URL não configurada",
)


def _payload(index: int) -> SavedLocationCreate:
    return SavedLocationCreate(
        name=f"Local PostgreSQL {index}",
        final_latitude=-23.1 + index / 10_000,
        final_longitude=-46.5 - index / 10_000,
        address_reference=None,
        instructions=None,
        accuracy_meters=5,
        map_provider="maptiler",
        map_type="hybrid",
        region_confirmed=True,
        exact_point_selected=True,
        user_confirmed=True,
        user_confirmed_safe_area=True,
    )


def _create_concurrently(
    session_factory: sessionmaker[Session],
    user_id: UUID,
    index: int,
    barrier: Barrier,
) -> str:
    with session_factory() as session:
        barrier.wait()
        try:
            create_saved_location(session, user_id, _payload(index))
            return "success"
        except SavedLocationLimitReachedError as exc:
            session.rollback()
            return exc.code
        except Exception:
            session.rollback()
            raise


def test_concurrent_creates_never_exceed_three_saved_locations() -> None:
    assert POSTGRES_TEST_URL is not None
    database_url = make_url(POSTGRES_TEST_URL)
    assert database_url.get_backend_name() == "postgresql", (
        "SAVED_LOCATIONS_POSTGRES_TEST_URL deve apontar para PostgreSQL"
    )
    database_name = database_url.database or ""
    assert "test" in database_name.lower(), (
        "O nome do banco de integração deve conter 'test' para impedir uso do banco normal"
    )

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_timeout=10,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=15000 -c lock_timeout=10000",
        },
    )
    integration_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    user_id = uuid4()
    user_created = False

    try:
        with integration_session() as session:
            session.add(
                User(
                    id=user_id,
                    role=UserRole.CUSTOMER,
                    name="Cliente de concorrência PostgreSQL",
                    email=f"saved-location-pg-{uuid4()}@example.test",
                    password_hash="unused-in-integration-test",
                    active=True,
                )
            )
            session.commit()
            user_created = True

        with integration_session() as session:
            create_saved_location(session, user_id, _payload(1))
            create_saved_location(session, user_id, _payload(2))

        barrier = Barrier(3, timeout=10)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    _create_concurrently,
                    integration_session,
                    user_id,
                    index,
                    barrier,
                )
                for index in (3, 4)
            ]
            barrier.wait()
            outcomes = [future.result(timeout=20) for future in futures]

        assert outcomes.count("success") == 1
        assert outcomes.count("SAVED_LOCATION_LIMIT_REACHED") == 1

        with integration_session() as session:
            final_count = session.scalar(
                select(func.count())
                .select_from(SavedLocation)
                .where(SavedLocation.user_id == user_id)
            )
        assert final_count == 3
    finally:
        if user_created:
            with integration_session() as session:
                session.execute(delete(User).where(User.id == user_id))
                session.commit()
        engine.dispose()
