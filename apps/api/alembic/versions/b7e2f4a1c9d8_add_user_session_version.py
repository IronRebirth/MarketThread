"""add user session version

Revision ID: b7e2f4a1c9d8
Revises: x1e5f7a9b3c2
"""

import sqlalchemy as sa

from alembic import op

revision = "b7e2f4a1c9d8"
down_revision = "x1e5f7a9b3c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "session_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
