"""
ETAPA 1: creación de esquema inicial.

Resumen de cambios:
- Crea todas las tablas y enumeraciones definidas actualmente en los modelos ORM.
- Incluye constraints y defaults que preservan compatibilidad con datos existentes al no modificar estructuras previas.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


channel_status = sa.Enum(
    "ok",
    "warning_no_installation",
    "warning_mismatch_installation",
    name="channel_status",
    create_type=False,
)
file_kind = sa.Enum("raw_csv", "normalized_csv", name="file_kind", create_type=False)
quality_flag = sa.Enum("ok", "doubtful", "bad", name="quality_flag", create_type=False)


def _create_enum_if_not_exists(bind, enum_type: sa.Enum) -> None:
    enum_name = enum_type.name
    quoted_values = ", ".join(f"'{value}'" for value in enum_type.enums)
    bind.exec_driver_sql(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN
                EXECUTE 'CREATE TYPE "{enum_name}" AS ENUM ({quoted_values})';
            END IF;
        END$$;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    _create_enum_if_not_exists(bind, channel_status)
    _create_enum_if_not_exists(bind, file_kind)
    _create_enum_if_not_exists(bind, quality_flag)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="Consulta"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "bridges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False, unique=True),
        sa.Column("clave_interna", sa.String(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "strand_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("diametro_mm", sa.Float(), nullable=False),
        sa.Column("area_mm2", sa.Float(), nullable=False),
        sa.Column("e_mpa", sa.Float(), nullable=False),
        sa.Column("fu_default", sa.Float(), nullable=False),
        sa.Column("mu_por_toron_kg_m", sa.Float(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.CheckConstraint("diametro_mm > 0"),
        sa.CheckConstraint("area_mm2 > 0"),
        sa.CheckConstraint("e_mpa > 0"),
        sa.CheckConstraint("fu_default > 0"),
    )

    op.create_table(
        "cables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bridge_id", sa.Integer(), sa.ForeignKey("bridges.id"), nullable=False),
        sa.Column("nombre_en_puente", sa.String(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("bridge_id", "nombre_en_puente"),
    )

    op.create_table(
        "cable_state_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("length_effective_m", sa.Float(), nullable=False),
        sa.Column("length_total_m", sa.Float(), nullable=True),
        sa.Column("strands_total", sa.Integer(), nullable=False),
        sa.Column("strands_active", sa.Integer(), nullable=False),
        sa.Column("strands_inactive", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("strand_type_id", sa.Integer(), sa.ForeignKey("strand_types.id"), nullable=False),
        sa.Column("diametro_mm", sa.Float(), nullable=False),
        sa.Column("area_mm2", sa.Float(), nullable=False),
        sa.Column("e_mpa", sa.Float(), nullable=False),
        sa.Column("mu_total_kg_m", sa.Float(), nullable=False),
        sa.Column("mu_active_basis_kg_m", sa.Float(), nullable=False),
        sa.Column("design_tension_tf", sa.Float(), nullable=False),
        sa.Column("fu_override", sa.Float(), nullable=True),
        sa.Column("antivandalic_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("antivandalic_length_m", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("cable_id", "valid_from", name="uq_cable_version_start"),
        sa.CheckConstraint("length_effective_m > 0"),
        sa.CheckConstraint("(valid_to IS NULL) OR (valid_to > valid_from)", name="valid_dates"),
        sa.CheckConstraint("strands_total > 0"),
        sa.CheckConstraint("strands_active > 0"),
        sa.CheckConstraint("strands_inactive >= 0"),
        sa.CheckConstraint("strands_active <= strands_total", name="strands_active_le_total"),
        sa.CheckConstraint("strands_inactive <= strands_total", name="strands_inactive_le_total"),
        sa.CheckConstraint("diametro_mm > 0"),
        sa.CheckConstraint("area_mm2 > 0"),
        sa.CheckConstraint("e_mpa > 0"),
        sa.CheckConstraint("design_tension_tf > 0"),
        sa.CheckConstraint("mu_total_kg_m > 0"),
        sa.CheckConstraint("mu_active_basis_kg_m > 0"),
        sa.CheckConstraint(
            "(NOT antivandalic_enabled) OR (antivandalic_length_m IS NOT NULL)",
            name="antivandalic_length_required",
        ),
    )

    op.create_table(
        "sensors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sensor_type", sa.String(), nullable=False, server_default="acelerometro"),
        sa.Column("serial_or_asset_id", sa.String(), nullable=False, unique=True),
        sa.Column("unit", sa.String(), nullable=False, server_default="g"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "sensor_installations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sensor_id", sa.Integer(), sa.ForeignKey("sensors.id"), nullable=False),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("installed_from", sa.DateTime(), nullable=False),
        sa.Column("installed_to", sa.DateTime(), nullable=True),
        sa.Column("height_m", sa.Float(), nullable=False),
        sa.Column("mounting_details", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.CheckConstraint("(installed_to IS NULL) OR (installed_to > installed_from)", name="valid_installation_dates"),
        sa.CheckConstraint("height_m > 0"),
    )

    op.create_table(
        "acquisitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bridge_id", sa.Integer(), sa.ForeignKey("bridges.id"), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("Fs_Hz", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "raw_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("acquisition_id", sa.Integer(), sa.ForeignKey("acquisitions.id"), nullable=False),
        sa.Column("file_kind", file_kind, nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.UniqueConstraint("acquisition_id", "file_kind", name="uq_acquisition_file_kind"),
        sa.CheckConstraint("file_size_bytes > 0"),
        sa.CheckConstraint("length(sha256) = 64", name="sha256_len"),
    )

    op.create_table(
        "acquisition_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("acquisition_id", sa.Integer(), sa.ForeignKey("acquisitions.id"), nullable=False),
        sa.Column("csv_column_name", sa.String(), nullable=False),
        sa.Column("sensor_id", sa.Integer(), sa.ForeignKey("sensors.id"), nullable=False),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("height_m", sa.Float(), nullable=False),
        sa.Column("status_flag", channel_status, nullable=False, server_default="ok"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("acquisition_id", "csv_column_name"),
        sa.CheckConstraint("height_m > 0"),
    )

    op.create_table(
        "weighing_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bridge_id", sa.Integer(), sa.ForeignKey("bridges.id"), nullable=False),
        sa.Column("performed_at", sa.DateTime(), nullable=False),
        sa.Column("performed_by", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("equipment", sa.String(), nullable=False),
        sa.Column("temperature_C", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
    )

    op.create_table(
        "weighing_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weighing_campaign_id", sa.Integer(), sa.ForeignKey("weighing_campaigns.id"), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "weighing_measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("weighing_campaign_id", sa.Integer(), sa.ForeignKey("weighing_campaigns.id"), nullable=False),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("measured_tension_tf", sa.Float(), nullable=False),
        sa.Column("measured_temperature_C", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.CheckConstraint("measured_tension_tf > 0"),
    )

    op.create_table(
        "cable_config_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("source_state_version_id", sa.Integer(), sa.ForeignKey("cable_state_versions.id"), nullable=True),
        sa.Column("effective_length_m", sa.Float(), nullable=False),
        sa.Column("mu_basis", sa.String(), nullable=False),
        sa.Column("mu_value_kg_m", sa.Float(), nullable=False),
        sa.Column("strands_active", sa.Integer(), nullable=False),
        sa.Column("strands_total", sa.Integer(), nullable=False),
        sa.Column("strand_type_id", sa.Integer(), sa.ForeignKey("strand_types.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.CheckConstraint("effective_length_m > 0"),
        sa.CheckConstraint("mu_value_kg_m > 0"),
        sa.CheckConstraint("strands_active > 0"),
        sa.CheckConstraint("strands_total > 0"),
        sa.CheckConstraint("strands_active <= strands_total", name="snap_active_le_total"),
    )

    op.create_table(
        "k_calibrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column(
            "derived_from_weighing_measurement_id",
            sa.Integer(),
            sa.ForeignKey("weighing_measurements.id"),
            nullable=False,
        ),
        sa.Column("config_snapshot_id", sa.Integer(), sa.ForeignKey("cable_config_snapshots.id"), nullable=False),
        sa.Column("k_value", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("computed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.CheckConstraint("k_value > 0"),
        sa.CheckConstraint("(valid_to IS NULL) OR (valid_to > valid_from)", name="valid_k_dates"),
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("acquisition_id", sa.Integer(), sa.ForeignKey("acquisitions.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    op.create_table(
        "analysis_run_params",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("segment_pct_start", sa.Float(), nullable=False),
        sa.Column("segment_pct_end", sa.Float(), nullable=False),
        sa.Column("nperseg", sa.Integer(), nullable=False),
        sa.Column("noverlap", sa.Integer(), nullable=False),
        sa.Column("sigma", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("min_distance_hz", sa.Float(), nullable=False),
        sa.Column("n_harmonics", sa.Integer(), nullable=False),
        sa.Column("f0_mode", sa.String(), nullable=False),
        sa.Column("f0_hint_hz", sa.Float(), nullable=True),
        sa.Column("tol_hz", sa.Float(), nullable=True),
        sa.CheckConstraint("segment_pct_start >= 0 AND segment_pct_start < segment_pct_end"),
        sa.CheckConstraint("segment_pct_end <= 100"),
        sa.CheckConstraint("noverlap >= 0"),
        sa.CheckConstraint("nperseg > 0"),
        sa.CheckConstraint("noverlap < nperseg"),
    )

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("cable_id", sa.Integer(), sa.ForeignKey("cables.id"), nullable=False),
        sa.Column("f0_hz", sa.Float(), nullable=False),
        sa.Column("harmonics_json", sa.Text(), nullable=False),
        sa.Column("k_used_value", sa.Float(), nullable=False),
        sa.Column("k_used_calibration_id", sa.Integer(), sa.ForeignKey("k_calibrations.id"), nullable=False),
        sa.Column("tension_tf", sa.Float(), nullable=False),
        sa.Column("df_hz", sa.Float(), nullable=False),
        sa.Column("snr_metric", sa.Float(), nullable=False),
        sa.Column("quality_flag", quality_flag, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.CheckConstraint("f0_hz > 0"),
        sa.CheckConstraint("k_used_value > 0"),
        sa.CheckConstraint("tension_tf > 0"),
    )


def downgrade() -> None:
    op.drop_table("analysis_results")
    op.drop_table("analysis_run_params")
    op.drop_table("analysis_runs")
    op.drop_table("k_calibrations")
    op.drop_table("cable_config_snapshots")
    op.drop_table("weighing_measurements")
    op.drop_table("weighing_attachments")
    op.drop_table("weighing_campaigns")
    op.drop_table("acquisition_channels")
    op.drop_table("raw_files")
    op.drop_table("acquisitions")
    op.drop_table("sensor_installations")
    op.drop_table("sensors")
    op.drop_table("cable_state_versions")
    op.drop_table("cables")
    op.drop_table("strand_types")
    op.drop_table("bridges")
    op.drop_table("users")

    channel_status.drop(op.get_bind(), checkfirst=True)
    file_kind.drop(op.get_bind(), checkfirst=True)
    quality_flag.drop(op.get_bind(), checkfirst=True)
