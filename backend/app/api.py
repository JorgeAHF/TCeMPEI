from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Body, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import schemas
from .config import get_settings
from .db import Base, engine, get_db
from .models import (
    Acquisition,
    AcquisitionChannel,
    AnalysisResult,
    AnalysisRun,
    Bridge,
    Cable,
    CableStateVersion,
    KCalibration,
    RawFile,
    Sensor,
    SensorInstallation,
    StrandType,
    WeighingAttachment,
    WeighingCampaign,
    WeighingMeasurement,
    CableConfigSnapshot,
    User,
    AuditLog,
)
from .security import hash_password, verify_password, create_access_token, decode_token
from .services.business import (
    effective_fu,
    select_cable_state_version,
    select_k_for_timestamp,
    validate_installations_no_overlap,
    validate_k_no_overlap,
)
from .services.ingestion import normalize_from_raw, register_raw_file
from .utils import save_upload

router = APIRouter()
Base.metadata.create_all(bind=engine)
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def ensure_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: int = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    user = db.get(User, user_id)
    if not user:
        raise credentials_exception
    return user


def require_roles(*roles):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return checker


def log_action(db: Session, entity: str, entity_id: int, action: str, user_id: int, notes: str | None = None):
    log = AuditLog(entity=entity, entity_id=entity_id, action=action, performed_by=user_id, notes=notes)
    db.add(log)
    db.commit()


def get_user(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


@router.post("/auth/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "user": schemas.UserOut.from_orm(user)}


@router.post("/users", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))):
    if get_user(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, "user", user.id, "create", current_user.id)
    return user


