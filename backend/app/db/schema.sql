-- Schema for CeMPEI cable management and analysis (etapa 1)
-- Assumes PostgreSQL >= 13

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 0) Users / auth
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role TEXT NOT NULL CHECK (role IN ('admin', 'analyst', 'consulta', 'invitado')),
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4.1 Catalog
CREATE TABLE IF NOT EXISTS bridges (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    clave_interna TEXT,
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS strand_types (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    diametro_mm DOUBLE PRECISION NOT NULL CHECK (diametro_mm > 0),
    area_mm2 DOUBLE PRECISION NOT NULL CHECK (area_mm2 > 0),
    E_MPa DOUBLE PRECISION NOT NULL CHECK (E_MPa > 0),
    Fu_default DOUBLE PRECISION NOT NULL CHECK (Fu_default > 0),
    mu_por_toron_kg_m DOUBLE PRECISION NOT NULL CHECK (mu_por_toron_kg_m > 0),
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id),
    CONSTRAINT uq_strand_types_nombre UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS cables (
    id BIGSERIAL PRIMARY KEY,
    bridge_id BIGINT NOT NULL REFERENCES bridges(id) ON DELETE CASCADE,
    nombre_en_puente TEXT NOT NULL,
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id),
    CONSTRAINT uq_cable_nombre_por_puente UNIQUE (bridge_id, nombre_en_puente)
);

CREATE TABLE IF NOT EXISTS cable_state_versions (
    id BIGSERIAL PRIMARY KEY,
    cable_id BIGINT NOT NULL REFERENCES cables(id) ON DELETE CASCADE,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    length_effective_m DOUBLE PRECISION NOT NULL CHECK (length_effective_m > 0),
    length_total_m DOUBLE PRECISION CHECK (length_total_m > 0),
    strands_total INTEGER NOT NULL CHECK (strands_total > 0),
    strands_active INTEGER NOT NULL CHECK (strands_active > 0),
    strands_inactive INTEGER NOT NULL DEFAULT 0 CHECK (strands_inactive >= 0),
    strand_type_id BIGINT NOT NULL REFERENCES strand_types(id),
    diametro_mm DOUBLE PRECISION NOT NULL CHECK (diametro_mm > 0),
    area_mm2 DOUBLE PRECISION NOT NULL CHECK (area_mm2 > 0),
    E_MPa DOUBLE PRECISION NOT NULL CHECK (E_MPa > 0),
    mu_total_kg_m DOUBLE PRECISION NOT NULL CHECK (mu_total_kg_m > 0),
    mu_active_basis_kg_m DOUBLE PRECISION NOT NULL CHECK (mu_active_basis_kg_m > 0),
    design_tension_tf DOUBLE PRECISION NOT NULL CHECK (design_tension_tf > 0),
    Fu_override DOUBLE PRECISION,
    antivandalic_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    antivandalic_length_m DOUBLE PRECISION CHECK (antivandalic_length_m > 0),
    source TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id),
    CONSTRAINT chk_strands_active_total CHECK (strands_active <= strands_total),
    CONSTRAINT chk_valid_to_gt_from CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT chk_antivandalic_length_req CHECK (
        (antivandalic_enabled AND antivandalic_length_m IS NOT NULL) OR
        (NOT antivandalic_enabled)
    )
);

-- Una sola versión abierta por cable
CREATE UNIQUE INDEX IF NOT EXISTS uq_cable_version_open
ON cable_state_versions (cable_id)
WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS sensors (
    id BIGSERIAL PRIMARY KEY,
    sensor_type TEXT NOT NULL,
    serial_or_asset_id TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL,
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sensor_installations (
    id BIGSERIAL PRIMARY KEY,
    sensor_id BIGINT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    cable_id BIGINT NOT NULL REFERENCES cables(id) ON DELETE CASCADE,
    installed_from TIMESTAMPTZ NOT NULL,
    installed_to TIMESTAMPTZ,
    height_m DOUBLE PRECISION NOT NULL CHECK (height_m > 0),
    mounting_details TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id),
    CONSTRAINT chk_installed_to_gt_from CHECK (installed_to IS NULL OR installed_to > installed_from)
);

