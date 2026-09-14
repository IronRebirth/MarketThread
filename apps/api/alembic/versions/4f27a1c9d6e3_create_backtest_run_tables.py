"""Create persisted backtest run tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4f27a1c9d6e3"
down_revision: str | None = "d903ad3af48b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create backtest run, fold, and evaluation tables."""

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("evaluation_count", sa.Integer(), nullable=False),
        sa.Column("valid_evaluation_count", sa.Integer(), nullable=False),
        sa.Column("rejected_evaluation_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_backtest_runs_completed_at",
        "backtest_runs",
        ["completed_at"],
    )

    op.create_table(
        "backtest_folds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("backtest_id", sa.Uuid(), nullable=False),
        sa.Column("fold_number", sa.Integer(), nullable=False),
        sa.Column("training_periods", sa.JSON(), nullable=False),
        sa.Column("evaluation_periods", sa.JSON(), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["backtest_id"],
            ["backtest_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_backtest_folds_backtest_id",
        "backtest_folds",
        ["backtest_id"],
    )

    op.create_table(
        "backtest_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fold_id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column(
            "signal_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("temporal_error", sa.String(length=64), nullable=True),
        sa.Column("signal_direction", sa.String(length=32), nullable=False),
        sa.Column(
            "observed_direction",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("signal_strength", sa.String(length=32), nullable=False),
        sa.Column(
            "recommendation_state",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("signal_confidence", sa.Float(), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=True),
        sa.Column("forward_return_pct", sa.Float(), nullable=True),
        sa.Column("benchmark_return_pct", sa.Float(), nullable=True),
        sa.Column("relative_return_pct", sa.Float(), nullable=True),
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fold_id"],
            ["backtest_folds.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_backtest_evaluations_fold_id",
        "backtest_evaluations",
        ["fold_id"],
    )
    op.create_index(
        "ix_backtest_evaluations_signal_id",
        "backtest_evaluations",
        ["signal_id"],
    )
    op.create_index(
        "ix_backtest_evaluations_event_id",
        "backtest_evaluations",
        ["event_id"],
    )
    op.create_index(
        "ix_backtest_evaluations_instrument_id",
        "backtest_evaluations",
        ["instrument_id"],
    )
    op.create_index(
        "ix_backtest_evaluations_signal_created_at",
        "backtest_evaluations",
        ["signal_created_at"],
    )
    op.create_index(
        "ix_backtest_evaluations_signal_strength",
        "backtest_evaluations",
        ["signal_strength"],
    )
    op.create_index(
        "ix_backtest_evaluations_recommendation_state",
        "backtest_evaluations",
        ["recommendation_state"],
    )
    op.create_index(
        "ix_backtest_evaluations_horizon",
        "backtest_evaluations",
        ["horizon"],
    )


def downgrade() -> None:
    """Drop persisted backtest run tables."""

    op.drop_index(
        "ix_backtest_evaluations_horizon",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_recommendation_state",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_signal_strength",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_signal_created_at",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_instrument_id",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_event_id",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_signal_id",
        table_name="backtest_evaluations",
    )
    op.drop_index(
        "ix_backtest_evaluations_fold_id",
        table_name="backtest_evaluations",
    )
    op.drop_table("backtest_evaluations")

    op.drop_index(
        "ix_backtest_folds_backtest_id",
        table_name="backtest_folds",
    )
    op.drop_table("backtest_folds")

    op.drop_index(
        "ix_backtest_runs_completed_at",
        table_name="backtest_runs",
    )
    op.drop_table("backtest_runs")
