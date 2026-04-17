from __future__ import annotations

import io
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Acquisition, AcquisitionChannel, Cable, RawFile, Sensor, SensorInstallation
from app.utils import save_upload


class DuplicateRawFileInAcquisitionError(ValueError):
    def __init__(self, message: str, existing_file_id: int):
        super().__init__(message)
        self.existing_file_id = existing_file_id


def _decode_csv_lines(content: bytes) -> List[str]:
    return content.decode("utf-8-sig").splitlines()


def _extract_header_row(
    lines: List[str],
    data_start_marker: str = "DATA_START",
    header_row_override: int | None = None,
) -> tuple[List[str], int]:
    if not lines:
        raise ValueError("CSV vacío")

    if header_row_override is not None:
        if header_row_override < 0 or header_row_override >= len(lines):
            raise ValueError("header_row_override fuera de rango")
        header_row_idx = header_row_override
    else:
        marker_idx = None
        for idx, line in enumerate(lines):
            if data_start_marker in line:
                marker_idx = idx
                break
        if marker_idx is None:
            raise ValueError(
                f"No se encontró la etiqueta {data_start_marker} en el CSV. "
                "Proporciona header_row_override para seleccionar la cabecera manualmente."
            )
        header_row_idx = marker_idx + 1

    if header_row_idx >= len(lines):
        raise ValueError("No hay fila de cabeceras disponible")

    headers = [h.strip() for h in lines[header_row_idx].split(",") if h.strip()]
    if not headers:
        raise ValueError("Encabezados vacíos en la fila de cabecera")
    return headers, header_row_idx


def read_csv_with_detected_header(
    content: bytes,
    data_start_marker: str = "DATA_START",
    header_row_override: int | None = None,
) -> tuple[pd.DataFrame, List[str], int]:
    lines = _decode_csv_lines(content)
    headers, header_row_idx = _extract_header_row(
        lines=lines,
        data_start_marker=data_start_marker,
        header_row_override=header_row_override,
    )
    data_lines = lines[header_row_idx + 1 :]
    df = pd.read_csv(io.StringIO("\n".join(data_lines)), names=headers)
    return df, headers, header_row_idx


def build_raw_preview(
    content: bytes,
    data_start_marker: str = "DATA_START",
    header_row_override: int | None = None,
    max_lines: int = 20,
) -> dict:
    lines = _decode_csv_lines(content)
    _, headers, header_row_idx = read_csv_with_detected_header(
        content=content,
        data_start_marker=data_start_marker,
        header_row_override=header_row_override,
    )
    return {
        "header_row_index": header_row_idx,
        "headers": headers,
        "sample_lines": lines[:max_lines],
    }


async def get_next_file_version(db: AsyncSession, acquisition_id: int, file_kind: str) -> int:
    result = await db.execute(
        select(func.max(RawFile.version_no)).where(
            RawFile.acquisition_id == acquisition_id,
            RawFile.file_kind == file_kind,
        )
    )
    max_version = result.scalar()
    return (max_version or 0) + 1


async def _resolve_raw_file(db: AsyncSession, acq_id: int, raw_file_id: int | None) -> RawFile | None:
    q = select(RawFile).where(RawFile.acquisition_id == acq_id, RawFile.file_kind == "raw_csv")
    if raw_file_id is not None:
        return (await db.execute(q.where(RawFile.id == raw_file_id))).scalar_one_or_none()
    return (await db.execute(q.order_by(RawFile.version_no.desc(), RawFile.created_at.desc()))).scalars().first()


def _build_versioned_filename(acq_id: int, file_kind: str, version_no: int, original_filename: str) -> str:
    base = Path(original_filename or "upload.csv").name.replace(" ", "_")
    kind = "raw" if file_kind == "raw_csv" else "normalized"
    return f"acq{acq_id}_{kind}_v{version_no:04d}_{base}"


