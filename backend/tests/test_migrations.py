from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_alembic_head_contains_optional_integration_health_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-health.db"
    backend_dir = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+pysqlite:///{database_path.as_posix()}",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    columns = {
        column["name"]: column for column in inspect(engine).get_columns("vehicle_health_snapshots")
    }
    expected_columns = {
        "connection_state",
        "connection_mode",
        "connection_topology",
        "connection_endpoint",
        "serial_port",
        "connection_baud",
        "mavlink_system_id",
        "mavlink_component_id",
        "heartbeat_age_seconds",
        "last_heartbeat_at",
        "current_latitude",
        "current_longitude",
        "current_altitude_m",
        "mission_upload_enabled",
        "flight_commands_enabled",
        "mission_start_enabled",
        "connection_error",
    }
    assert expected_columns <= columns.keys()
    assert all(columns[name]["nullable"] for name in expected_columns)
