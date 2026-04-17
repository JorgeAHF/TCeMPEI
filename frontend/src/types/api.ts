export type Role = 'admin' | 'analyst' | 'reviewer' | 'viewer'

export interface User {
  id: number
  username: string
  full_name?: string
  role: Role
  created_at: string
}

export interface AuthLoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  access_expires_in_minutes: number
  refresh_expires_in_minutes: number
  user: User
}

export interface Bridge {
  id: number
  nombre: string
  clave_interna?: string
  num_tirantes?: number
  notas?: string
}

export interface Cable {
  id: number
  bridge_id: number
  nombre_en_puente: string
  notas?: string
}

export interface CableStateVersion {
  id: number
  cable_id: number
  valid_from: string
  valid_to?: string
  length_effective_m: number
  length_total_m?: number
  strands_total: number
  strands_active: number
  strands_inactive?: number
  strand_type_id: number
  diametro_mm: number
  area_mm2: number
  E_MPa: number
  mu_total_kg_m: number
  mu_active_basis_kg_m: number
  design_tension_tf: number
  Fu_override?: number
  antivandalic_enabled: boolean
  antivandalic_length_m?: number
  source?: string
  notes?: string
  created_at: string
}

export interface StrandType {
  id: number
  nombre: string
  diametro_mm: number
  area_mm2: number
  E_MPa: number
  Fu_default: number
  mu_por_toron_kg_m: number
  notas?: string
}

export interface Sensor {
  id: number
  sensor_type: string
  serial_or_asset_id: string
  unit: string
  notas?: string
  created_at: string
}

export interface Acquisition {
  id: number
  bridge_id: number
  acquired_at: string
  operator_user_id?: number
  Fs_Hz: number
  notes?: string
}

export interface AnalysisRun {
  id: number
  acquisition_id: number
  algorithm_version: string
  notes?: string
  created_at: string
}

export interface AnalysisResult {
  id: number
  analysis_run_id: number
  cable_id: number
  f0_hz: number
  tension_tf: number
  k_used_value: number
  quality_flag: string
  is_approved: boolean
  approved_by_user_id?: number
  approved_at?: string
  created_at: string
}

export interface AnomalyItem {
  analysis_result_id: number
  cable_id: number
  nombre_en_puente: string
  acquired_at: string
  f0_hz: number
  tension_tf: number
  quality_flag: string
  is_approved: boolean
  zscore_tension: number
  zscore_f0: number
  is_anomaly: boolean
  anomaly_reason?: string
}

export interface AnomaliesResponse {
  cable_id: number
  n_results: number
  n_anomalies: number
  z_threshold: number
  items: AnomalyItem[]
}

export interface AnalysisPeak {
  frequency_hz: number
  amplitude: number
}

export interface AnalysisHarmonic {
  order: number
  target_frequency_hz: number
  frequency_hz: number
  amplitude: number
}

export interface AnalysisPreviewResponse {
  run_id: number
  acquisition_id: number
  cable_id: number
  channel_name: string
  normalized_file_id: number
  segment_pct_start: number
  segment_pct_end: number
  segment_samples: number
  fs_hz: number
  df_hz: number
  f0_suggested_hz: number
  f0_selected_hz: number
  snr_metric: number
  candidate_peaks: AnalysisPeak[]
  harmonics: AnalysisHarmonic[]
  signal_full: { time_s: number[]; accel: number[] }
  signal_segment: { time_s: number[]; accel: number[] }
  fft: { freq_hz: number[]; amplitude: number[] }
  psd: { freq_hz: number[]; power: number[] }
}

export interface SemaforoItem {
  cable_id: number
  nombre_en_puente: string
  tension_tf: number
  fu: number
  pct_fu: number
  estado: string
}

export interface SemaforoResponse {
  bridge_id: number
  acquisition_id: number
  total: number
  exceden: number
  items: SemaforoItem[]
  top_n?: number
}

export interface HistoryItem {
  cable_id: number
  nombre_en_puente: string
  acquired_at: string
  analysis_run_id: number
  f0_hz: number
  tension_tf: number
  k_used_value: number
  k_used_calibration_id: number
  quality_flag: string
}

export interface HistoryResponse {
  results: HistoryItem[]
  k_calibrations?: KCalibration[]
}

export interface WeighingCampaign {
  id: number
  bridge_id: number
  performed_at: string
  performed_by: string
  method: string
  equipment: string
  temperature_C?: number
  notes?: string
}

export interface WeighingMeasurement {
  id: number
  weighing_campaign_id: number
  cable_id: number
  measured_tension_tf: number
  measured_temperature_C?: number
  notes?: string
  created_at: string
}

export interface CableConfigSnapshot {
  id: number
  cable_id: number
  source_state_version_id?: number
  effective_length_m: number
  mu_basis: string
  mu_value_kg_m: number
  strands_active: number
  strands_total: number
  strand_type_id?: number
  notes?: string
  created_at: string
}

export interface KCalibration {
  id: number
  cable_id: number
  derived_from_weighing_measurement_id: number
  config_snapshot_id: number
  k_value: number
  valid_from: string
  valid_to?: string
  algorithm_version: string
  computed_by_user_id?: number
  notes?: string
}

export interface RawPreviewResponse {
  raw_file_id: number
  version_no: number
  original_filename: string
  header_row_index?: number
  headers: string[]
  preview_lines?: string[]
}
