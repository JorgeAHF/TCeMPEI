from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str]
    role: str = "analyst"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    role: str
    created_at: datetime

    class Config:
        orm_mode = True


class BridgeCreate(BaseModel):
    nombre: str
    clave_interna: Optional[str] = None
    num_tirantes: Optional[int] = None
    notas: Optional[str] = None


class BridgeUpdate(BaseModel):
    nombre: Optional[str]
    clave_interna: Optional[str]
    num_tirantes: Optional[int]
    notas: Optional[str]


class BridgeOut(BaseModel):
    id: int
    nombre: str
    clave_interna: Optional[str]
    num_tirantes: Optional[int]
    notas: Optional[str]

    class Config:
        orm_mode = True


class StrandTypeCreate(BaseModel):
    nombre: str
    diametro_mm: float
    area_mm2: float
    E_MPa: float
    Fu_default: float
    mu_por_toron_kg_m: float
    notas: Optional[str]


class StrandTypeOut(StrandTypeCreate):
    id: int

    class Config:
        orm_mode = True


class StrandTypeUpdate(BaseModel):
    nombre: Optional[str]
    diametro_mm: Optional[float]
    area_mm2: Optional[float]
    E_MPa: Optional[float]
    Fu_default: Optional[float]
    mu_por_toron_kg_m: Optional[float]
    notas: Optional[str]


class CableCreate(BaseModel):
    bridge_id: int
    nombre_en_puente: str
    notas: Optional[str]


class CableOut(CableCreate):
    id: int

    class Config:
        orm_mode = True


class CableUpdate(BaseModel):
    nombre_en_puente: Optional[str] = None
    notas: Optional[str] = None


class AcquisitionCreate(BaseModel):
    bridge_id: int
    acquired_at: datetime
    operator_user_id: Optional[int]
    Fs_Hz: float
    notes: Optional[str]


class AcquisitionOut(AcquisitionCreate):
    id: int

    class Config:
        orm_mode = True


class WeighingCampaignCreate(BaseModel):
    bridge_id: int
    performed_at: datetime
    performed_by: str
    method: str
    equipment: str
    temperature_C: Optional[float] = None
    notes: Optional[str] = None


class WeighingCampaignOut(WeighingCampaignCreate):
    id: int

    class Config:
        orm_mode = True


class AnalysisRunCreate(BaseModel):
    acquisition_id: int
    created_by_user_id: Optional[int]
    algorithm_version: str
    notes: Optional[str]


class AnalysisRunOut(AnalysisRunCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class AnalysisResultCreate(BaseModel):
    analysis_run_id: int
    cable_id: int
    f0_hz: float
    harmonics_json: Optional[dict]
    df_hz: Optional[float]
    snr_metric: Optional[float]
    quality_flag: str = Field(..., regex="^(ok|doubtful|bad)$")


class AnalysisResultOut(AnalysisResultCreate):
    id: int
    k_used_value: float
    k_used_calibration_id: int
    tension_tf: float
    created_at: datetime

    class Config:
        orm_mode = True


class SemaforoItem(BaseModel):
    cable_id: int
    nombre_en_puente: str
    tension_tf: float
    fu: float
    pct_fu: float
    estado: str


class SemaforoResponse(BaseModel):
    bridge_id: int
    acquisition_id: int
    total: int
    exceden: int
    items: List[SemaforoItem]
    top_n: Optional[int] = None


class HistoryItem(BaseModel):
    cable_id: int
    nombre_en_puente: str
    acquired_at: datetime
    analysis_run_id: int
    f0_hz: float
    tension_tf: float
    k_used_value: float
    k_used_calibration_id: int
    quality_flag: str


class HistoryResponse(BaseModel):
    results: List[HistoryItem]
    k_calibrations: Optional[List[KCalibrationOut]] = None


class CableStateVersionCreate(BaseModel):
    cable_id: int
    valid_from: datetime
    valid_to: Optional[datetime]
    length_effective_m: float
    length_total_m: Optional[float] = None
    strands_total: int
    strands_active: int
    strands_inactive: Optional[int] = 0
    strand_type_id: int
    diametro_mm: float
    area_mm2: float
    E_MPa: float
    mu_total_kg_m: float
    mu_active_basis_kg_m: float
    design_tension_tf: float
    Fu_override: Optional[float]
    antivandalic_enabled: bool = False
    antivandalic_length_m: Optional[float]
    source: Optional[str]
    notes: Optional[str]


class CableStateVersionOut(CableStateVersionCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class SensorCreate(BaseModel):
    sensor_type: str
    serial_or_asset_id: str
    unit: str
    notas: Optional[str]


class SensorOut(SensorCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class SensorInstallationCreate(BaseModel):
    sensor_id: int
    cable_id: int
    installed_from: datetime
    installed_to: Optional[datetime]
    height_m: float
    mounting_details: Optional[str]
    notes: Optional[str]


class SensorInstallationOut(SensorInstallationCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class WeighingMeasurementCreate(BaseModel):
    weighing_campaign_id: int
    cable_id: int
    measured_tension_tf: float
    measured_temperature_C: Optional[float]
    notes: Optional[str]


class WeighingMeasurementOut(WeighingMeasurementCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class CableConfigSnapshotCreate(BaseModel):
    cable_id: int
    source_state_version_id: Optional[int]
    effective_length_m: float
    mu_basis: str
    mu_value_kg_m: float
    strands_active: int
    strands_total: int
    strand_type_id: Optional[int]
    notes: Optional[str]


class CableConfigSnapshotOut(CableConfigSnapshotCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class KCalibrationCreate(BaseModel):
    cable_id: int
    derived_from_weighing_measurement_id: int
    config_snapshot_id: int
    k_value: float
    valid_from: datetime
    valid_to: Optional[datetime]
    algorithm_version: str
    computed_by_user_id: Optional[int]
    notes: Optional[str]


class KCalibrationOut(KCalibrationCreate):
    id: int

    class Config:
        orm_mode = True