async def _status_for_installation(
    db: AsyncSession, sensor_id: int, cable_id: int, acquired_at: datetime
) -> str:
    stmt = select(SensorInstallation).where(
        SensorInstallation.sensor_id == sensor_id,
        SensorInstallation.installed_from <= acquired_at,
        (SensorInstallation.installed_to.is_(None)) | (SensorInstallation.installed_to >= acquired_at),
    )
    installs = (await db.execute(stmt)).scalars().all()
    if not installs:
        return "warning_no_installation"
    cables = {inst.cable_id for inst in installs}
    return "ok" if cable_id in cables else "warning_mismatch_installation"


async def register_raw_file(
    db: AsyncSession, acq: Acquisition, parser_version: str, file_name: str, data_root: Path, content: bytes
) -> tuple[RawFile, str | None]:
    digest = hashlib.sha256(content).hexdigest()
    duplicate_in_same_acq = (
        await db.execute(
            select(RawFile).where(
                RawFile.acquisition_id == acq.id,
                RawFile.file_kind == "raw_csv",
                RawFile.sha256 == digest,
            )
        )
    ).scalar_one_or_none()
    if duplicate_in_same_acq:
        raise DuplicateRawFileInAcquisitionError(
            "Archivo duplicado exacto en la misma campaña",
            existing_file_id=duplicate_in_same_acq.id,
        )

    duplicate_other = (
        await db.execute(
            select(RawFile).where(
                RawFile.file_kind == "raw_csv",
                RawFile.sha256 == digest,
                RawFile.acquisition_id != acq.id,
            )
        )
    ).scalar_one_or_none()
    warning = None
    if duplicate_other:
        warning = (
            "Se detectó el mismo archivo (sha256) en otra campaña "
            f"(acquisition_id={duplicate_other.acquisition_id}, raw_file_id={duplicate_other.id})."
        )

    version_no = await get_next_file_version(db, acq.id, "raw_csv")
    versioned_name = _build_versioned_filename(acq.id, "raw_csv", version_no, file_name)
    path, digest = save_upload(data_root, "raw", versioned_name, content)
    record = RawFile(
        acquisition_id=acq.id,
        file_kind="raw_csv",
        source_raw_file_id=None,
        version_no=version_no,
        storage_path=str(path),
        original_filename=file_name,
        sha256=digest,
        file_size_bytes=len(content),
        parser_version=parser_version,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record, warning


async def normalize_from_raw(
    db: AsyncSession,
    acq: Acquisition,
    mapping: Iterable[dict],
    data_root: Path,
    parser_version: str,
    raw_file_id: int | None = None,
    header_row_override: int | None = None,
    data_start_marker: str = "DATA_START",
) -> Tuple[RawFile, List[AcquisitionChannel], str]:
    raw_record = await _resolve_raw_file(db=db, acq_id=acq.id, raw_file_id=raw_file_id)
    if not raw_record:
        raise ValueError("No hay raw_csv registrado para esta adquisición")
    raw_bytes = Path(raw_record.storage_path).read_bytes()
    df, _, _ = read_csv_with_detected_header(
        content=raw_bytes,
        data_start_marker=data_start_marker,
        header_row_override=header_row_override,
    )

    mapping_items = list(mapping)
    if not mapping_items:
        raise ValueError("Debe proporcionar al menos un canal mapeado")

    rename_map = {}
    channel_rows: List[AcquisitionChannel] = []
    seen_columns = set()
    cable_assignments: dict[int, list[dict]] = {}
    normalized_labels: List[str] = []
    validated_rows: List[dict] = []
    for item in mapping_items:
        col = item.get("csv_column_name")
        sensor_id = item.get("sensor_id")
        cable_id = item.get("cable_id")
        height_m = item.get("height_m")
        multichannel_intentional = bool(item.get("multichannel_intentional", False))

        if not col:
            raise ValueError("Cada canal debe incluir csv_column_name")
        if col in seen_columns:
            raise ValueError(f"Columna duplicada en mapeo: {col}")
        seen_columns.add(col)

        if cable_id is None:
            raise ValueError(f"Canal sin tirante asignado: {col}")
        if sensor_id is None:
            raise ValueError(f"Canal sin sensor asignado: {col}")
        if height_m is None or height_m <= 0:
            raise ValueError("height_m debe ser > 0 en el mapeo")
        if col not in df.columns:
            raise ValueError(f"Columna {col} no existe en el CSV crudo")
        try:
            cable_id = int(cable_id)
        except (TypeError, ValueError):
            raise ValueError(f"cable_id inválido para columna {col}: {cable_id}")
        try:
            sensor_id = int(sensor_id)
        except (TypeError, ValueError):
            raise ValueError(f"sensor_id inválido para columna {col}: {sensor_id}")
        cable: Cable | None = await db.get(Cable, cable_id)
        if not cable:
            raise ValueError(f"Cable {cable_id} no existe")
        sensor: Sensor | None = await db.get(Sensor, sensor_id)
        if not sensor:
            raise ValueError(f"Sensor {sensor_id} no existe")
        cable_name = cable.nombre_en_puente
        entry = {
            "csv_column_name": col,
            "sensor_id": sensor_id,
            "cable_id": cable_id,
            "height_m": float(height_m),
            "multichannel_intentional": multichannel_intentional,
            "cable_name": cable_name,
        }
        validated_rows.append(entry)
        cable_assignments.setdefault(cable_id, []).append(entry)

    unintended_multi = []
    for cable_rows in cable_assignments.values():
        if len(cable_rows) <= 1:
            continue
        if not all(r["multichannel_intentional"] for r in cable_rows):
            unintended_multi.append(cable_rows[0]["cable_name"])
    if unintended_multi:
        repeated = ", ".join(sorted(set(unintended_multi)))
        raise ValueError(
            f"Tirante duplicado no intencional en mapeo: {repeated}. "
            "Marca multichannel_intentional=true en todos los canales del tirante."
        )

    for item in validated_rows:
        col = item["csv_column_name"]
        cable_id = item["cable_id"]
        sensor_id = item["sensor_id"]
        cable_name = item["cable_name"]
        if len(cable_assignments[cable_id]) > 1:
            target_col = f"{cable_name}__{col}"
        else:
            target_col = cable_name
        base = target_col
        seq = 2
        while target_col in rename_map.values():
            target_col = f"{base}__{seq}"
            seq += 1
        rename_map[col] = target_col
        normalized_labels.append(target_col)
        status_flag = await _status_for_installation(db, sensor_id, cable_id, acq.acquired_at)
        channel_rows.append(
            AcquisitionChannel(
                acquisition_id=acq.id,
                csv_column_name=col,
                sensor_id=sensor_id,
                cable_id=cable_id,
                height_m=item["height_m"],
                status_flag=status_flag,
                notes="multichannel_intentional" if item["multichannel_intentional"] else None,
            )
        )

    df_norm = df.copy()
    df_norm = df_norm.rename(columns=rename_map)
    cols_order = [df_norm.columns[0]] + list(dict.fromkeys(normalized_labels))
    df_norm = df_norm[cols_order]
    # Convertir a numérico salvo la primera columna (tiempo)
    for col in df_norm.columns[1:]:
        df_norm[col] = pd.to_numeric(df_norm[col], errors="coerce")
    # No se eliminan filas; NaN se preserva (policy conservadora)

    version_no = await get_next_file_version(db, acq.id, "normalized_csv")
    fname = _build_versioned_filename(
        acq.id,
        "normalized_csv",
        version_no,
        f"from_raw_{raw_record.id}.csv",
    )
    path, digest = save_upload(data_root, "normalized", fname, df_norm.to_csv(index=False).encode("utf-8"))
    norm_record = RawFile(
        acquisition_id=acq.id,
        file_kind="normalized_csv",
        source_raw_file_id=raw_record.id,
        version_no=version_no,
        storage_path=str(path),
        original_filename=fname,
        sha256=digest,
        file_size_bytes=path.stat().st_size,
        parser_version=parser_version,
    )
    db.add(norm_record)
    for row in channel_rows:
        db.add(row)
    await db.commit()
    await db.refresh(norm_record)
    return norm_record, channel_rows, str(path)
