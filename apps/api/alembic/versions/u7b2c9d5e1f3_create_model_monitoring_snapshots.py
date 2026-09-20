"""create model monitoring snapshots

Revision ID: v8c3e7f2a4b1
Revises: u7b2c5d9e1f3
"""

import sqlalchemy as sa
from alembic import op

revision = "v8c3e7f2a4b1"
down_revision = "u7b2c5d9e1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_monitoring_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_model_monitoring_snapshots_model_name",
        "model_monitoring_snapshots",
        ["model_name"],
    )
    op.create_index(
        "ix_model_monitoring_snapshots_observed_at",
        "model_monitoring_snapshots",
        ["observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_monitoring_snapshots_observed_at",
        table_name="model_monitoring_snapshots",
    )
    op.drop_index(
        "ix_model_monitoring_snapshots_model_name",
        table_name="model_monitoring_snapshots",
    )
    op.drop_table("model_monitoring_snapshots")
