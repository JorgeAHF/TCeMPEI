from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Acquisition, AcquisitionChannel, Cable, RawFile, SensorInstallation
from app.utils import save_upload


def _read_csv_after_data_start(content: bytes) -> pd.DataFrame:
    lines = content.decode("utf-8").splitlines()
    data_start_idx = None
    for idx, line in enumerate(lines):
        if "DATA_START" in line:
            data_start_idx = idx + 1
            break
    if data_start_idx is None:
        raise ValueError("No se encontró la etiqueta DATA_START en el CSV")
    headers = [h.strip() for h in lines[data_start_idx].split(",") if h.strip()]
    if not headers:
        raise ValueError("Encabezados vacíos después de DATA_START")
    data_lines = lines[data_start_idx + 1 :]
    df = pd.read_csv(io.StringIO("\n".join(data_lines)), names=headers)
    return df


def _status_for_installation(
    db: Session, sensor_id: int, cable_id: int, acquired_at: datetime
) -> str:
    installs: List[SensorInstallation] = (
        db.query(SensorInstallation)
        .filter(
            SensorInstallation.sensor_id == sensor_id,
            SensorInstallation.installed_from <= acquired_at,
            (SensorInstallation.installed_to.is_(None)) | (SensorInstallation.installed_to >= acquired_at),
        )
        .all()
    )
    if not installs:
        return "warning_no_installation"
    cables = {inst.cable_id for inst in installs}
    return "ok" if cable_id in cables else "warning_mismatch_installation"


def register_raw_file(
    db: Session, acq: Acquisition, parser_version: str, file_name: str, data_root: Path, content: bytes
) -> RawFile:
    path, digest = save_upload(data_root, "raw", file_name, content)
    record = RawFile(
        acquisition_id=acq.id,
        file_kind="raw_csv",
        storage_path=str(path),
        original_filename=file_name,
        sha256=digest,
        file_size_bytes=len(content),
        parser_version=parser_version,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def normalize_from_raw(
    db: Session,
    acq: Acquisition,
    mapping: Iterable[dict],
    data_root: Path,
    parser_version: str,
) -> Tuple[RawFile, List[AcquisitionChannel], str]:
    raw_record: RawFile | None = (
        db.query(RawFile)
        .filter(RawFile.acquisition_id == acq.id, RawFile.file_kind == "raw_csv")
        .order_by(RawFile.created_at.desc())
        .first()
    )
    if not raw_record:
        raise ValueError("No hay raw_csv registrado para esta adquisición")
    raw_bytes = Path(raw_record.storage_path).read_bytes()
    df = _read_csv_after_data_start(raw_bytes)

    rename_map = {}
    channel_rows: List[AcquisitionChannel] = []
    seen_cable_names = set()
    for item in mapping:
        col = item.get("csv_column_name")
        sensor_id = item.get("sensor_id")
        cable_id = item.get("cable_id")
        height_m = item.get("height_m")
        if height_m is None or height_m <= 0:
            raise ValueError("height_m debe ser > 0 en el mapeo")
        if col not in df.columns:
            raise ValueError(f"Columna {col} no existe en el CSV crudo")
        cable: Cable | None = db.get(Cable, cable_id)
        if not cable:
            raise ValueError(f"Cable {cable_id} no existe")
        cable_name = cable.nombre_en_puente
        if cable_name in seen_cable_names:
            raise ValueError(f"Tirante repetido en mapeo: {cable_name}")
        seen_cable_names.add(cable_name)
        rename_map[col] = cable_name
        status_flag = _status_for_installation(db, sensor_id, cable_id, acq.acquired_at)
        channel_rows.append(
            AcquisitionChannel(
                acquisition_id=acq.id,
                csv_column_name=col,
                sensor_id=sensor_id,
                cable_id=cable_id,
                height_m=height_m,
                status_flag=status_flag,
                notes=None,
            )
        )

    df_norm = df.copy()
    df_norm = df_norm.rename(columns=rename_map)
    cols_order = [df_norm.columns[0]] + sorted(seen_cable_names)
    df_norm = df_norm[cols_order]
    # Convertir a numérico salvo la primera columna (tiempo)
    for col in df_norm.columns[1:]:
        df_norm[col] = pd.to_numeric(df_norm[col], errors="coerce")
    # No se eliminan filas; NaN se preserva (policy conservadora)

    fname = f"normalized_{acq.bridge_id}_{acq.acquired_at.strftime('%Y%m%d_%H%M%S')}_acq{acq.id}.csv"
    path, digest = save_upload(data_root, "normalized", fname, df_norm.to_csv(index=False).encode("utf-8"))
    norm_record = RawFile(
        acquisition_id=acq.id,
        file_kind="normalized_csv",
        storage_path=str(path),
        original_filename=fname,
        sha256=digest,
        file_size_bytes=path.stat().st_size,
        parser_version=parser_version,
    )
    db.add(norm_record)
    for row in channel_rows:
        db.add(row)
    db.commit()
    db.refresh(norm_record)
    return norm_record, channel_rows, str(path)
