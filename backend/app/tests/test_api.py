import os
import shutil
from datetime import datetime, timezone
from math import pi, sin
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"
os.environ["APP_ENV"] = "test"
os.environ["ALLOW_SQLITE_FOR_TESTS"] = "true"
os.environ["DATA_ROOT"] = "./test_data"

from app.db import Base, SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    CableConfigSnapshot,
    CableStateVersion,
    KCalibration,
    User,
    WeighingCampaign,
    WeighingMeasurement,
)
from app.security import hash_password  # noqa: E402


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clean_db():
    shutil.rmtree(Path(os.environ["DATA_ROOT"]), ignore_errors=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = User(
            username="admin",
            full_name="Admin",
            role="admin",
            password_hash=hash_password("secret123"),
        )
        db.add(admin)
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def _login_auth():
    login_resp = client.post(
        "/auth/token",
        data={"username": "admin", "password": "secret123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


def _bootstrap_ingestion_context(auth: dict, user_id: int, bridge_name: str):
    bridge_id = client.post("/bridges", json={"nombre": bridge_name, "clave_interna": bridge_name[:6]}, headers=auth).json()["id"]
    cable_id = client.post("/cables", json={"bridge_id": bridge_id, "nombre_en_puente": "C1"}, headers=auth).json()["id"]
    sensor_id = client.post(
        "/sensors",
        json={"sensor_type": "acc", "serial_or_asset_id": f"S-{bridge_name}", "unit": "g", "notas": ""},
        headers=auth,
    ).json()["id"]
    acq_id = client.post(
        "/acquisitions",
        json={
            "bridge_id": bridge_id,
            "acquired_at": "2024-01-03T00:00:00Z",
            "operator_user_id": user_id,
            "Fs_Hz": 128.0,
            "notes": "",
        },
        headers=auth,
    ).json()["id"]
    return bridge_id, cable_id, sensor_id, acq_id


def test_full_flow_semáforo_alerta():
    # 1) Login
    auth, user_id = _login_auth()

    # 2) Strand type, bridge, cable
    st_resp = client.post(
        "/strand-types",
        json={
            "nombre": "7-0.6",
            "diametro_mm": 15.0,
            "area_mm2": 140.0,
            "E_MPa": 195000,
            "Fu_default": 120.0,
            "mu_por_toron_kg_m": 12.0,
            "notas": "",
        },
        headers=auth,
    )
    assert st_resp.status_code == 200
    st_id = st_resp.json()["id"]

    bridge_id = client.post("/bridges", json={"nombre": "Puente 1", "clave_interna": "P1"}, headers=auth).json()["id"]
    cable_id = client.post("/cables", json={"bridge_id": bridge_id, "nombre_en_puente": "C1"}, headers=auth).json()["id"]

    # 3) Cable state version, weighing, K (direct DB for now)
    kc_id = None
    with SessionLocal() as db:
        state = CableStateVersion(
            cable_id=cable_id,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            valid_to=None,
            length_effective_m=100.0,
            length_total_m=100.0,
            strands_total=7,
            strands_active=7,
            strands_inactive=0,
            strand_type_id=st_id,
            diametro_mm=15.0,
            area_mm2=140.0,
            E_MPa=195000,
            mu_total_kg_m=12.0,
            mu_active_basis_kg_m=12.0,
            design_tension_tf=80.0,
            Fu_override=110.0,
            antivandalic_enabled=False,
        )
        db.add(state)
        db.flush()

        wc = WeighingCampaign(
            bridge_id=bridge_id,
            performed_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            performed_by="team",
            method="jack",
            equipment="jack-01",
            temperature_C=20.0,
        )
        db.add(wc)
        db.flush()
        meas = WeighingMeasurement(
            weighing_campaign_id=wc.id, cable_id=cable_id, measured_tension_tf=50.0, measured_temperature_C=20.0
        )
        db.add(meas)
        db.flush()
        snap = CableConfigSnapshot(
            cable_id=cable_id,
            source_state_version_id=state.id,
            effective_length_m=100.0,
            mu_basis="active",
            mu_value_kg_m=12.0,
            strands_active=7,
            strands_total=7,
            strand_type_id=st_id,
        )
        db.add(snap)
        db.flush()
        kc = KCalibration(
            cable_id=cable_id,
            derived_from_weighing_measurement_id=meas.id,
            config_snapshot_id=snap.id,
            k_value=1.5,
            valid_from=datetime(2024, 1, 2, tzinfo=timezone.utc),
            valid_to=None,
            algorithm_version="v1.0",
            computed_by_user_id=user_id,
        )
        db.add(kc)
        db.commit()
        kc_id = kc.id

    # 4) Acquisition + analysis run + result
    acq_id = client.post(
        "/acquisitions",
        json={
            "bridge_id": bridge_id,
            "acquired_at": "2024-01-03T00:00:00Z",
            "operator_user_id": user_id,
            "Fs_Hz": 128.0,
            "notes": "",
        },
        headers=auth,
    ).json()["id"]

    run_id = client.post(
        "/analysis-runs",
        json={"acquisition_id": acq_id, "created_by_user_id": user_id, "algorithm_version": "v1.0", "notes": ""},
        headers=auth,
    ).json()["id"]

    # Tensión 60 tf, Fu 110 -> 54.5% => ALERTA
    res_resp = client.post(
        "/analysis-results",
        json={
            "analysis_run_id": run_id,
            "cable_id": cable_id,
            "f0_hz": 6.324555320336759,
            "harmonics_json": {},
            "k_used_value": 15.0,
            "k_used_calibration_id": kc_id,
            "tension_tf": 60.0,
            "df_hz": 0.1,
            "snr_metric": 10.0,
            "quality_flag": "ok",
        },
        headers=auth,
    )
    assert res_resp.status_code == 200

    sem = client.get(f"/bridges/{bridge_id}/semaforo", params={"acquisition_id": acq_id})
    data = sem.json()
    assert data["total"] == 1
    assert data["exceden"] == 1
    assert data["items"][0]["estado"] == "ALERTA"


def test_raw_upload_blocks_exact_duplicate_in_same_campaign():
    auth, user_id = _login_auth()
    _, _, _, acq_id = _bootstrap_ingestion_context(auth, user_id, "Puente Dup Mismo")

    raw_csv = b"meta\nDATA_START\ntime,ch1\n0,0.1\n1,0.2\n"
    files = {"file": ("raw.csv", raw_csv, "text/csv")}
    first = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files=files,
        headers=auth,
    )
    assert first.status_code == 200
    assert first.json()["version_no"] == 1

    second = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files=files,
        headers=auth,
    )
    assert second.status_code == 409
    assert "duplicado exacto" in second.json()["detail"].lower()


def test_raw_upload_warns_duplicate_in_other_campaign():
    auth, user_id = _login_auth()
    bridge_id, _, _, acq1_id = _bootstrap_ingestion_context(auth, user_id, "Puente Dup Otro A")
    acq2_id = client.post(
        "/acquisitions",
        json={
            "bridge_id": bridge_id,
            "acquired_at": "2024-01-04T00:00:00Z",
            "operator_user_id": user_id,
            "Fs_Hz": 128.0,
            "notes": "",
        },
        headers=auth,
    ).json()["id"]

    raw_csv = b"meta\nDATA_START\ntime,ch1\n0,0.1\n1,0.2\n"
    files = {"file": ("raw.csv", raw_csv, "text/csv")}
    first = client.post(
        f"/acquisitions/{acq1_id}/raw-upload",
        params={"parser_version": "v1"},
        files=files,
        headers=auth,
    )
    assert first.status_code == 200
    assert first.json()["warning"] is None

    second = client.post(
        f"/acquisitions/{acq2_id}/raw-upload",
        params={"parser_version": "v1"},
        files=files,
        headers=auth,
    )
    assert second.status_code == 200
    assert "otra campaña" in (second.json()["warning"] or "").lower()


def test_normalize_supports_manual_header_override():
    auth, user_id = _login_auth()
    _, cable_id, sensor_id, acq_id = _bootstrap_ingestion_context(auth, user_id, "Puente Manual Header")

    raw_csv_without_marker = b"metadata line\ntime,ch1\n0,0.1\n1,0.2\n"
    up = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files={"file": ("raw_no_marker.csv", raw_csv_without_marker, "text/csv")},
        headers=auth,
    )
    assert up.status_code == 200
    raw_file_id = up.json()["id"]

    preview_fail = client.get(
        f"/acquisitions/{acq_id}/raw-preview",
        params={"raw_file_id": raw_file_id},
        headers=auth,
    )
    assert preview_fail.status_code == 400
    assert "header_row_override" in preview_fail.json()["detail"]

    preview_ok = client.get(
        f"/acquisitions/{acq_id}/raw-preview",
        params={"raw_file_id": raw_file_id, "header_row_override": 1},
        headers=auth,
    )
    assert preview_ok.status_code == 200
    assert preview_ok.json()["headers"] == ["time", "ch1"]

    mapping = [{"csv_column_name": "ch1", "sensor_id": sensor_id, "cable_id": cable_id, "height_m": 1.5}]
    norm_fail = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id},
        json=mapping,
        headers=auth,
    )
    assert norm_fail.status_code == 400
    assert "header_row_override" in norm_fail.json()["detail"]

    norm_ok = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id, "header_row_override": 1},
        json=mapping,
        headers=auth,
    )
    assert norm_ok.status_code == 200
    assert norm_ok.json()["raw_file_id"] == raw_file_id
    assert norm_ok.json()["version_no"] == 1


