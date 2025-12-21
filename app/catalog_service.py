from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session_local
from .models import KCalibration

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


def select_k_calibration(session: Session, cable_id: int, at: datetime) -> Optional[KCalibration]:
    """Selecciona la calibración K vigente o la última previa a la fecha."""

    range_match = session.scalars(
        select(KCalibration)
        .where(
            KCalibration.cable_id == cable_id,
            KCalibration.valid_from <= at,
            (KCalibration.valid_to.is_(None) | (KCalibration.valid_to >= at)),
        )
        .order_by(KCalibration.valid_from.desc())
    ).first()
    if range_match:
        return range_match

    return session.scalars(
        select(KCalibration)
        .where(KCalibration.cable_id == cable_id, KCalibration.valid_from <= at)
        .order_by(KCalibration.valid_from.desc())
    ).first()


def compute_tension_from_f0(f0_hz: float, k_value: float) -> float:
    return f0_hz ** 2 * k_value

