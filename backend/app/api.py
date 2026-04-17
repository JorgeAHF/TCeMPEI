from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Body, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import schemas
from .config import get_settings
from .db import get_db
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
    RefreshToken,
)
from .security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from .services.business import (
    effective_fu,
    select_cable_state_version,
    select_k_for_timestamp,
    validate_installations_no_overlap,
    validate_k_no_overlap,
)
from .services.ingestion import (
    DuplicateRawFileInAcquisitionError,
    build_raw_preview,
    get_next_file_version,
    normalize_from_raw,
    register_raw_file,
)
from .services.signal_analysis import build_analysis_preview, detect_anomalies
from .utils import save_upload

router = APIRouter()
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
ALLOWED_ROLES = {"admin", "analyst", "reviewer", "viewer"}


def ensure_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
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
    user = await db.get(User, user_id)
    if not user:
        raise credentials_exception
    return user


def require_roles(*roles):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return checker


async def log_action(db: AsyncSession, entity: str, entity_id: int, action: str, user_id: int, notes: str | None = None):
    log = AuditLog(entity=entity, entity_id=entity_id, action=action, performed_by=user_id, notes=notes)
    db.add(log)
    await db.commit()


async def get_user(db: AsyncSession, username: str) -> User | None:
    return (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()


async def _persist_refresh_token(db: AsyncSession, user_id: int, jti: str, expires_at: datetime) -> RefreshToken:
    token_row = RefreshToken(user_id=user_id, token_jti=jti, expires_at=expires_at)
    db.add(token_row)
    await db.commit()
    await db.refresh(token_row)
    return token_row


async def _revoke_refresh_token(db: AsyncSession, jti: str, reason: str) -> None:
    row = (await db.execute(select(RefreshToken).where(RefreshToken.token_jti == jti))).scalar_one_or_none()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        row.revoked_reason = reason
        db.add(row)
        await db.commit()


@router.post("/auth/login", response_model=schemas.AuthLoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="User role is not allowed")
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token, jti, refresh_exp = create_refresh_token({"sub": str(user.id)})
    await _persist_refresh_token(db, user.id, jti, refresh_exp)
    await log_action(db, "auth", user.id, "login", user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "access_expires_in_minutes": settings.access_token_expire_minutes,
        "refresh_expires_in_minutes": settings.refresh_token_expire_minutes,
        "user": schemas.UserOut.from_orm(user),
    }


@router.post("/auth/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # Backward-compatible endpoint expected by OAuth2PasswordBearer and the web client login flow.
    return await login(form_data, db)


@router.post("/auth/refresh", response_model=schemas.AuthRefreshResponse)
async def refresh_access_token(payload: schemas.AuthRefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(token_payload.get("sub"))
        jti = token_payload.get("jti")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if not jti:
        raise HTTPException(status_code=401, detail="Malformed refresh token")

    token_row = (await db.execute(select(RefreshToken).where(RefreshToken.token_jti == jti))).scalar_one_or_none()
    if not token_row or token_row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    if token_row.expires_at <= datetime.utcnow():
        await _revoke_refresh_token(db, jti, "expired")
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Rotation: revoke old token and issue a new pair.
    await _revoke_refresh_token(db, jti, "rotated")
    access_token = create_access_token({"sub": str(user.id)})
    new_refresh_token, new_jti, refresh_exp = create_refresh_token({"sub": str(user.id)})
    await _persist_refresh_token(db, user.id, new_jti, refresh_exp)
    await log_action(db, "auth", user.id, "refresh", user.id)
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "access_expires_in_minutes": settings.access_token_expire_minutes,
        "refresh_expires_in_minutes": settings.refresh_token_expire_minutes,
    }


@router.post("/auth/logout")
async def logout(payload: schemas.AuthLogoutRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
        jti = token_payload.get("jti")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not jti:
        raise HTTPException(status_code=401, detail="Malformed refresh token")
    await _revoke_refresh_token(db, jti, "logout")
    await log_action(db, "auth", user.id, "logout", user.id)
    return {"status": "ok"}


@router.post("/users", response_model=schemas.UserOut)
async def create_user(payload: schemas.UserCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_roles("admin"))):
    if await get_user(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_action(db, "user", user.id, "create", current_user.id)
    return user


@router.post("/bridges", response_model=schemas.BridgeOut)
async def create_bridge(payload: schemas.BridgeCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    bridge = Bridge(
        nombre=payload.nombre,
        clave_interna=payload.clave_interna,
        num_tirantes=payload.num_tirantes,
        notas=payload.notas,
        created_by_user_id=user.id,
    )
    db.add(bridge)
    await db.commit()
    await db.refresh(bridge)
    await log_action(db, "bridge", bridge.id, "create", user.id)

    # Crear tirantes placeholder si se solicitó
    if payload.num_tirantes and payload.num_tirantes > 0:
        width = max(2, len(str(payload.num_tirantes)))
        for idx in range(1, payload.num_tirantes + 1):
            name = f"T-{idx:0{width}d}"
            cable = Cable(bridge_id=bridge.id, nombre_en_puente=name, created_by_user_id=user.id)
            db.add(cable)
            await db.flush()
            await log_action(db, "cable", cable.id, "create_placeholder", user.id, notes="auto-generated")
        await db.commit()
    return bridge


@router.get("/bridges", response_model=List[schemas.BridgeOut])
async def list_bridges(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Bridge).order_by(Bridge.nombre))).scalars().all()


@router.put("/bridges/{bridge_id}", response_model=schemas.BridgeOut)
async def update_bridge(
    bridge_id: int,
    payload: schemas.BridgeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    bridge = await db.get(Bridge, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Bridge not found")
    current_cables = (await db.execute(select(Cable).where(Cable.bridge_id == bridge_id).order_by(Cable.id))).scalars().all()
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
                await db.flush()
                await log_action(db, "cable", cable.id, "create_placeholder", user.id, notes="auto-generated by update")

    db.add(bridge)
    await db.commit()
    await db.refresh(bridge)
    await log_action(db, "bridge", bridge.id, "update", user.id)
    return bridge


@router.delete("/bridges/{bridge_id}")
async def delete_bridge(
    bridge_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    bridge = await db.get(Bridge, bridge_id)
    if not bridge:
        raise HTTPException(status_code=404, detail="Bridge not found")
    cables = (await db.execute(select(Cable).where(Cable.bridge_id == bridge_id))).scalars().all()
    if cables:
        raise HTTPException(status_code=400, detail="Elimina tirantes del puente antes de borrarlo.")
    await db.delete(bridge)
    await db.commit()
    await log_action(db, "bridge", bridge_id, "delete", user.id)
    return {"status": "deleted", "id": bridge_id}


@router.delete("/strand-types/{strand_type_id}")
async def delete_strand_type(
    strand_type_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    st = await db.get(StrandType, strand_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="Strand type not found")
    await db.delete(st)
    await db.commit()
    await log_action(db, "strand_type", strand_type_id, "delete", user.id)
    return {"status": "deleted", "id": strand_type_id}


@router.post("/strand-types", response_model=schemas.StrandTypeOut)
async def create_strand_type(payload: schemas.StrandTypeCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    st = StrandType(**payload.dict(), created_by_user_id=user.id)
    db.add(st)
    await db.commit()
    await db.refresh(st)
    await log_action(db, "strand_type", st.id, "create", user.id)
    return st


@router.get("/strand-types", response_model=List[schemas.StrandTypeOut])
async def list_strand_types(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(StrandType).order_by(StrandType.nombre))).scalars().all()


@router.put("/strand-types/{strand_type_id}", response_model=schemas.StrandTypeOut)
async def update_strand_type(
    strand_type_id: int,
    payload: schemas.StrandTypeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    st = await db.get(StrandType, strand_type_id)
    if not st:
        raise HTTPException(status_code=404, detail="Strand type not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(st, field, value)
    db.add(st)
    await db.commit()
    await db.refresh(st)
    await log_action(db, "strand_type", st.id, "update", user.id)
    return st


@router.post("/cables", response_model=schemas.CableOut)
async def create_cable(payload: schemas.CableCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    cable = Cable(**payload.dict(), created_by_user_id=user.id)
    db.add(cable)
    await db.commit()
    await db.refresh(cable)
    await log_action(db, "cable", cable.id, "create", user.id)
    return cable


@router.get("/cables", response_model=List[schemas.CableOut])
async def list_cables(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Cable).order_by(Cable.bridge_id, Cable.nombre_en_puente))).scalars().all()


@router.put("/cables/{cable_id}", response_model=schemas.CableOut)
async def update_cable(
    cable_id: int,
    payload: schemas.CableUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    cable = await db.get(Cable, cable_id)
    if not cable:
        raise HTTPException(status_code=404, detail="Cable not found")
    if payload.nombre_en_puente:
        cable.nombre_en_puente = payload.nombre_en_puente
    if payload.notas is not None:
        cable.notas = payload.notas
    db.add(cable)
    await db.commit()
    await db.refresh(cable)
    await log_action(db, "cable", cable.id, "update", user.id)
    return cable


@router.delete("/cables/{cable_id}")
async def delete_cable(cable_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    cable = await db.get(Cable, cable_id)
    if not cable:
        raise HTTPException(status_code=404, detail="Cable not found")
    await db.delete(cable)
    await db.commit()
    await log_action(db, "cable", cable_id, "delete", user.id)
    return {"status": "deleted", "id": cable_id}


@router.post("/cable-states", response_model=schemas.CableStateVersionOut)
async def create_cable_state(payload: schemas.CableStateVersionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    if payload.valid_to and payload.valid_to <= payload.valid_from:
        raise HTTPException(status_code=400, detail="valid_to must be greater than valid_from")
    if payload.strands_active > payload.strands_total:
        raise HTTPException(status_code=400, detail="strands_active must be <= strands_total")
    if payload.antivandalic_enabled and not payload.antivandalic_length_m:
        raise HTTPException(status_code=400, detail="antivandalic_length_m required when antivandalic_enabled")

    open_state = (
        await db.execute(
            select(CableStateVersion).where(
                CableStateVersion.cable_id == payload.cable_id,
                CableStateVersion.valid_to.is_(None),
            )
        )
    ).scalar_one_or_none()
    if open_state and payload.valid_to is None:
        raise HTTPException(status_code=400, detail="Cable already has an open state version")

    state = CableStateVersion(**payload.dict(), created_by_user_id=user.id)
    db.add(state)
    await db.commit()
    await db.refresh(state)
    await log_action(db, "cable_state_version", state.id, "create", user.id)
    return state


@router.get("/cables/{cable_id}/states", response_model=List[schemas.CableStateVersionOut])
async def list_cable_states(cable_id: int, db: AsyncSession = Depends(get_db)):
    return (
        await db.execute(
            select(CableStateVersion)
            .where(CableStateVersion.cable_id == cable_id)
            .order_by(CableStateVersion.valid_from.desc())
        )
    ).scalars().all()


@router.post("/sensors", response_model=schemas.SensorOut)
async def create_sensor(payload: schemas.SensorCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    sensor = Sensor(**payload.dict(), created_by_user_id=user.id)
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)
    await log_action(db, "sensor", sensor.id, "create", user.id)
    return sensor


@router.get("/sensors", response_model=List[schemas.SensorOut])
async def list_sensors(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Sensor).order_by(Sensor.serial_or_asset_id))).scalars().all()


@router.post("/sensor-installations", response_model=schemas.SensorInstallationOut)
async def create_sensor_installation(payload: schemas.SensorInstallationCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    if payload.installed_to and payload.installed_to <= payload.installed_from:
        raise HTTPException(status_code=400, detail="installed_to must be greater than installed_from")
    if payload.height_m <= 0:
        raise HTTPException(status_code=400, detail="height_m must be > 0")

    existing = (
        await db.execute(select(SensorInstallation).where(SensorInstallation.sensor_id == payload.sensor_id))
    ).scalars().all()
    validate_installations_no_overlap(existing + [SensorInstallation(**payload.dict())])

    inst = SensorInstallation(**payload.dict(), created_by_user_id=user.id)
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    await log_action(db, "sensor_installation", inst.id, "create", user.id)
    return inst


@router.get("/sensor-installations", response_model=List[schemas.SensorInstallationOut])
async def list_sensor_installations(db: AsyncSession = Depends(get_db)):
    return (
        await db.execute(
            select(SensorInstallation).order_by(
                SensorInstallation.sensor_id, SensorInstallation.installed_from.desc()
            )
        )
    ).scalars().all()


@router.post("/acquisitions", response_model=schemas.AcquisitionOut)
async def create_acquisition(payload: schemas.AcquisitionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    acq = Acquisition(**payload.dict(), created_by_user_id=user.id)
    db.add(acq)
    await db.commit()
    await db.refresh(acq)
    await log_action(db, "acquisition", acq.id, "create", user.id)
    return acq


@router.get("/acquisitions", response_model=List[schemas.AcquisitionOut])
async def list_acquisitions(bridge_id: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Acquisition)
    if bridge_id:
        stmt = stmt.where(Acquisition.bridge_id == bridge_id)
    stmt = stmt.order_by(Acquisition.acquired_at.desc(), Acquisition.id.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/weighing-campaigns", response_model=schemas.WeighingCampaignOut)
async def create_weighing_campaign(payload: schemas.WeighingCampaignCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst"))):
    wc = WeighingCampaign(**payload.dict(), created_by_user_id=user.id)
    db.add(wc)
    await db.commit()
    await db.refresh(wc)
    await log_action(db, "weighing_campaign", wc.id, "create", user.id)
    return wc


@router.get("/weighing-campaigns", response_model=List[schemas.WeighingCampaignOut])
async def list_weighing_campaigns(bridge_id: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(WeighingCampaign)
    if bridge_id:
        stmt = stmt.where(WeighingCampaign.bridge_id == bridge_id)
    stmt = stmt.order_by(WeighingCampaign.performed_at.desc(), WeighingCampaign.id.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/analysis-runs", response_model=schemas.AnalysisRunOut)
async def create_analysis_run(payload: schemas.AnalysisRunCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst", "reviewer"))):
    run_payload = payload.dict(exclude={"created_by_user_id"})
    run = AnalysisRun(**run_payload, created_by_user_id=user.id)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    await log_action(db, "analysis_run", run.id, "create", user.id)
    return run


@router.get("/analysis-runs", response_model=List[schemas.AnalysisRunOut])
async def list_analysis_runs(acquisition_id: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(AnalysisRun)
    if acquisition_id:
        stmt = stmt.where(AnalysisRun.acquisition_id == acquisition_id)
    stmt = stmt.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/analysis-runs/{run_id}/preview", response_model=schemas.AnalysisPreviewResponse)
async def preview_analysis_run(
    run_id: int,
    payload: schemas.AnalysisPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "reviewer", "viewer")),
):
    run = await db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    acq = await db.get(Acquisition, run.acquisition_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found for run")
    cable = await db.get(Cable, payload.cable_id)
    if not cable:
        raise HTTPException(status_code=404, detail="Cable not found")
    if cable.bridge_id != acq.bridge_id:
        raise HTTPException(status_code=400, detail="Cable does not belong to acquisition bridge")

    try:
        result = await build_analysis_preview(
            db=db,
            run_id=run_id,
            acquisition=acq,
            cable=cable,
            csv_column_name=payload.csv_column_name,
            normalized_file_id=payload.normalized_file_id,
            segment_pct_start=payload.segment_pct_start,
            segment_pct_end=payload.segment_pct_end,
            nperseg=payload.nperseg,
            noverlap_pct=payload.noverlap_pct,
            peak_threshold=payload.peak_threshold,
            min_distance_hz=payload.min_distance_hz,
            n_harmonics=payload.n_harmonics,
            f0_hint_hz=payload.f0_hint_hz,
            f0_manual_hz=payload.f0_manual_hz,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await log_action(db, "analysis_run", run.id, "preview", user.id, notes=f"cable_id={payload.cable_id}")
    return result


@router.post("/analysis-results", response_model=schemas.AnalysisResultOut)
async def create_analysis_result(payload: schemas.AnalysisResultCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles("admin", "analyst", "reviewer"))):
    run = await db.get(AnalysisRun, payload.analysis_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="AnalysisRun not found")
    acq = await db.get(Acquisition, run.acquisition_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found for run")
    calibrations = (
        await db.execute(select(KCalibration).where(KCalibration.cable_id == payload.cable_id))
    ).scalars().all()
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
    await db.commit()
    await db.refresh(res)
    await log_action(db, "analysis_result", res.id, "create", user.id)
    return res


@router.get("/analysis-runs/{run_id}/results", response_model=List[schemas.AnalysisResultOut])
async def list_analysis_results(run_id: int, db: AsyncSession = Depends(get_db)):
    return (
        await db.execute(
            select(AnalysisResult)
            .where(AnalysisResult.analysis_run_id == run_id)
            .order_by(AnalysisResult.created_at.desc())
        )
    ).scalars().all()


@router.patch("/analysis-results/{result_id}/approve", response_model=schemas.AnalysisResultApproveResponse)
async def approve_analysis_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "reviewer")),
):
    """Marca un analysis_result como aprobado/vigente para su tirante dentro del mismo run.
    Desaprueba automáticamente cualquier resultado anterior aprobado del mismo cable en el mismo run.
    """
    result = await db.get(AnalysisResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="AnalysisResult not found")

    # Desaprobar otros resultados del mismo cable en el mismo run
    siblings = (
        await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.analysis_run_id == result.analysis_run_id,
                AnalysisResult.cable_id == result.cable_id,
                AnalysisResult.id != result_id,
                AnalysisResult.is_approved.is_(True),
            )
        )
    ).scalars().all()

    unapproved_ids: list[int] = []
    for sibling in siblings:
        sibling.is_approved = False
        sibling.approved_by_user_id = None
        sibling.approved_at = None
        db.add(sibling)
        unapproved_ids.append(sibling.id)

    result.is_approved = True
    result.approved_by_user_id = user.id
    result.approved_at = datetime.utcnow()
    db.add(result)
    await db.commit()
    await db.refresh(result)
    await log_action(
        db, "analysis_result", result.id, "approve", user.id,
        notes=f"unapproved={unapproved_ids}" if unapproved_ids else None,
    )
    return schemas.AnalysisResultApproveResponse(
        id=result.id,
        is_approved=result.is_approved,
        approved_by_user_id=result.approved_by_user_id,
        approved_at=result.approved_at,
        previously_unapproved_ids=unapproved_ids,
    )


@router.patch("/analysis-results/{result_id}/unapprove", response_model=schemas.AnalysisResultOut)
async def unapprove_analysis_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "reviewer")),
):
    """Revoca la aprobación de un analysis_result."""
    result = await db.get(AnalysisResult, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="AnalysisResult not found")
    result.is_approved = False
    result.approved_by_user_id = None
    result.approved_at = None
    db.add(result)
    await db.commit()
    await db.refresh(result)
    await log_action(db, "analysis_result", result.id, "unapprove", user.id)
    return result


@router.get("/history", response_model=schemas.HistoryResponse)
async def history(
    bridge_id: int | None = None,
    cable_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AnalysisResult, AnalysisRun, Acquisition, Cable)
        .join(AnalysisRun, AnalysisResult.analysis_run_id == AnalysisRun.id)
        .join(Acquisition, AnalysisRun.acquisition_id == Acquisition.id)
        .join(Cable, Cable.id == AnalysisResult.cable_id)
    )
    if bridge_id:
        stmt = stmt.where(Cable.bridge_id == bridge_id)
    if cable_id:
        stmt = stmt.where(Cable.id == cable_id)
    if date_from:
        stmt = stmt.where(Acquisition.acquired_at >= date_from)
    if date_to:
        stmt = stmt.where(Acquisition.acquired_at <= date_to)
    stmt = stmt.order_by(Acquisition.acquired_at)

    rows = (await db.execute(stmt)).all()
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
        k_list = await list_k_calibrations(cable_id=cable_id, db=db)
    return schemas.HistoryResponse(results=items, k_calibrations=k_list)


@router.post("/acquisitions/{acq_id}/file")
async def upload_acquisition_file(
    acq_id: int,
    file_kind: str,
    parser_version: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    acq = await db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    data = await file.read()
    if file_kind not in {"raw_csv", "normalized_csv"}:
        raise HTTPException(status_code=400, detail="file_kind must be raw_csv or normalized_csv")

    warning = None
    if file_kind == "raw_csv":
        try:
            record, warning = await register_raw_file(db, acq, parser_version, file.filename, Path(settings.data_root), data)
        except DuplicateRawFileInAcquisitionError as exc:
            raise HTTPException(
                status_code=409,
                detail=f"{exc}. raw_file_id existente={exc.existing_file_id}",
            )
    else:
        version_no = await get_next_file_version(db, acq_id, "normalized_csv")
        versioned_name = f"acq{acq_id}_normalized_v{version_no:04d}_{Path(file.filename).name.replace(' ', '_')}"
        path, digest = save_upload(Path(settings.data_root), "normalized", versioned_name, data)
        record = RawFile(
            acquisition_id=acq_id,
            file_kind="normalized_csv",
            source_raw_file_id=None,
            version_no=version_no,
            storage_path=str(path),
            original_filename=file.filename,
            sha256=digest,
            file_size_bytes=len(data),
            parser_version=parser_version,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
    await log_action(db, "raw_file", record.id, "create", user.id, notes=file_kind)
    return {
        "id": record.id,
        "sha256": record.sha256,
        "path": record.storage_path,
        "version_no": record.version_no,
        "warning": warning,
    }


@router.get("/acquisitions/{acq_id}/raw-preview")
async def preview_raw_csv(
    acq_id: int,
    raw_file_id: int | None = None,
    header_row_override: int | None = Query(default=None, ge=0),
    data_start_marker: str = "DATA_START",
    max_lines: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "reviewer", "viewer")),
):
    acq = await db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    q = select(RawFile).where(RawFile.acquisition_id == acq_id, RawFile.file_kind == "raw_csv")
    if raw_file_id is not None:
        raw_record = (await db.execute(q.where(RawFile.id == raw_file_id))).scalar_one_or_none()
    else:
        raw_record = (await db.execute(q.order_by(RawFile.version_no.desc(), RawFile.created_at.desc()))).scalars().first()
    if not raw_record:
        raise HTTPException(status_code=404, detail="No raw_csv file found for acquisition")
    content = Path(raw_record.storage_path).read_bytes()
    try:
        preview = build_raw_preview(
            content=content,
            data_start_marker=data_start_marker,
            header_row_override=header_row_override,
            max_lines=max_lines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    preview.update(
        {
            "raw_file_id": raw_record.id,
            "version_no": raw_record.version_no,
            "original_filename": raw_record.original_filename,
        }
    )
    return preview


@router.post("/acquisitions/{acq_id}/parse-preview")
async def parse_preview_raw_csv(
    acq_id: int,
    raw_file_id: int | None = None,
    header_row_override: int | None = Query(default=None, ge=0),
    data_start_marker: str = "DATA_START",
    max_lines: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "reviewer", "viewer")),
):
    return await preview_raw_csv(
        acq_id=acq_id,
        raw_file_id=raw_file_id,
        header_row_override=header_row_override,
        data_start_marker=data_start_marker,
        max_lines=max_lines,
        db=db,
        user=user,
    )


@router.post("/acquisitions/{acq_id}/raw-upload")
async def upload_raw_csv(
    acq_id: int,
    parser_version: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    acq = await db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    data = await file.read()
    try:
        record, warning = await register_raw_file(db, acq, parser_version, file.filename, Path(settings.data_root), data)
    except DuplicateRawFileInAcquisitionError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"{exc}. raw_file_id existente={exc.existing_file_id}",
        )
    await log_action(db, "raw_file", record.id, "create", user.id, notes="raw_csv")
    return {
        "id": record.id,
        "sha256": record.sha256,
        "path": record.storage_path,
        "version_no": record.version_no,
        "warning": warning,
    }


@router.post("/acquisitions/{acq_id}/normalize")
async def normalize_acquisition(
    acq_id: int,
    parser_version: str,
    raw_file_id: int | None = None,
    header_row_override: int | None = Query(default=None, ge=0),
    data_start_marker: str = "DATA_START",
    mapping: List[dict] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    acq = await db.get(Acquisition, acq_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")
    try:
        norm_record, channels, path = await normalize_from_raw(
            db=db,
            acq=acq,
            mapping=mapping,
            data_root=Path(settings.data_root),
            parser_version=parser_version,
            raw_file_id=raw_file_id,
            header_row_override=header_row_override,
            data_start_marker=data_start_marker,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await log_action(db, "raw_file", norm_record.id, "create", user.id, notes="normalized_csv")
    return {
        "normalized_file_id": norm_record.id,
        "raw_file_id": norm_record.source_raw_file_id,
        "version_no": norm_record.version_no,
        "path": path,
        "channels_created": len(channels),
    }


@router.post("/weighing-measurements", response_model=schemas.WeighingMeasurementOut)
async def create_weighing_measurement(
    payload: schemas.WeighingMeasurementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    if payload.measured_tension_tf <= 0:
        raise HTTPException(status_code=400, detail="measured_tension_tf must be > 0")
    wm = WeighingMeasurement(**payload.dict())
    db.add(wm)
    await db.commit()
    await db.refresh(wm)
    await log_action(db, "weighing_measurement", wm.id, "create", user.id)
    return wm


@router.get("/weighing-measurements", response_model=List[schemas.WeighingMeasurementOut])
async def list_weighing_measurements(db: AsyncSession = Depends(get_db)):
    return (
        await db.execute(select(WeighingMeasurement).order_by(WeighingMeasurement.weighing_campaign_id.desc()))
    ).scalars().all()


@router.post("/cable-config-snapshots", response_model=schemas.CableConfigSnapshotOut)
async def create_snapshot(
    payload: schemas.CableConfigSnapshotCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    if payload.strands_active > payload.strands_total:
        raise HTTPException(status_code=400, detail="strands_active must be <= strands_total")
    if payload.effective_length_m <= 0 or payload.mu_value_kg_m <= 0:
        raise HTTPException(status_code=400, detail="effective_length_m and mu_value_kg_m must be > 0")
    snap = CableConfigSnapshot(**payload.dict())
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    await log_action(db, "cable_config_snapshot", snap.id, "create", user.id)
    return snap


@router.get("/cable-config-snapshots", response_model=List[schemas.CableConfigSnapshotOut])
async def list_snapshots(cable_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(CableConfigSnapshot)
    if cable_id:
        q = q.where(CableConfigSnapshot.cable_id == cable_id)
    return (await db.execute(q.order_by(CableConfigSnapshot.created_at.desc()))).scalars().all()


@router.post("/k-calibrations", response_model=schemas.KCalibrationOut)
async def create_k_calibration(
    payload: schemas.KCalibrationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    if payload.k_value <= 0:
        raise HTTPException(status_code=400, detail="k_value must be > 0")
    if payload.valid_to and payload.valid_to <= payload.valid_from:
        raise HTTPException(status_code=400, detail="valid_to must be greater than valid_from")
    existing = (
        await db.execute(select(KCalibration).where(KCalibration.cable_id == payload.cable_id))
    ).scalars().all()
    candidate = KCalibration(**payload.dict())
    validate_k_no_overlap(existing, candidate)
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    await log_action(db, "k_calibration", candidate.id, "create", user.id)
    return candidate


@router.get("/k-calibrations", response_model=List[schemas.KCalibrationOut])
async def list_k_calibrations(cable_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(KCalibration)
    if cable_id:
        q = q.where(KCalibration.cable_id == cable_id)
    return (await db.execute(q.order_by(KCalibration.valid_from.desc()))).scalars().all()


@router.post("/weighing-campaigns/{campaign_id}/attachment")
async def upload_weighing_attachment(
    campaign_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
):
    wc = await db.get(WeighingCampaign, campaign_id)
    if not wc:
        raise HTTPException(status_code=404, detail="Weighing campaign not found")
    data = await file.read()
    path, digest = save_upload(Path(settings.data_root), "attachments", file.filename, data)
    attach = WeighingAttachment(
        weighing_campaign_id=campaign_id,
        storage_path=str(path),
        filename=file.filename,
        sha256=digest,
    )
    db.add(attach)
    await db.commit()
    await db.refresh(attach)
    await log_action(db, "weighing_attachment", attach.id, "create", user.id)
    return {"id": attach.id, "sha256": digest, "path": attach.storage_path}


@router.get("/cables/{cable_id}/anomalies", response_model=schemas.AnomaliesResponse)
async def cable_anomalies(
    cable_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    z_threshold: float = Query(default=2.5, gt=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst", "reviewer", "viewer")),
):
    """Detecta valores atípicos en el historial de análisis de un tirante.

    Usa z-score sobre tensión calculada y frecuencia fundamental.
    Un resultado se marca como anomalía si alguna de sus métricas supera z_threshold.
    Requiere al menos 3 resultados para estadísticas significativas.
    """
    cable = await db.get(Cable, cable_id)
    if not cable:
        raise HTTPException(status_code=404, detail="Cable not found")

    result = await detect_anomalies(
        db=db,
        cable_id=cable_id,
        cable_name=cable.nombre_en_puente,
        date_from=date_from,
        date_to=date_to,
        z_threshold=z_threshold,
    )
    return result


@router.get("/bridges/{bridge_id}/semaforo", response_model=schemas.SemaforoResponse)
async def semaforo(bridge_id: int, acquisition_id: int, top_n: int | None = Query(None, gt=0), db: AsyncSession = Depends(get_db)):
    acq = await db.get(Acquisition, acquisition_id)
    if not acq:
        raise HTTPException(status_code=404, detail="Acquisition not found")

    stmt = (
        select(AnalysisResult, Cable)
        .join(AnalysisRun, AnalysisResult.analysis_run_id == AnalysisRun.id)
        .join(Cable, Cable.id == AnalysisResult.cable_id)
        .where(AnalysisRun.acquisition_id == acquisition_id, Cable.bridge_id == bridge_id)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return schemas.SemaforoResponse(bridge_id=bridge_id, acquisition_id=acquisition_id, total=0, exceden=0, items=[])

    items = []
    exceden = 0
    for res, cable in rows:
        states = (
            await db.execute(select(CableStateVersion).where(CableStateVersion.cable_id == cable.id))
        ).scalars().all()
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
