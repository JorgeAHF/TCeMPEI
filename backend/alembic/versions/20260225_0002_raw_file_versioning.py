"""raw file versioning and per-campaign duplicate policy

Revision ID: 20260225_0002
Revises: 20260224_0001
Create Date: 2026-02-25 20:20:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260225_0002"
down_revision = "20260224_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS source_raw_file_id BIGINT")
    conn.exec_driver_sql("ALTER TABLE raw_files ADD COLUMN IF NOT EXISTS version_no INTEGER")

    conn.exec_driver_sql(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY acquisition_id, file_kind
                    ORDER BY created_at, id
                ) AS rn
            FROM raw_files
        )
        UPDATE raw_files rf
        SET version_no = ranked.rn
        FROM ranked
        WHERE rf.id = ranked.id
          AND rf.version_no IS NULL
        """
    )
    conn.exec_driver_sql("UPDATE raw_files SET version_no = 1 WHERE version_no IS NULL")

    conn.exec_driver_sql("ALTER TABLE raw_files ALTER COLUMN version_no SET NOT NULL")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS ck_raw_files_version_no_positive")
    conn.exec_driver_sql(
        "ALTER TABLE raw_files ADD CONSTRAINT ck_raw_files_version_no_positive CHECK (version_no > 0)"
    )
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS fk_raw_files_source_raw_file_id")
    conn.exec_driver_sql(
        """
        ALTER TABLE raw_files
        ADD CONSTRAINT fk_raw_files_source_raw_file_id
        FOREIGN KEY (source_raw_file_id) REFERENCES raw_files(id) ON DELETE SET NULL
        """
    )

    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS uq_raw_files_sha")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS uq_raw_files_acq_kind_version")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS uq_raw_files_acq_kind_sha")
    conn.exec_driver_sql(
        """
        ALTER TABLE raw_files
        ADD CONSTRAINT uq_raw_files_acq_kind_version
        UNIQUE (acquisition_id, file_kind, version_no)
        """
    )
    conn.exec_driver_sql(
        """
        ALTER TABLE raw_files
        ADD CONSTRAINT uq_raw_files_acq_kind_sha
        UNIQUE (acquisition_id, file_kind, sha256)
        """
    )
    conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_raw_files_source_raw_file_id ON raw_files(source_raw_file_id)")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DROP INDEX IF EXISTS idx_raw_files_source_raw_file_id")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS uq_raw_files_acq_kind_sha")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS uq_raw_files_acq_kind_version")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS fk_raw_files_source_raw_file_id")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS ck_raw_files_version_no_positive")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP CONSTRAINT IF EXISTS uq_raw_files_sha")
    conn.exec_driver_sql("ALTER TABLE raw_files ADD CONSTRAINT uq_raw_files_sha UNIQUE (sha256)")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP COLUMN IF EXISTS version_no")
    conn.exec_driver_sql("ALTER TABLE raw_files DROP COLUMN IF EXISTS source_raw_file_id")
