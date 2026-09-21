"""fix admin audit log timestamp default

Revision ID: x1e5f7a9b3c2
Revises: w9d4f8a3b2c1
"""

import sqlalchemy as sa

from alembic import op

revision = "x1e5f7a9b3c2"
down_revision = "w9d4f8a3b2c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "admin_audit_logs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "admin_audit_logs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=None,
    )