@router.post("/bridges", response_model=schemas.BridgeOut)
def create_bridge(payload: schemas.BridgeCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    bridge = Bridge(
        nombre=payload.nombre,
        clave_interna=payload.clave_interna,
        num_tirantes=payload.num_tirantes,
        notas=payload.notas,
        created_by_user_id=user.id,
    )
    db.add(bridge)
    db.commit()
    db.refresh(bridge)
    log_action(db, "bridge", bridge.id, "create", user.id)

    # Crear tirantes placeholder si se solicitó
    if payload.num_tirantes and payload.num_tirantes > 0:
        width = max(2, len(str(payload.num_tirantes)))
        for idx in range(1, payload.num_tirantes + 1):
            name = f"T-{idx:0{width}d}"
            cable = Cable(bridge_id=bridge.id, nombre_en_puente=name, created_by_user_id=user.id)
            db.add(cable)
            db.flush()
            log_action(db, "cable", cable.id, "create_placeholder", user.id, notes="auto-generated")
        db.commit()
    return bridge


@router.get("/bridges", response_model=List[schemas.BridgeOut])
def list_bridges(db: Session = Depends(get_db)):
    return db.query(Bridge).order_by(Bridge.nombre).all()


@router.put("/bridges/{bridge_id}", response_model=schemas.BridgeOut)
def update_bridge(
    bridge_id: int,
    payload: schemas.BridgeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    bridge = db.get(Bridge, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Bridge not found")
    current_cables = db.query(Cable).filter(Cable.bridge_id == bridge_id).order_by(Cable.id).all()
    if payload.nombre is not None:
        bridge.nombre = payload.nombre
    if payload.clave_interna is not None:
        bridge.clave_interna = payload.clave_interna
    if payload.notas is not None:
        bridge.notas = payload.notas

    # Ajuste de número de tirantes con validaciones
    if payload.num_tirantes is not None:
        bridge.num_tirantes = payload.num_tirantes
        current_count = len(current_cables)
        target = payload.num_tirantes
        if target < current_count:
            raise HTTPException(
                status_code=400,
                detail="No se puede reducir num_tirantes. Elimina tirantes en el paso 2 antes de disminuir la cantidad.",
            )
        if target > current_count:
            width = max(2, len(str(target)))
            for idx in range(current_count + 1, target + 1):
                name = f"T-{idx:0{width}d}"
                cable = Cable(bridge_id=bridge.id, nombre_en_puente=name, created_by_user_id=user.id)
                db.add(cable)
                db.flush()
                log_action(db, "cable", cable.id, "create_placeholder", user.id, notes="auto-generated by update")

    db.add(bridge)
    db.commit()
    db.refresh(bridge)
    log_action(db, "bridge", bridge.id, "update", user.id)
    return bridge


@router.delete("/bridges/{bridge_id}")
def delete_bridge(
    bridge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    bridge = db.get(Bridge, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Bridge not found")
    cables = db.query(Cable).filter(Cable.bridge_id == bridge_id).all()
    if cables:
        raise HTTPException(status_code=400, detail="Elimina tirantes del puente antes de borrarlo.")
    db.delete(bridge)
    db.commit()
    log_action(db, "bridge", bridge_id, "delete", user.id)
    return {"status": "deleted", "id": bridge_id}


@router.delete("/strand-types/{strand_type_id}")
def delete_strand_type(
    strand_type_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    st = db.get(StrandType, strand_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="Strand type not found")
    db.delete(st)
    db.commit()
    log_action(db, "strand_type", strand_type_id, "delete", user.id)
    return {"status": "deleted", "id": strand_type_id}

@router.post("/strand-types", response_model=schemas.StrandTypeOut)
def create_strand_type(payload: schemas.StrandTypeCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    st = StrandType(**payload.dict(), created_by_user_id=user.id)
    db.add(st)
    db.commit()
    db.refresh(st)
    log_action(db, "strand_type", st.id, "create", user.id)
    return st


@router.get("/strand-types", response_model=List[schemas.StrandTypeOut])
def list_strand_types(db: Session = Depends(get_db)):
    return db.query(StrandType).order_by(StrandType.nombre).all()

@router.put("/strand-types/{strand_type_id}", response_model=schemas.StrandTypeOut)
def update_strand_type(
    strand_type_id: int,
    payload: schemas.StrandTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    st = db.get(StrandType, strand_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="Strand type not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(st, field, value)
    db.add(st)
    db.commit()
    db.refresh(st)
    log_action(db, "strand_type", st.id, "update", user.id)
    return st


@router.post("/cables", response_model=schemas.CableOut)
def create_cable(payload: schemas.CableCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    cable = Cable(**payload.dict(), created_by_user_id=user.id)
    db.add(cable)
    db.commit()
    db.refresh(cable)
    log_action(db, "cable", cable.id, "create", user.id)
    return cable


@router.get("/cables", response_model=List[schemas.CableOut])
def list_cables(db: Session = Depends(get_db)):
    return db.query(Cable).order_by(Cable.bridge_id, Cable.nombre_en_puente).all()


@router.put("/cables/{cable_id}", response_model=schemas.CableOut)
def update_cable(
    cable_id: int,
    payload: schemas.CableUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    cable = db.get(Cable, cable_id)
    if not cable:
        raise HTTPException(status_code=404, detail="Cable not found")
    if payload.nombre_en_puente:
        cable.nombre_en_puente = payload.nombre_en_puente
    if payload.notas is not None:
        cable.notas = payload.notas
    db.add(cable)
    db.commit()
    db.refresh(cable)
    log_action(db, "cable", cable.id, "update", user.id)
    return cable


@router.delete("/cables/{cable_id}")
def delete_cable(cable_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    cable = db.get(Cable, cable_id)
    if not cable:
        raise HTTPException(status_code=404, detail="Cable not found")
    db.delete(cable)
    db.commit()
    log_action(db, "cable", cable_id, "delete", user.id)
    return {"status": "deleted", "id": cable_id}


@router.post("/cable-states", response_model=schemas.CableStateVersionOut)
def create_cable_state(payload: schemas.CableStateVersionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    if payload.valid_to and payload.valid_to <= payload.valid_from:
        raise HTTPException(status_code=400, detail="valid_to must be greater than valid_from")
    if payload.strands_active > payload.strands_total:
        raise HTTPException(status_code=400, detail="strands_active must be <= strands_total")
    if payload.antivandalic_enabled and not payload.antivandalic_length_m:
        raise HTTPException(status_code=400, detail="antivandalic_length_m required when antivandalic_enabled")

    open_state = (
        db.query(CableStateVersion)
        .filter(CableStateVersion.cable_id == payload.cable_id, CableStateVersion.valid_to.is_(None))
        .first()
    )
    if open_state and payload.valid_to is None:
        raise HTTPException(status_code=400, detail="Cable already has an open state version")

    state = CableStateVersion(**payload.dict(), created_by_user_id=user.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    log_action(db, "cable_state_version", state.id, "create", user.id)
    return state


@router.get("/cables/{cable_id}/states", response_model=List[schemas.CableStateVersionOut])
def list_cable_states(cable_id: int, db: Session = Depends(get_db)):
    return (
        db.query(CableStateVersion)
        .filter(CableStateVersion.cable_id == cable_id)
        .order_by(CableStateVersion.valid_from.desc())
        .all()
    )


@router.post("/sensors", response_model=schemas.SensorOut)
def create_sensor(payload: schemas.SensorCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    sensor = Sensor(**payload.dict(), created_by_user_id=user.id)
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    log_action(db, "sensor", sensor.id, "create", user.id)
    return sensor


@router.get("/sensors", response_model=List[schemas.SensorOut])
def list_sensors(db: Session = Depends(get_db)):
    return db.query(Sensor).order_by(Sensor.serial_or_asset_id).all()


@router.post("/sensor-installations", response_model=schemas.SensorInstallationOut)
def create_sensor_installation(payload: schemas.SensorInstallationCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    if payload.installed_to and payload.installed_to <= payload.installed_from:
        raise HTTPException(status_code=400, detail="installed_to must be greater than installed_from")
    if payload.height_m <= 0:
        raise HTTPException(status_code=400, detail="height_m must be > 0")

    existing = db.query(SensorInstallation).filter(SensorInstallation.sensor_id == payload.sensor_id).all()
    validate_installations_no_overlap(existing + [SensorInstallation(**payload.dict())])

    inst = SensorInstallation(**payload.dict(), created_by_user_id=user.id)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    log_action(db, "sensor_installation", inst.id, "create", user.id)
    return inst


@router.get("/sensor-installations", response_model=List[schemas.SensorInstallationOut])
def list_sensor_installations(db: Session = Depends(get_db)):
    return (
        db.query(SensorInstallation)
        .order_by(SensorInstallation.sensor_id, SensorInstallation.installed_from.desc())
        .all()
    )


@router.post("/acquisitions", response_model=schemas.AcquisitionOut)
def create_acquisition(payload: schemas.AcquisitionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    acq = Acquisition(**payload.dict(), created_by_user_id=user.id)
    db.add(acq)
    db.commit()
    db.refresh(acq)
    log_action(db, "acquisition", acq.id, "create", user.id)
    return acq


@router.post("/weighing-campaigns", response_model=schemas.WeighingCampaignOut)
def create_weighing_campaign(payload: schemas.WeighingCampaignCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    wc = WeighingCampaign(**payload.dict(), created_by_user_id=user.id)
    db.add(wc)
    db.commit()
    db.refresh(wc)
    log_action(db, "weighing_campaign", wc.id, "create", user.id)
    return wc


@router.post("/analysis-runs", response_model=schemas.AnalysisRunOut)
def create_analysis_run(payload: schemas.AnalysisRunCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    run = AnalysisRun(**payload.dict(), created_by_user_id=user.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    log_action(db, "analysis_run", run.id, "create", user.id)
    return run


@router.post("/analysis-results", response_model=schemas.AnalysisResultOut)
def create_analysis_result(payload: schemas.AnalysisResultCreate, db: Session = Depends(get_db)):
    run = db.get(AnalysisRun, payload.analysis_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    acq = db.get(Acquisition, run.acquisition_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found for run")
    calibrations = db.query(KCalibration).filter(KCalibration.cable_id == payload.cable_id).all()
    try:
        selected_k = select_k_for_timestamp(calibrations, acq.acquired_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="No K vigente para la fecha de la acquisition")

    tension = (payload.f0_hz ** 2) * selected_k.k_value
    res = AnalysisResult(
        analysis_run_id=payload.analysis_run_id,
        cable_id=payload.cable_id,
        f0_hz=payload.f0_hz,
        harmonics_json=payload.harmonics_json,
        k_used_value=selected_k.k_value,
        k_used_calibration_id=selected_k.id,
        tension_tf=tension,
        df_hz=payload.df_hz,
        snr_metric=payload.snr_metric,
        quality_flag=payload.quality_flag,
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@router.get("/analysis-runs/{run_id}/results", response_model=List[schemas.AnalysisResultOut])
def list_analysis_results(run_id: int, db: Session = Depends(get_db)):
    return (
        db.query(AnalysisResult)
        .filter(AnalysisResult.analysis_run_id == run_id)
        .order_by(AnalysisResult.created_at.desc())
        .all()
    )


@router.get("/history", response_model=schemas.HistoryResponse)
def history(
    bridge_id: int | None = None,
    cable_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(
            AnalysisResult,
            AnalysisRun,
            Acquisition,
            Cable,
        )
        .join(AnalysisRun, AnalysisResult.analysis_run_id == AnalysisRun.id)
        .join(Acquisition, AnalysisRun.acquisition_id == Acquisition.id)
        .join(Cable, Cable.id == AnalysisResult.cable_id)
    )
    if bridge_id:
        q = q.filter(Cable.bridge_id == bridge_id)
    if cable_id:
        q = q.filter(Cable.id == cable_id)
    if date_from:
        q = q.filter(Acquisition.acquired_at >= date_from)
    if date_to:
        q = q.filter(Acquisition.acquired_at <= date_to)

    rows = q.order_by(Acquisition.acquired_at).all()
    items = [
        schemas.HistoryItem(
            cable_id=cable.id,
            nombre_en_puente=cable.nombre_en_puente,
            acquired_at=acq.acquired_at,
            analysis_run_id=run.id,
            f0_hz=res.f0_hz,
            tension_tf=res.tension_tf,
            k_used_value=res.k_used_value,
            k_used_calibration_id=res.k_used_calibration_id,
            quality_flag=res.quality_flag,
        )
        for res, run, acq, cable in rows
    ]

    k_list = None
    if cable_id:
        k_list = list_k_calibrations(cable_id=cable_id, db=db)
    return schemas.HistoryResponse(results=items, k_calibrations=k_list)


@router.post("/acquisitions/{acq_id}/file")
def upload_acquisition_file(
    acq_id: int,
    file_kind: str,
    parser_version: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    acq = db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    data = file.file.read()
    path, digest = save_upload(Path(settings.data_root), "raw" if file_kind == "raw_csv" else "normalized", file.filename, data)
    record = RawFile(
        acquisition_id=acq_id,
        file_kind=file_kind,
        storage_path=str(path),
        original_filename=file.filename,
        sha256=digest,
        file_size_bytes=len(data),
        parser_version=parser_version,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "sha256": digest, "path": record.storage_path}


@router.post("/acquisitions/{acq_id}/raw-upload")
def upload_raw_csv(
    acq_id: int,
    parser_version: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    acq = db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    data = file.file.read()
    record = register_raw_file(db, acq, parser_version, file.filename, Path(settings.data_root), data)
    log_action(db, "raw_file", record.id, "create", user.id, notes="raw_csv")
    return {"id": record.id, "sha256": record.sha256, "path": record.storage_path}


@router.post("/acquisitions/{acq_id}/normalize")
def normalize_acquisition(
    acq_id: int,
    parser_version: str,
    mapping: List[dict] = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    acq = db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    norm_record, channels, path = normalize_from_raw(
        db=db,
        acq=acq,
        mapping=mapping,
        data_root=Path(settings.data_root),
        parser_version=parser_version,
    )
    log_action(db, "raw_file", norm_record.id, "create", user.id, notes="normalized_csv")
    return {
        "normalized_file_id": norm_record.id,
        "path": path,
        "channels_created": len(channels),
    }


@router.post("/weighing-measurements", response_model=schemas.WeighingMeasurementOut)
def create_weighing_measurement(payload: schemas.WeighingMeasurementCreate, db: Session = Depends(get_db)):
    if payload.measured_tension_tf <= 0:
        raise HTTPException(status_code=400, detail="measured_tension_tf must be > 0")
    wm = WeighingMeasurement(**payload.dict())
    db.add(wm)
    db.commit()
    db.refresh(wm)
    return wm


@router.get("/weighing-measurements", response_model=List[schemas.WeighingMeasurementOut])
def list_weighing_measurements(db: Session = Depends(get_db)):
    return db.query(WeighingMeasurement).order_by(WeighingMeasurement.weighing_campaign_id.desc()).all()


@router.post("/cable-config-snapshots", response_model=schemas.CableConfigSnapshotOut)
def create_snapshot(payload: schemas.CableConfigSnapshotCreate, db: Session = Depends(get_db)):
    if payload.strands_active > payload.strands_total:
        raise HTTPException(status_code=400, detail="strands_active must be <= strands_total")
    if payload.effective_length_m <= 0 or payload.mu_value_kg_m <= 0:
        raise HTTPException(status_code=400, detail="effective_length_m and mu_value_kg_m must be > 0")
    snap = CableConfigSnapshot(**payload.dict())
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


@router.get("/cable-config-snapshots", response_model=List[schemas.CableConfigSnapshotOut])
def list_snapshots(cable_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(CableConfigSnapshot)
    if cable_id:
        q = q.filter(CableConfigSnapshot.cable_id == cable_id)
    return q.order_by(CableConfigSnapshot.created_at.desc()).all()


@router.post("/k-calibrations", response_model=schemas.KCalibrationOut)
def create_k_calibration(payload: schemas.KCalibrationCreate, db: Session = Depends(get_db)):
    if payload.k_value <= 0:
        raise HTTPException(status_code=400, detail="k_value must be > 0")
    if payload.valid_to and payload.valid_to <= payload.valid_from:
        raise HTTPException(status_code=400, detail="valid_to must be greater than valid_from")
    existing = db.query(KCalibration).filter(KCalibration.cable_id == payload.cable_id).all()
    candidate = KCalibration(**payload.dict())
    validate_k_no_overlap(existing, candidate)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/k-calibrations", response_model=List[schemas.KCalibrationOut])
def list_k_calibrations(cable_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(KCalibration)
    if cable_id:
        q = q.filter(KCalibration.cable_id == cable_id)
    return q.order_by(KCalibration.valid_from.desc()).all()


@router.post("/weighing-campaigns/{campaign_id}/attachment")
def upload_weighing_attachment(
    campaign_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    wc = db.get(WeighingCampaign, campaign_id)
    if not wc:
        raise HTTPException(status_code=404, detail="Weighing campaign not found")
    data = file.file.read()
    path, digest = save_upload(Path(settings.data_root), "attachments", file.filename, data)
    attach = WeighingAttachment(
        weighing_campaign_id=campaign_id,
        storage_path=str(path),
        filename=file.filename,
        sha256=digest,
    )
    db.add(attach)
    db.commit()
    db.refresh(attach)
    return {"id": attach.id, "sha256": digest, "path": attach.storage_path}


@router.get("/bridges/{bridge_id}/semaforo", response_model=schemas.SemaforoResponse)
def semaforo(bridge_id: int, acquisition_id: int, top_n: int | None = Query(None, gt=0), db: Session = Depends(get_db)):
    acq = db.get(Acquisition, acquisition_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    rows = (
        db.query(AnalysisResult, Cable)
        .join(AnalysisRun, AnalysisResult.analysis_run_id == AnalysisRun.id)
        .join(Cable, Cable.id == AnalysisResult.cable_id)
        .filter(AnalysisRun.acquisition_id == acquisition_id, Cable.bridge_id == bridge_id)
        .all()
    )
    if not rows:
        return schemas.SemaforoResponse(bridge_id=bridge_id, acquisition_id=acquisition_id, total=0, exceden=0, items=[])

    items = []
    exceden = 0
    for res, cable in rows:
        states: List[CableStateVersion] = db.query(CableStateVersion).filter(CableStateVersion.cable_id == cable.id).all()
        if not states:
            continue
        state_selected = select_cable_state_version(states, acq.acquired_at)
        fu = effective_fu(state_selected)
        tension = res.tension_tf
        pct = (tension / fu) * 100 if fu else 0.0
        estado = "ALERTA" if pct > 45.0 else "OK"
        if estado == "ALERTA":
            exceden += 1
        items.append(
            schemas.SemaforoItem(
                cable_id=cable.id,
                nombre_en_puente=cable.nombre_en_puente,
                tension_tf=tension,
                fu=fu,
                pct_fu=pct,
                estado=estado,
            )
        )

    items_sorted = sorted(items, key=lambda x: x.pct_fu, reverse=True)
    if top_n:
        items_sorted = items_sorted[:top_n]
    return schemas.SemaforoResponse(
        bridge_id=bridge_id,
        acquisition_id=acquisition_id,
        total=len(items),
        exceden=exceden,
        items=items_sorted,
        top_n=top_n,
    )