-- Evita solapamiento del mismo sensor en cables distintos
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE INDEX IF NOT EXISTS idx_sensor_installations_no_overlap
ON sensor_installations
USING GIST (
    sensor_id,
    tstzrange(installed_from, COALESCE(installed_to, 'infinity')) WITH &&);

-- 4.2 Acquisitions
CREATE TABLE IF NOT EXISTS acquisitions (
    id BIGSERIAL PRIMARY KEY,
    bridge_id BIGINT NOT NULL REFERENCES bridges(id) ON DELETE CASCADE,
    acquired_at TIMESTAMPTZ NOT NULL,
    operator_user_id BIGINT REFERENCES users(id),
    Fs_Hz DOUBLE PRECISION NOT NULL CHECK (Fs_Hz > 0),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS raw_files (
    id BIGSERIAL PRIMARY KEY,
    acquisition_id BIGINT NOT NULL REFERENCES acquisitions(id) ON DELETE CASCADE,
    file_kind TEXT NOT NULL CHECK (file_kind IN ('raw_csv', 'normalized_csv')),
    storage_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes > 0),
    parser_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_raw_files_sha UNIQUE (sha256)
);

CREATE TABLE IF NOT EXISTS acquisition_channels (
    id BIGSERIAL PRIMARY KEY,
    acquisition_id BIGINT NOT NULL REFERENCES acquisitions(id) ON DELETE CASCADE,
    csv_column_name TEXT NOT NULL,
    sensor_id BIGINT NOT NULL REFERENCES sensors(id),
    cable_id BIGINT NOT NULL REFERENCES cables(id),
    height_m DOUBLE PRECISION NOT NULL CHECK (height_m > 0),
    status_flag TEXT NOT NULL CHECK (status_flag IN ('ok','warning_no_installation','warning_mismatch_installation')),
    notes TEXT
);

