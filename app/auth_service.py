from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from typing import Iterator, Optional, Tuple

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


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(candidate: str, hashed: str) -> bool:
    return hash_password(candidate) == hashed


def ensure_default_admin(
    email: str | None = None, password: str | None = None, session: Session | None = None
) -> Tuple[bool, str]:
    """
    Crea un usuario administrador por defecto si no existe ya un administrador.

    Retorna una tupla (created, message) indicando si se creó el usuario.
    """

    admin_email = email or os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    admin_password = password or os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    with session_scope(session) as db:
        existing_admin = db.scalars(select(User).where(User.role == "Admin")).first()
        if existing_admin:
            return False, f"Ya existe un administrador con el correo {existing_admin.email}."

        existing_email = get_user_by_email(db, admin_email)
        if existing_email:
            return (
                False,
                f"El correo {admin_email} ya está registrado con rol {existing_email.role}.",
            )

        user = create_user(
            email=admin_email,
            hashed_password=hash_password(admin_password),
            role="Admin",
            session=db,
        )
        return True, f"Usuario administrador creado con correo {user.email}."

