from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy.orm import Session

from .db import get_session_local
from .models import SensorInstallation
from .validation_service import ValidationError, ensure_installation_window_available

SessionLocal = get_session_local()


@contextmanager
def session_scope(session: Session | None = None) -> Iterator[Session]:
    managed = session is None
    session = session or SessionLocal()
    try:
        yield session
        if managed:
            session.commit()
    except Exception:
        if managed:
            session.rollback()
        raise
    finally:
        if managed:
            session.close()


def validate_installation_overlap(
    session: Session, sensor_id: int, candidate_from: datetime, candidate_to: datetime | None
) -> bool:
    """Retorna True si no hay traslapes, False en caso contrario."""

    try:
        ensure_installation_window_available(session, sensor_id, candidate_from, candidate_to)
        return True
    except ValidationError:
        return False


def register_installation(installation: SensorInstallation, session: Session | None = None) -> SensorInstallation:
    """Crea una instalación validando que no existan solapes."""

    with session_scope(session) as db:
        ensure_installation_window_available(
            db, installation.sensor_id, installation.installed_from, installation.installed_to
        )
        db.add(installation)
        db.flush()
        return installation