-- 4.3 Pesajes directos y K
CREATE TABLE IF NOT EXISTS weighing_campaigns (
    id BIGSERIAL PRIMARY KEY,
    bridge_id BIGINT NOT NULL REFERENCES bridges(id) ON DELETE CASCADE,
    performed_at TIMESTAMPTZ NOT NULL,
    performed_by TEXT NOT NULL,
    method TEXT NOT NULL,
    equipment TEXT NOT NULL,
    temperature_C DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id BIGINT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS weighing_attachments (
    id BIGSERIAL PRIMARY KEY,
    weighing_campaign_id BIGINT NOT NULL REFERENCES weighing_campaigns(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 CHAR(64),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS weighing_measurements (
    id BIGSERIAL PRIMARY KEY,
    weighing_campaign_id BIGINT NOT NULL REFERENCES weighing_campaigns(id) ON DELETE CASCADE,
    cable_id BIGINT NOT NULL REFERENCES cables(id),
    measured_tension_tf DOUBLE PRECISION NOT NULL CHECK (measured_tension_tf > 0),
    measured_temperature_C DOUBLE PRECISION,
    notes TEXT
);

-- 4.4 Snapshots y K calibrations
CREATE TABLE IF NOT EXISTS cable_config_snapshots (
    id BIGSERIAL PRIMARY KEY,
    cable_id BIGINT NOT NULL REFERENCES cables(id),
    source_state_version_id BIGINT REFERENCES cable_state_versions(id),
    effective_length_m DOUBLE PRECISION NOT NULL CHECK (effective_length_m > 0),
    mu_basis TEXT NOT NULL CHECK (mu_basis IN ('active','total','custom')),
    mu_value_kg_m DOUBLE PRECISION NOT NULL CHECK (mu_value_kg_m > 0),
    strands_active INTEGER NOT NULL CHECK (strands_active > 0),
    strands_total INTEGER NOT NULL CHECK (strands_total > 0),
    strand_type_id BIGINT REFERENCES strand_types(id),
    notes TEXT,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_active_le_total CHECK (strands_active <= strands_total)
);

CREATE TABLE IF NOT EXISTS k_calibrations (
    id BIGSERIAL PRIMARY KEY,
    cable_id BIGINT NOT NULL REFERENCES cables(id),
    derived_from_weighing_measurement_id BIGINT NOT NULL REFERENCES weighing_measurements(id),
    config_snapshot_id BIGINT NOT NULL REFERENCES cable_config_snapshots(id),
    k_value DOUBLE PRECISION NOT NULL CHECK (k_value > 0),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    algorithm_version TEXT NOT NULL,
    computed_by_user_id BIGINT REFERENCES users(id),
    notes TEXT,
    CONSTRAINT chk_k_valid_to_gt_from CHECK (valid_to IS NULL OR valid_to > valid_from)
);

-- Evita traslapes de K por tirante
CREATE INDEX IF NOT EXISTS idx_k_calibrations_no_overlap
ON k_calibrations
USING GIST (
    cable_id,
    tstzrange(valid_from, COALESCE(valid_to, 'infinity')) WITH &&);

-- 5 Análisis
CREATE TABLE IF NOT EXISTS analysis_runs (
    id BIGSERIAL PRIMARY KEY,
    acquisition_id BIGINT NOT NULL REFERENCES acquisitions(id) ON DELETE CASCADE,
    created_by_user_id BIGINT REFERENCES users(id),
    algorithm_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS analysis_run_params (
    id BIGSERIAL PRIMARY KEY,
    analysis_run_id BIGINT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    cable_id BIGINT NOT NULL REFERENCES cables(id),
    segment_pct_start DOUBLE PRECISION NOT NULL CHECK (segment_pct_start >= 0 AND segment_pct_start < 100),
    segment_pct_end DOUBLE PRECISION NOT NULL CHECK (segment_pct_end > 0 AND segment_pct_end <= 100),
    nperseg INTEGER NOT NULL CHECK (nperseg > 0),
    noverlap INTEGER NOT NULL CHECK (noverlap >= 0),
    sigma DOUBLE PRECISION NOT NULL CHECK (sigma > 0),
    threshold DOUBLE PRECISION NOT NULL,
    min_distance_hz DOUBLE PRECISION NOT NULL CHECK (min_distance_hz > 0),
    n_harmonics INTEGER NOT NULL CHECK (n_harmonics > 0),
    f0_mode TEXT NOT NULL CHECK (f0_mode IN ('auto','hint')),
    f0_hint_hz DOUBLE PRECISION,
    tol_hz DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_segment_order CHECK (segment_pct_start < segment_pct_end),
    CONSTRAINT chk_overlap_less_than_nperseg CHECK (noverlap < nperseg)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id BIGSERIAL PRIMARY KEY,
    analysis_run_id BIGINT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    cable_id BIGINT NOT NULL REFERENCES cables(id),
    f0_hz DOUBLE PRECISION NOT NULL CHECK (f0_hz > 0),
    harmonics_json JSONB,
    k_used_value DOUBLE PRECISION NOT NULL CHECK (k_used_value > 0),
    k_used_calibration_id BIGINT NOT NULL REFERENCES k_calibrations(id),
    tension_tf DOUBLE PRECISION NOT NULL CHECK (tension_tf > 0),
    df_hz DOUBLE PRECISION,
    snr_metric DOUBLE PRECISION,
    quality_flag TEXT NOT NULL CHECK (quality_flag IN ('ok','doubtful','bad')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Helpers
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    entity TEXT NOT NULL,
    entity_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    performed_by BIGINT REFERENCES users(id),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);
