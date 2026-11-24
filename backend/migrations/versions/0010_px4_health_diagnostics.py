"""Store PX4 diagnostics independently of operational authorization checks."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_px4_health_diagnostics"
down_revision: str | None = "0009_px4_review_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch:
        batch.add_column(sa.Column("px4_diagnostics", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch:
        batch.drop_column("px4_diagnostics")
