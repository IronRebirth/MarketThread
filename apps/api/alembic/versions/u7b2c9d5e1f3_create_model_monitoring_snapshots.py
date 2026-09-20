"""create model monitoring snapshots

Revision ID: u7b2c9d5e1f3
Revises: t6a1c9e4b7d8
"""

from alembic import op
import sqlalchemy as sa

revision = "u7b2c9d5e1f3"
down_revision = "t6a1c9e4b7d8"
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
    op.drop_index("ix_model_monitoring_snapshots_observed_at", table_name="model_monitoring_snapshots")
    op.drop_index("ix_model_monitoring_snapshots_model_name", table_name="model_monitoring_snapshots")
    op.drop_table("model_monitoring_snapshots")
