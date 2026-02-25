"""initial phase1 baseline

Revision ID: 20260224_0001
Revises:
Create Date: 2026-02-24 20:05:00
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260224_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_file = Path(__file__).resolve().parents[2] / "app" / "db" / "schema.sql"
    sql = schema_file.read_text(encoding="utf-8")
    conn = op.get_bind()
    for stmt in sql.split(";"):
        statement = stmt.strip()
        if statement:
            conn.exec_driver_sql(statement)
    # Align user role constraint with v1 RBAC roles.
    conn.exec_driver_sql("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check")
    conn.exec_driver_sql(
        "ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'analyst', 'reviewer', 'viewer'))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS analysis_results")
    op.execute("DROP TABLE IF EXISTS analysis_run_params")
    op.execute("DROP TABLE IF EXISTS analysis_runs")
    op.execute("DROP TABLE IF EXISTS k_calibrations")
    op.execute("DROP TABLE IF EXISTS cable_config_snapshots")
    op.execute("DROP TABLE IF EXISTS weighing_measurements")
    op.execute("DROP TABLE IF EXISTS weighing_attachments")
    op.execute("DROP TABLE IF EXISTS weighing_campaigns")
    op.execute("DROP TABLE IF EXISTS acquisition_channels")
    op.execute("DROP TABLE IF EXISTS raw_files")
    op.execute("DROP TABLE IF EXISTS acquisitions")
    op.execute("DROP TABLE IF EXISTS sensor_installations")
    op.execute("DROP TABLE IF EXISTS sensors")
    op.execute("DROP TABLE IF EXISTS cable_state_versions")
    op.execute("DROP TABLE IF EXISTS cables")
    op.execute("DROP TABLE IF EXISTS strand_types")
    op.execute("DROP TABLE IF EXISTS bridges")
    op.execute("DROP TABLE IF EXISTS users")
