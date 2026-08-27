"""Persist the independent ARM gate and widen gateway command values.

Revision ID: 0007_vehicle_arm_command
Revises: 0006_mission_start_health
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_vehicle_arm_command"
down_revision: str | None = "0006_mission_start_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.add_column(sa.Column("vehicle_arm_enabled", sa.Boolean()))
    with op.batch_alter_table("gateway_commands") as batch_op:
        batch_op.alter_column(
            "command",
            existing_type=sa.String(length=5),
            type_=sa.String(length=16),
            existing_nullable=False,
        )


def downgrade() -> None:
    connection = op.get_bind()
    incompatible_command = connection.execute(
        sa.text(
            "SELECT command FROM gateway_commands "
            "WHERE length(command) > 5 ORDER BY command LIMIT 1"
        )
    ).scalar_one_or_none()
    if incompatible_command is not None:
        raise RuntimeError(
            "Downgrade 0007 recusado: gateway_commands contém comando maior que 5 caracteres "
            f"({incompatible_command!r}). Preserve a auditoria ou remova o dado explicitamente."
        )
    with op.batch_alter_table("gateway_commands") as batch_op:
        batch_op.alter_column(
            "command",
            existing_type=sa.String(length=16),
            type_=sa.String(length=5),
            existing_nullable=False,
        )
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.drop_column("vehicle_arm_enabled")
