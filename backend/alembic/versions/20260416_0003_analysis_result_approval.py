"""analysis_results approval columns and anomaly detection support

Revision ID: 20260416_0003
Revises: 20260225_0002
Create Date: 2026-04-16 00:00:00
"""

from __future__ import annotations

from alembic import op

revision = "20260416_0003"
down_revision = "20260225_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        "ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS is_approved BOOLEAN NOT NULL DEFAULT FALSE"
    )
    conn.exec_driver_sql(
        "ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS approved_by_user_id BIGINT REFERENCES users(id)"
    )
    conn.exec_driver_sql(
        "ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE analysis_results DROP COLUMN IF EXISTS approved_at")
    conn.exec_driver_sql("ALTER TABLE analysis_results DROP COLUMN IF EXISTS approved_by_user_id")
    conn.exec_driver_sql("ALTER TABLE analysis_results DROP COLUMN IF EXISTS is_approved")
