from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    role = Column(String, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Bridge(Base):
    __tablename__ = "bridges"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)
    clave_interna = Column(String)
    num_tirantes = Column(Integer)
    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))

    cables = relationship("Cable", back_populates="bridge")


class StrandType(Base):
    __tablename__ = "strand_types"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)
    diametro_mm = Column(Float, nullable=False)
    area_mm2 = Column(Float, nullable=False)
    E_MPa = Column(Float, nullable=False)
    Fu_default = Column(Float, nullable=False)
    mu_por_toron_kg_m = Column(Float, nullable=False)
    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))


class Cable(Base):
    __tablename__ = "cables"
    id = Column(Integer, primary_key=True)
    bridge_id = Column(Integer, ForeignKey("bridges.id"), nullable=False)
    nombre_en_puente = Column(String, nullable=False)
    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))

    bridge = relationship("Bridge", back_populates="cables")
    states = relationship("CableStateVersion", back_populates="cable")


class CableStateVersion(Base):
    __tablename__ = "cable_state_versions"
    id = Column(Integer, primary_key=True)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime)
    length_effective_m = Column(Float, nullable=False)
    length_total_m = Column(Float)
    strands_total = Column(Integer, nullable=False)
    strands_active = Column(Integer, nullable=False)
    strands_inactive = Column(Integer, default=0, nullable=False)
    strand_type_id = Column(Integer, ForeignKey("strand_types.id"), nullable=False)
    diametro_mm = Column(Float, nullable=False)
    area_mm2 = Column(Float, nullable=False)
    E_MPa = Column(Float, nullable=False)
    mu_total_kg_m = Column(Float, nullable=False)
    mu_active_basis_kg_m = Column(Float, nullable=False)
    design_tension_tf = Column(Float, nullable=False)
    Fu_override = Column(Float)
    antivandalic_enabled = Column(Boolean, default=False, nullable=False)
    antivandalic_length_m = Column(Float)
    source = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))

    cable = relationship("Cable", back_populates="states")
    strand_type = relationship("StrandType")

    __table_args__ = (
        CheckConstraint("strands_active <= strands_total", name="chk_strands_active_total_orm"),
    )


class Sensor(Base):
    __tablename__ = "sensors"
    id = Column(Integer, primary_key=True)
    sensor_type = Column(String, nullable=False)
    serial_or_asset_id = Column(String, unique=True, nullable=False)
    unit = Column(String, nullable=False)
    notas = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))


class SensorInstallation(Base):
    __tablename__ = "sensor_installations"
    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=False)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    installed_from = Column(DateTime, nullable=False)
    installed_to = Column(DateTime)
    height_m = Column(Float, nullable=False)
    mounting_details = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))


class Acquisition(Base):
    __tablename__ = "acquisitions"
    id = Column(Integer, primary_key=True)
    bridge_id = Column(Integer, ForeignKey("bridges.id"), nullable=False)
    acquired_at = Column(DateTime, nullable=False)
    operator_user_id = Column(Integer, ForeignKey("users.id"))
    Fs_Hz = Column(Float, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))


class RawFile(Base):
    __tablename__ = "raw_files"
    id = Column(Integer, primary_key=True)
    acquisition_id = Column(Integer, ForeignKey("acquisitions.id"), nullable=False)
    file_kind = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    sha256 = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    parser_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AcquisitionChannel(Base):
    __tablename__ = "acquisition_channels"
    id = Column(Integer, primary_key=True)
    acquisition_id = Column(Integer, ForeignKey("acquisitions.id"), nullable=False)
    csv_column_name = Column(String, nullable=False)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=False)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    height_m = Column(Float, nullable=False)
    status_flag = Column(String, nullable=False)
    notes = Column(Text)


class WeighingCampaign(Base):
    __tablename__ = "weighing_campaigns"
    id = Column(Integer, primary_key=True)
    bridge_id = Column(Integer, ForeignKey("bridges.id"), nullable=False)
    performed_at = Column(DateTime, nullable=False)
    performed_by = Column(String, nullable=False)
    method = Column(String, nullable=False)
    equipment = Column(String, nullable=False)
    temperature_C = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))


class WeighingAttachment(Base):
    __tablename__ = "weighing_attachments"
    id = Column(Integer, primary_key=True)
    weighing_campaign_id = Column(Integer, ForeignKey("weighing_campaigns.id"), nullable=False)
    storage_path = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    sha256 = Column(String(64))
    notes = Column(Text)


class WeighingMeasurement(Base):
    __tablename__ = "weighing_measurements"
    id = Column(Integer, primary_key=True)
    weighing_campaign_id = Column(Integer, ForeignKey("weighing_campaigns.id"), nullable=False)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    measured_tension_tf = Column(Float, nullable=False)
    measured_temperature_C = Column(Float)
    notes = Column(Text)


class CableConfigSnapshot(Base):
    __tablename__ = "cable_config_snapshots"
    id = Column(Integer, primary_key=True)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    source_state_version_id = Column(Integer, ForeignKey("cable_state_versions.id"))
    effective_length_m = Column(Float, nullable=False)
    mu_basis = Column(String, nullable=False)
    mu_value_kg_m = Column(Float, nullable=False)
    strands_active = Column(Integer, nullable=False)
    strands_total = Column(Integer, nullable=False)
    strand_type_id = Column(Integer, ForeignKey("strand_types.id"))
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class KCalibration(Base):
    __tablename__ = "k_calibrations"
    id = Column(Integer, primary_key=True)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    derived_from_weighing_measurement_id = Column(Integer, ForeignKey("weighing_measurements.id"), nullable=False)
    config_snapshot_id = Column(Integer, ForeignKey("cable_config_snapshots.id"), nullable=False)
    k_value = Column(Float, nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime)
    algorithm_version = Column(String, nullable=False)
    computed_by_user_id = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id = Column(Integer, primary_key=True)
    acquisition_id = Column(Integer, ForeignKey("acquisitions.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    algorithm_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text)


class AnalysisRunParams(Base):
    __tablename__ = "analysis_run_params"
    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    segment_pct_start = Column(Float, nullable=False)
    segment_pct_end = Column(Float, nullable=False)
    nperseg = Column(Integer, nullable=False)
    noverlap = Column(Integer, nullable=False)
    sigma = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    min_distance_hz = Column(Float, nullable=False)
    n_harmonics = Column(Integer, nullable=False)
    f0_mode = Column(String, nullable=False)
    f0_hint_hz = Column(Float)
    tol_hz = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False)
    cable_id = Column(Integer, ForeignKey("cables.id"), nullable=False)
    f0_hz = Column(Float, nullable=False)
    harmonics_json = Column(JSON)
    k_used_value = Column(Float, nullable=False)
    k_used_calibration_id = Column(Integer, ForeignKey("k_calibrations.id"), nullable=False)
    tension_tf = Column(Float, nullable=False)
    df_hz = Column(Float)
    snr_metric = Column(Float)
    quality_flag = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    entity = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    performed_by = Column(Integer, ForeignKey("users.id"))
    performed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text)
