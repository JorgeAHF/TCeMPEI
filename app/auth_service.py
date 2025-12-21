from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session_local
from .models import User
from .validation_service import ValidationError

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


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.scalars(select(User).where(User.email == email)).first()


def create_user(email: str, hashed_password: str, role: str = "Consulta", session: Session | None = None) -> User:
    """Crea un usuario validando unicidad del correo."""

    with session_scope(session) as db:
        existing = get_user_by_email(db, email)
        if existing:
            raise ValidationError("El correo ya está registrado.")
        user = User(email=email, hashed_password=hashed_password, role=role)
        db.add(user)
        db.flush()
        return user