def test_normalize_blocks_channel_without_cable():
    auth, user_id = _login_auth()
    _, _, sensor_id, acq_id = _bootstrap_ingestion_context(auth, user_id, "Puente Sin Cable")

    raw_csv = b"meta\nDATA_START\ntime,ch1\n0,0.1\n1,0.2\n"
    up = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files={"file": ("raw.csv", raw_csv, "text/csv")},
        headers=auth,
    )
    assert up.status_code == 200
    raw_file_id = up.json()["id"]

    bad_mapping = [{"csv_column_name": "ch1", "sensor_id": sensor_id, "cable_id": None, "height_m": 1.0}]
    norm = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id},
        json=bad_mapping,
        headers=auth,
    )
    assert norm.status_code == 400
    assert "sin tirante asignado" in norm.json()["detail"].lower()


def test_normalize_blocks_unintended_multichannel_duplicate():
    auth, user_id = _login_auth()
    _, cable_id, sensor_id, acq_id = _bootstrap_ingestion_context(auth, user_id, "Puente Multi Canal")

    sensor2_id = client.post(
        "/sensors",
        json={"sensor_type": "acc", "serial_or_asset_id": "S-Puente-Multi-2", "unit": "g", "notas": ""},
        headers=auth,
    ).json()["id"]

    raw_csv = b"meta\nDATA_START\ntime,ch1,ch2\n0,0.1,0.2\n1,0.2,0.3\n"
    up = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files={"file": ("raw_multi.csv", raw_csv, "text/csv")},
        headers=auth,
    )
    assert up.status_code == 200
    raw_file_id = up.json()["id"]

    duplicate_mapping = [
        {"csv_column_name": "ch1", "sensor_id": sensor_id, "cable_id": cable_id, "height_m": 1.0},
        {"csv_column_name": "ch2", "sensor_id": sensor2_id, "cable_id": cable_id, "height_m": 1.1},
    ]
    norm_bad = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id},
        json=duplicate_mapping,
        headers=auth,
    )
    assert norm_bad.status_code == 400
    assert "duplicado no intencional" in norm_bad.json()["detail"].lower()

    intended_mapping = [
        {
            "csv_column_name": "ch1",
            "sensor_id": sensor_id,
            "cable_id": cable_id,
            "height_m": 1.0,
            "multichannel_intentional": True,
        },
        {
            "csv_column_name": "ch2",
            "sensor_id": sensor2_id,
            "cable_id": cable_id,
            "height_m": 1.1,
            "multichannel_intentional": True,
        },
    ]
    norm_ok = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id},
        json=intended_mapping,
        headers=auth,
    )
    assert norm_ok.status_code == 200
    assert norm_ok.json()["channels_created"] == 2


