from datetime import datetime
from typing import List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


status_enum = Enum("ok", "warning_no_installation", "warning_mismatch_installation", name="channel_status")
file_kind_enum = Enum("raw_csv", "normalized_csv", name="file_kind")
quality_flag_enum = Enum("ok", "doubtful", "bad", name="quality_flag")


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class User(Base, Timestamped):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="Consulta")


class Bridge(Base, Timestamped):
    __tablename__ = "bridges"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    clave_interna: Mapped[str | None] = mapped_column(String, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text)

    cables: Mapped[List["Cable"]] = relationship(back_populates="bridge")


class StrandType(Base, Timestamped):
    __tablename__ = "strand_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    diametro_mm: Mapped[float] = mapped_column(Float, nullable=False)
    area_mm2: Mapped[float] = mapped_column(Float, nullable=False)
    e_mpa: Mapped[float] = mapped_column(Float, nullable=False)
    fu_default: Mapped[float] = mapped_column(Float, nullable=False)
    mu_por_toron_kg_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("diametro_mm > 0"),
        CheckConstraint("area_mm2 > 0"),
        CheckConstraint("e_mpa > 0"),
        CheckConstraint("fu_default > 0"),
    )


class Cable(Base, Timestamped):
    __tablename__ = "cables"
    __table_args__ = (UniqueConstraint("bridge_id", "nombre_en_puente"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bridge_id: Mapped[int] = mapped_column(ForeignKey("bridges.id"), nullable=False)
    nombre_en_puente: Mapped[str] = mapped_column(String, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text)

    bridge: Mapped[Bridge] = relationship(back_populates="cables")
    states: Mapped[List["CableStateVersion"]] = relationship(back_populates="cable")


class CableStateVersion(Base, Timestamped):
    __tablename__ = "cable_state_versions"
    __table_args__ = (
        UniqueConstraint("cable_id", "valid_from", name="uq_cable_version_start"),
        CheckConstraint("length_effective_m > 0"),
        CheckConstraint("(valid_to IS NULL) OR (valid_to > valid_from)", name="valid_dates"),
        CheckConstraint("strands_total > 0"),
        CheckConstraint("strands_active > 0"),
        CheckConstraint("strands_inactive >= 0"),
        CheckConstraint("strands_active <= strands_total", name="strands_active_le_total"),
        CheckConstraint("strands_inactive <= strands_total", name="strands_inactive_le_total"),
        CheckConstraint("diametro_mm > 0"),
        CheckConstraint("area_mm2 > 0"),
        CheckConstraint("e_mpa > 0"),
        CheckConstraint("design_tension_tf > 0"),
        CheckConstraint("mu_total_kg_m > 0"),
        CheckConstraint("mu_active_basis_kg_m > 0"),
        CheckConstraint(
            "(NOT antivandalic_enabled) OR (antivandalic_length_m IS NOT NULL)",
            name="antivandalic_length_required",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    length_effective_m: Mapped[float] = mapped_column(Float, nullable=False)
    length_total_m: Mapped[float | None] = mapped_column(Float)
    strands_total: Mapped[int] = mapped_column(Integer, nullable=False)
    strands_active: Mapped[int] = mapped_column(Integer, nullable=False)
    strands_inactive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strand_type_id: Mapped[int] = mapped_column(ForeignKey("strand_types.id"), nullable=False)
    diametro_mm: Mapped[float] = mapped_column(Float, nullable=False)
    area_mm2: Mapped[float] = mapped_column(Float, nullable=False)
    e_mpa: Mapped[float] = mapped_column(Float, nullable=False)
    mu_total_kg_m: Mapped[float] = mapped_column(Float, nullable=False)
    mu_active_basis_kg_m: Mapped[float] = mapped_column(Float, nullable=False)
    design_tension_tf: Mapped[float] = mapped_column(Float, nullable=False)
    fu_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    antivandalic_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    antivandalic_length_m: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)

    cable: Mapped[Cable] = relationship(back_populates="states")
    strand_type: Mapped[StrandType] = relationship()


class Sensor(Base, Timestamped):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_type: Mapped[str] = mapped_column(String, nullable=False, default="acelerometro")
    serial_or_asset_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="g")
    notas: Mapped[str | None] = mapped_column(Text)


class SensorInstallation(Base, Timestamped):
    __tablename__ = "sensor_installations"
    __table_args__ = (
        CheckConstraint("(installed_to IS NULL) OR (installed_to > installed_from)", name="valid_installation_dates"),
        CheckConstraint("height_m > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"), nullable=False)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    installed_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    installed_to: Mapped[datetime | None] = mapped_column(DateTime)
    height_m: Mapped[float] = mapped_column(Float, nullable=False)
    mounting_details: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class Acquisition(Base, Timestamped):
    __tablename__ = "acquisitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    bridge_id: Mapped[int] = mapped_column(ForeignKey("bridges.id"), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    operator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    Fs_Hz: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class RawFile(Base):
    __tablename__ = "raw_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    acquisition_id: Mapped[int] = mapped_column(ForeignKey("acquisitions.id"), nullable=False)
    file_kind: Mapped[str] = mapped_column(file_kind_enum, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("acquisition_id", "file_kind", name="uq_acquisition_file_kind"),
        CheckConstraint("file_size_bytes > 0"),
        CheckConstraint("length(sha256) = 64", name="sha256_len"),
    )


class AcquisitionChannel(Base):
    __tablename__ = "acquisition_channels"
    __table_args__ = (
        UniqueConstraint("acquisition_id", "csv_column_name"),
        CheckConstraint("height_m > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    acquisition_id: Mapped[int] = mapped_column(ForeignKey("acquisitions.id"), nullable=False)
    csv_column_name: Mapped[str] = mapped_column(String, nullable=False)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"), nullable=False)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    height_m: Mapped[float] = mapped_column(Float, nullable=False)
    status_flag: Mapped[str] = mapped_column(status_enum, nullable=False, default="ok")
    notes: Mapped[str | None] = mapped_column(Text)


class WeighingCampaign(Base, Timestamped):
    __tablename__ = "weighing_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    bridge_id: Mapped[int] = mapped_column(ForeignKey("bridges.id"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    performed_by: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    equipment: Mapped[str] = mapped_column(String, nullable=False)
    temperature_C: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class WeighingAttachment(Base):
    __tablename__ = "weighing_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    weighing_campaign_id: Mapped[int] = mapped_column(ForeignKey("weighing_campaigns.id"), nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class WeighingMeasurement(Base, Timestamped):
    __tablename__ = "weighing_measurements"
    __table_args__ = (CheckConstraint("measured_tension_tf > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    weighing_campaign_id: Mapped[int] = mapped_column(ForeignKey("weighing_campaigns.id"), nullable=False)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    measured_tension_tf: Mapped[float] = mapped_column(Float, nullable=False)
    measured_temperature_C: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class CableConfigSnapshot(Base, Timestamped):
    __tablename__ = "cable_config_snapshots"
    __table_args__ = (
        CheckConstraint("effective_length_m > 0"),
        CheckConstraint("mu_value_kg_m > 0"),
        CheckConstraint("strands_active > 0"),
        CheckConstraint("strands_total > 0"),
        CheckConstraint("strands_active <= strands_total", name="snap_active_le_total"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    source_state_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("cable_state_versions.id"), nullable=True
    )
    effective_length_m: Mapped[float] = mapped_column(Float, nullable=False)
    mu_basis: Mapped[str] = mapped_column(String, nullable=False)
    mu_value_kg_m: Mapped[float] = mapped_column(Float, nullable=False)
    strands_active: Mapped[int] = mapped_column(Integer, nullable=False)
    strands_total: Mapped[int] = mapped_column(Integer, nullable=False)
    strand_type_id: Mapped[int | None] = mapped_column(ForeignKey("strand_types.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class KCalibration(Base, Timestamped):
    __tablename__ = "k_calibrations"
    __table_args__ = (
        CheckConstraint("k_value > 0"),
        CheckConstraint("(valid_to IS NULL) OR (valid_to > valid_from)", name="valid_k_dates"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    derived_from_weighing_measurement_id: Mapped[int] = mapped_column(
        ForeignKey("weighing_measurements.id"), nullable=False
    )
    config_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("cable_config_snapshots.id"), nullable=False
    )
    k_value: Mapped[float] = mapped_column(Float, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    computed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class AnalysisRun(Base, Timestamped):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    acquisition_id: Mapped[int] = mapped_column(ForeignKey("acquisitions.id"), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class AnalysisRunParams(Base):
    __tablename__ = "analysis_run_params"
    __table_args__ = (
        CheckConstraint("segment_pct_start >= 0 AND segment_pct_start < segment_pct_end"),
        CheckConstraint("segment_pct_end <= 100"),
        CheckConstraint("noverlap >= 0"),
        CheckConstraint("nperseg > 0"),
        CheckConstraint("noverlap < nperseg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    segment_pct_start: Mapped[float] = mapped_column(Float, nullable=False)
    segment_pct_end: Mapped[float] = mapped_column(Float, nullable=False)
    nperseg: Mapped[int] = mapped_column(Integer, nullable=False)
    noverlap: Mapped[int] = mapped_column(Integer, nullable=False)
    sigma: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    min_distance_hz: Mapped[float] = mapped_column(Float, nullable=False)
    n_harmonics: Mapped[int] = mapped_column(Integer, nullable=False)
    f0_mode: Mapped[str] = mapped_column(String, nullable=False)
    f0_hint_hz: Mapped[float | None] = mapped_column(Float)
    tol_hz: Mapped[float | None] = mapped_column(Float)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint("f0_hz > 0"),
        CheckConstraint("k_used_value > 0"),
        CheckConstraint("tension_tf > 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"), nullable=False)
    cable_id: Mapped[int] = mapped_column(ForeignKey("cables.id"), nullable=False)
    f0_hz: Mapped[float] = mapped_column(Float, nullable=False)
    harmonics_json: Mapped[str] = mapped_column(Text, nullable=False)
    k_used_value: Mapped[float] = mapped_column(Float, nullable=False)
    k_used_calibration_id: Mapped[int] = mapped_column(ForeignKey("k_calibrations.id"), nullable=False)
    tension_tf: Mapped[float] = mapped_column(Float, nullable=False)
    df_hz: Mapped[float] = mapped_column(Float, nullable=False)
    snr_metric: Mapped[float] = mapped_column(Float, nullable=False)
    quality_flag: Mapped[str] = mapped_column(quality_flag_enum, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

