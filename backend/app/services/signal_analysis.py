from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, welch
from sqlalchemy.orm import Session

from app.models import Acquisition, Cable, RawFile


def _downsample(x: np.ndarray, y: np.ndarray, max_points: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    if len(x) <= max_points:
        return x, y
    step = max(1, int(np.ceil(len(x) / max_points)))
    return x[::step], y[::step]


def _normalized_file_for_acquisition(db: Session, acquisition_id: int, normalized_file_id: int | None) -> RawFile | None:
    q = db.query(RawFile).filter(RawFile.acquisition_id == acquisition_id, RawFile.file_kind == "normalized_csv")
    if normalized_file_id is not None:
        return q.filter(RawFile.id == normalized_file_id).first()
    return q.order_by(RawFile.version_no.desc(), RawFile.created_at.desc()).first()


def _resolve_channel_column(df: pd.DataFrame, cable_name: str, csv_column_name: str | None) -> str:
    if csv_column_name:
        # Prefer explicit normalized column, then cable-prefixed multichannel form.
        if csv_column_name in df.columns:
            return csv_column_name
        candidate = f"{cable_name}__{csv_column_name}"
        if candidate in df.columns:
            return candidate
        raise ValueError(f"No existe la columna solicitada para análisis: {csv_column_name}")

    if cable_name in df.columns:
        return cable_name
    prefixed = [c for c in df.columns if c.startswith(f"{cable_name}__")]
    if not prefixed:
        raise ValueError(f"No hay canales normalizados para tirante {cable_name}")
    return sorted(prefixed)[0]


def _time_axis(df: pd.DataFrame, fs_hz: float) -> np.ndarray:
    first_col = df.columns[0]
    t_raw = pd.to_numeric(df[first_col], errors="coerce")
    if t_raw.notna().mean() > 0.9:
        t = t_raw.to_numpy(dtype=float)
        if len(t) > 1 and np.all(np.diff(t[np.isfinite(t)]) >= 0):
            return t
    n = len(df)
    return np.arange(n, dtype=float) / fs_hz


def _compute_fft(x: np.ndarray, fs_hz: float) -> tuple[np.ndarray, np.ndarray]:
    n = len(x)
    if n < 4:
        raise ValueError("Segmento demasiado corto para FFT")
    x0 = x - float(np.nanmean(x))
    y = np.fft.rfft(x0)
    freq = np.fft.rfftfreq(n, d=1.0 / fs_hz)
    amp = np.abs(y) * (2.0 / n)
    return freq, amp


def _compute_psd(x: np.ndarray, fs_hz: float, nperseg: int, noverlap_pct: float) -> tuple[np.ndarray, np.ndarray]:
    n = len(x)
    if n < 8:
        raise ValueError("Segmento demasiado corto para PSD")
    nseg = max(8, min(int(nperseg), n))
    noverlap = int(nseg * (noverlap_pct / 100.0))
    noverlap = min(max(0, noverlap), nseg - 1)
    f, pxx = welch(x - float(np.nanmean(x)), fs=fs_hz, nperseg=nseg, noverlap=noverlap)
    return f, pxx


def _select_f0(
    freq_fft: np.ndarray,
    amp_fft: np.ndarray,
    peak_threshold: float,
    min_distance_hz: float,
    f0_hint_hz: float | None,
    f0_manual_hz: float | None,
) -> tuple[float, float, list[dict[str, float]]]:
    if len(freq_fft) < 3:
        raise ValueError("FFT insuficiente para detectar picos")

    mask_positive = freq_fft > 0
    f = freq_fft[mask_positive]
    a = amp_fft[mask_positive]
    if len(f) < 3:
        raise ValueError("No hay componentes de frecuencia positivas suficientes")

    amax = float(np.max(a)) if len(a) else 0.0
    min_height = max(0.0, float(peak_threshold)) * amax
    df_hz = float(np.median(np.diff(f))) if len(f) > 1 else 0.0
    distance_bins = max(1, int(round(min_distance_hz / df_hz))) if df_hz > 0 else 1

    peaks_idx, props = find_peaks(a, height=min_height, distance=distance_bins)
    candidate_peaks: list[dict[str, float]] = []
    for idx in peaks_idx:
        candidate_peaks.append({"frequency_hz": float(f[idx]), "amplitude": float(a[idx])})
    candidate_peaks.sort(key=lambda x: x["amplitude"], reverse=True)

    if candidate_peaks:
        if f0_hint_hz is not None:
            suggested = min(candidate_peaks, key=lambda p: abs(p["frequency_hz"] - f0_hint_hz))["frequency_hz"]
        else:
            suggested = candidate_peaks[0]["frequency_hz"]
    else:
        nonzero_idx = int(np.argmax(a))
        suggested = float(f[nonzero_idx])

    selected = float(f0_manual_hz) if f0_manual_hz is not None else float(suggested)
    return float(suggested), selected, candidate_peaks[:10]


def build_analysis_preview(
    db: Session,
    run_id: int,
    acquisition: Acquisition,
    cable: Cable,
    *,
    csv_column_name: str | None,
    normalized_file_id: int | None,
    segment_pct_start: float,
    segment_pct_end: float,
    nperseg: int,
    noverlap_pct: float,
    peak_threshold: float,
    min_distance_hz: float,
    n_harmonics: int,
    f0_hint_hz: float | None,
    f0_manual_hz: float | None,
) -> dict[str, Any]:
    if segment_pct_end <= segment_pct_start:
        raise ValueError("segment_pct_end debe ser mayor que segment_pct_start")

    fs_hz = float(acquisition.Fs_Hz)
    if fs_hz <= 0:
        raise ValueError("Fs_Hz inválida para la adquisición")

    normalized_file = _normalized_file_for_acquisition(db, acquisition.id, normalized_file_id)
    if not normalized_file:
        raise ValueError("No existe archivo normalized_csv para esta adquisición")

    df = pd.read_csv(Path(normalized_file.storage_path))
    if len(df.columns) < 2:
        raise ValueError("El archivo normalizado no contiene canales suficientes")

    channel_col = _resolve_channel_column(df, cable.nombre_en_puente, csv_column_name)

    time_s = _time_axis(df, fs_hz)
    signal_raw = pd.to_numeric(df[channel_col], errors="coerce").to_numpy(dtype=float)

    valid_mask = np.isfinite(time_s) & np.isfinite(signal_raw)
    time_s = time_s[valid_mask]
    signal = signal_raw[valid_mask]
    if len(signal) < 16:
        raise ValueError("Serie insuficiente para análisis")

    n = len(signal)
    start_idx = int(np.floor((segment_pct_start / 100.0) * n))
    end_idx = int(np.ceil((segment_pct_end / 100.0) * n))
    start_idx = min(max(0, start_idx), n - 1)
    end_idx = min(max(start_idx + 1, end_idx), n)

    t_seg = time_s[start_idx:end_idx]
    x_seg = signal[start_idx:end_idx]
    if len(x_seg) < 16:
        raise ValueError("Segmento seleccionado demasiado corto")

    f_fft, a_fft = _compute_fft(x_seg, fs_hz)
    f_psd, p_psd = _compute_psd(x_seg, fs_hz, nperseg=nperseg, noverlap_pct=noverlap_pct)
    f0_suggested, f0_selected, candidate_peaks = _select_f0(
        freq_fft=f_fft,
        amp_fft=a_fft,
        peak_threshold=peak_threshold,
        min_distance_hz=min_distance_hz,
        f0_hint_hz=f0_hint_hz,
        f0_manual_hz=f0_manual_hz,
    )

    harmonics: list[dict[str, float | int]] = []
    for h in range(1, n_harmonics + 1):
        target = h * f0_selected
        idx = int(np.argmin(np.abs(f_fft - target)))
        harmonics.append(
            {
                "order": h,
                "target_frequency_hz": float(target),
                "frequency_hz": float(f_fft[idx]),
                "amplitude": float(a_fft[idx]),
            }
        )

    noise_floor = float(np.median(a_fft[f_fft > 0])) if np.any(f_fft > 0) else 1e-12
    signal_peak = max((p["amplitude"] for p in candidate_peaks), default=float(np.max(a_fft)))
    snr_metric = float(signal_peak / max(noise_floor, 1e-12))

    t_full_ds, x_full_ds = _downsample(time_s, signal)
    t_seg_ds, x_seg_ds = _downsample(t_seg, x_seg)
    f_fft_ds, a_fft_ds = _downsample(f_fft, a_fft)
    f_psd_ds, p_psd_ds = _downsample(f_psd, p_psd)

    return {
        "run_id": run_id,
        "acquisition_id": acquisition.id,
        "cable_id": cable.id,
        "channel_name": channel_col,
        "normalized_file_id": normalized_file.id,
        "segment_pct_start": float(segment_pct_start),
        "segment_pct_end": float(segment_pct_end),
        "segment_samples": int(len(x_seg)),
        "fs_hz": fs_hz,
        "df_hz": float(np.median(np.diff(f_fft))) if len(f_fft) > 1 else 0.0,
        "f0_suggested_hz": float(f0_suggested),
        "f0_selected_hz": float(f0_selected),
        "snr_metric": snr_metric,
        "candidate_peaks": candidate_peaks,
        "harmonics": harmonics,
        "signal_full": {
            "time_s": [float(v) for v in t_full_ds],
            "accel": [float(v) for v in x_full_ds],
        },
        "signal_segment": {
            "time_s": [float(v) for v in t_seg_ds],
            "accel": [float(v) for v in x_seg_ds],
        },
        "fft": {
            "freq_hz": [float(v) for v in f_fft_ds],
            "amplitude": [float(v) for v in a_fft_ds],
        },
        "psd": {
            "freq_hz": [float(v) for v in f_psd_ds],
            "power": [float(v) for v in p_psd_ds],
        },
    }