def test_analysis_preview_returns_spectra_and_f0_suggestion():
    auth, user_id = _login_auth()
    bridge_id, cable_id, sensor_id, acq_id = _bootstrap_ingestion_context(auth, user_id, "Puente Preview FFT")

    fs = 128.0
    n = 1024
    f0_true = 3.0
    rows = ["meta", "DATA_START", "time,ch1"]
    for i in range(n):
        t = i / fs
        x = sin(2 * pi * f0_true * t)
        rows.append(f"{t:.6f},{x:.9f}")
    raw_csv = ("\n".join(rows) + "\n").encode("utf-8")

    up = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files={"file": ("raw_fft.csv", raw_csv, "text/csv")},
        headers=auth,
    )
    assert up.status_code == 200
    raw_file_id = up.json()["id"]

    mapping = [{"csv_column_name": "ch1", "sensor_id": sensor_id, "cable_id": cable_id, "height_m": 1.5}]
    norm = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id},
        json=mapping,
        headers=auth,
    )
    assert norm.status_code == 200

    run_id = client.post(
        "/analysis-runs",
        json={"acquisition_id": acq_id, "created_by_user_id": user_id, "algorithm_version": "v1.0", "notes": ""},
        headers=auth,
    ).json()["id"]

    preview = client.post(
        f"/analysis-runs/{run_id}/preview",
        json={
            "cable_id": cable_id,
            "segment_pct_start": 0,
            "segment_pct_end": 100,
            "nperseg": 1024,
            "noverlap_pct": 50,
            "peak_threshold": 0.2,
            "min_distance_hz": 0.2,
            "n_harmonics": 3,
        },
        headers=auth,
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["channel_name"].startswith("C1")
    assert abs(data["f0_suggested_hz"] - f0_true) < 0.4
    assert abs(data["f0_selected_hz"] - data["f0_suggested_hz"]) < 1e-6
    assert len(data["fft"]["freq_hz"]) > 10
    assert len(data["psd"]["freq_hz"]) > 10


def test_analysis_preview_allows_manual_f0_selection():
    auth, user_id = _login_auth()
    _, cable_id, sensor_id, acq_id = _bootstrap_ingestion_context(auth, user_id, "Puente Preview Manual")

    fs = 128.0
    n = 512
    rows = ["meta", "DATA_START", "time,ch1"]
    for i in range(n):
        t = i / fs
        x = sin(2 * pi * 2.5 * t)
        rows.append(f"{t:.6f},{x:.9f}")
    raw_csv = ("\n".join(rows) + "\n").encode("utf-8")

    up = client.post(
        f"/acquisitions/{acq_id}/raw-upload",
        params={"parser_version": "v1"},
        files={"file": ("raw_manual.csv", raw_csv, "text/csv")},
        headers=auth,
    )
    raw_file_id = up.json()["id"]
    mapping = [{"csv_column_name": "ch1", "sensor_id": sensor_id, "cable_id": cable_id, "height_m": 1.3}]
    norm = client.post(
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": "v1", "raw_file_id": raw_file_id},
        json=mapping,
        headers=auth,
    )
    assert norm.status_code == 200

    run_id = client.post(
        "/analysis-runs",
        json={"acquisition_id": acq_id, "created_by_user_id": user_id, "algorithm_version": "v1.0", "notes": ""},
        headers=auth,
    ).json()["id"]

    manual_f0 = 4.75
    preview = client.post(
        f"/analysis-runs/{run_id}/preview",
        json={
            "cable_id": cable_id,
            "segment_pct_start": 0,
            "segment_pct_end": 100,
            "nperseg": 512,
            "noverlap_pct": 50,
            "peak_threshold": 0.2,
            "min_distance_hz": 0.2,
            "n_harmonics": 3,
            "f0_manual_hz": manual_f0,
        },
        headers=auth,
    )
    assert preview.status_code == 200
    data = preview.json()
    assert abs(data["f0_selected_hz"] - manual_f0) < 1e-9
