import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

from app.db import Base, SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    CableConfigSnapshot,
    CableStateVersion,
    KCalibration,
    WeighingCampaign,
    WeighingMeasurement,
)


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_full_flow_semáforo_alerta():
    # 1) Crear usuario
    user_resp = client.post(
        "/users", json={"username": "admin", "password": "secret", "full_name": "Admin", "role": "admin"}
    )
    assert user_resp.status_code == 200
    user_id = user_resp.json()["id"]

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
    )
    st_id = st_resp.json()["id"]

    bridge_id = client.post("/bridges", json={"nombre": "Puente 1", "clave_interna": "P1"}).json()["id"]
    cable_id = client.post("/cables", json={"bridge_id": bridge_id, "nombre_en_puente": "C1"}).json()["id"]

    # 3) Cable state version, weighing, K (direct DB for now)
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
    ).json()["id"]

    run_id = client.post(
        "/analysis-runs",
        json={"acquisition_id": acq_id, "created_by_user_id": user_id, "algorithm_version": "v1.0", "notes": ""},
    ).json()["id"]

    # Tensión 60 tf, Fu 110 -> 54.5% => ALERTA
    res_resp = client.post(
        "/analysis-results",
        json={
            "analysis_run_id": run_id,
            "cable_id": cable_id,
            "f0_hz": 2.0,
            "harmonics_json": {},
            "k_used_value": 15.0,
            "k_used_calibration_id": kc.id,
            "tension_tf": 60.0,
            "df_hz": 0.1,
            "snr_metric": 10.0,
            "quality_flag": "ok",
        },
    )
    assert res_resp.status_code == 200

    sem = client.get(f"/bridges/{bridge_id}/semaforo", params={"acquisition_id": acq_id})
    data = sem.json()
    assert data["total"] == 1
    assert data["exceden"] == 1
    assert data["items"][0]["estado"] == "ALERTA"
