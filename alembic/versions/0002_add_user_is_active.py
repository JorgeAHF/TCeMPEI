"""Add is_active to users

Revision ID: 0002_add_user_is_active
Revises: 0001_initial_schema
Create Date: 2025-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_user_is_active"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
