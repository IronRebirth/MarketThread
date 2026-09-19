"""Add historical state reconstruction support.

Revision ID: m4f7c2d9e1a6
Revises: l3e6b9c2d7f4
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "m4f7c2d9e1a6"
down_revision = "l3e6b9c2d7f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the reconstruction index and seed existing current positions."""

    op.create_index(
        "ix_pos_hist_port_inst_recorded_seq",
        "portfolio_position_history",
        [
            "portfolio_id",
            "instrument_id",
            "recorded_at",
            "sequence_id",
        ],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO portfolio_position_history (
                id,
                portfolio_id,
                instrument_id,
                quantity,
                average_cost,
                event_type,
                recorded_at
            )
            SELECT
                gen_random_uuid(),
                position.portfolio_id,
                position.instrument_id,
                position.quantity,
                position.average_cost,
                'backfilled',
                now()
            FROM portfolio_positions AS position
            WHERE NOT EXISTS (
                SELECT 1
                FROM portfolio_position_history AS history
                WHERE history.portfolio_id = position.portfolio_id
                  AND history.instrument_id = position.instrument_id
            )
            """
        )
    )


def downgrade() -> None:
    """Remove the reconstruction index."""

    op.drop_index(
        "ix_pos_hist_port_inst_recorded_seq",
        table_name="portfolio_position_history",
    )
