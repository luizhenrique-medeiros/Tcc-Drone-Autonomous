from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_alembic_head_contains_optional_integration_health_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-health.db"
    backend_dir = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+pysqlite:///{database_path.as_posix()}",
    }
    previous_result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0006_mission_start_health"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert previous_result.returncode == 0, previous_result.stdout + previous_result.stderr

    previous_engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    previous_columns = {
        column["name"]
        for column in inspect(previous_engine).get_columns("vehicle_health_snapshots")
    }
    assert "vehicle_arm_enabled" not in previous_columns
    previous_engine.dispose()

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
        "vehicle_arm_enabled",
        "connection_error",
    }
    assert expected_columns <= columns.keys()
    assert all(columns[name]["nullable"] for name in expected_columns)

    command_column = next(
        column
        for column in inspect(engine).get_columns("gateway_commands")
        if column["name"] == "command"
    )
    assert command_column["type"].length >= len("CONTINUE")
    engine.dispose()

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0006_mission_start_health"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert downgrade.returncode == 0, downgrade.stdout + downgrade.stderr
    downgraded_engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    downgraded_columns = {
        column["name"]
        for column in inspect(downgraded_engine).get_columns("vehicle_health_snapshots")
    }
    assert "vehicle_arm_enabled" not in downgraded_columns
    downgraded_engine.dispose()

    reupgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert reupgrade.returncode == 0, reupgrade.stdout + reupgrade.stderr


def test_arm_migration_downgrade_refuses_command_that_does_not_fit(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-unsafe-downgrade.db"
    backend_dir = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+pysqlite:///{database_path.as_posix()}",
    }
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr

    engine = create_engine(f"sqlite+pysqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO gateway_commands "
                "(id, mission_id, requested_by_id, command, status, requested_at) "
                "VALUES (:id, :mission_id, :requested_by_id, 'CONTINUE', 'PENDING', "
                ":requested_at)"
            ),
            {
                "id": "00000000000000000000000000000001",
                "mission_id": "00000000000000000000000000000002",
                "requested_by_id": "00000000000000000000000000000003",
                "requested_at": "2026-08-21 12:00:00+00:00",
            },
        )
    engine.dispose()

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0006_mission_start_health"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert downgrade.returncode != 0
    assert "Downgrade 0007 recusado" in downgrade.stdout + downgrade.stderr
