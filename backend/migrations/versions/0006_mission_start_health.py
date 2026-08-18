"""Persist the independent mission-start safety flag.

Revision ID: 0006_mission_start_health
Revises: 0005_integration_health
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_mission_start_health"
down_revision: str | None = "0005_integration_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.add_column(sa.Column("mission_start_enabled", sa.Boolean()))


def downgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.drop_column("mission_start_enabled")
