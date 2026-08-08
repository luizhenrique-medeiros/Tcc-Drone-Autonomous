from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Enum, String, engine_from_config, pool

from app.core.config import get_settings
from app.database.base import Base
from app.database.session import import_models
from app.database.types import GeographyPoint

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().sqlalchemy_database_url)
import_models()
target_metadata = Base.metadata


def include_application_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    _compare_to: object | None,
) -> bool:
    table_name = getattr(getattr(object_, "table", None), "name", None)
    return not (reflected and (name == "spatial_ref_sys" or table_name == "spatial_ref_sys"))


def compare_column_types(
    _context: object,
    _inspected_column: object,
    metadata_column: object,
    inspected_type: object,
    metadata_type: object,
) -> bool | None:
    # The stock PostgreSQL dialect reflects PostGIS geography as an unknown type.
    # Scope the exception to the three metadata columns that deliberately use it.
    if isinstance(metadata_type, GeographyPoint):
        return False
    # Revision 0002 stores operational provenance as VARCHAR(20). The domain
    # model deliberately wraps those same values in a non-native Enum for
    # validation, which is not a database type change.
    table_name = getattr(getattr(metadata_column, "table", None), "name", None)
    column_name = getattr(metadata_column, "name", None)
    operational_columns = {
        ("vehicles", "operational_source"),
        ("vehicle_health_snapshots", "source"),
        ("telemetry_logs", "source"),
    }
    if (
        (table_name, column_name) in operational_columns
        and isinstance(metadata_type, Enum)
        and not metadata_type.native_enum
        and isinstance(inspected_type, String)
        and inspected_type.length == 20
    ):
        return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_column_types,
        include_object=include_application_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_column_types,
            include_object=include_application_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
