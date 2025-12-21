from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session_local
from .models import CableStateVersion
from .validation_service import ValidationError, ensure_cable_version_window

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


def select_cable_state_for_date(
    session: Session, cable_id: int, at: datetime
) -> Optional[CableStateVersion]:
    """Selecciona la versión activa del tirante para una fecha."""

    range_match = session.scalars(
        select(CableStateVersion)
        .where(
            CableStateVersion.cable_id == cable_id,
            CableStateVersion.valid_from <= at,
            (CableStateVersion.valid_to.is_(None) | (CableStateVersion.valid_to >= at)),
        )
        .order_by(CableStateVersion.valid_from.desc())
    ).first()
    if range_match:
        return range_match

    return session.scalars(
        select(CableStateVersion)
        .where(
            CableStateVersion.cable_id == cable_id,
            CableStateVersion.valid_from <= at,
        )
        .order_by(CableStateVersion.valid_from.desc())
    ).first()


def create_cable_state_version(candidate: CableStateVersion, session: Session | None = None) -> CableStateVersion:
    """Inserta una versión de tirante validando solapes y reglas de antivandálico."""

    with session_scope(session) as db:
        ensure_cable_version_window(db, candidate)
        db.add(candidate)
        db.flush()
        return candidate

