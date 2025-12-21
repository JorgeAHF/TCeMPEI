import pytest

from app.auth_service import (
    create_user,
    ensure_default_admin,
    hash_password,
    verify_password,
)
from app.db import Base, get_engine, get_session_local
from app.models import User
from app.validation_service import ValidationError


def setup_session():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    return SessionLocal()


def test_ensure_default_admin_creates_admin_if_missing():
    session = setup_session()

    created, message = ensure_default_admin(
        email="admin@test.com", password="secret", session=session
    )

    assert created
    assert "admin@test.com" in message
    admin = session.query(User).filter_by(role="Admin").one()
    assert admin.email == "admin@test.com"
    assert verify_password("secret", admin.hashed_password)


def test_ensure_default_admin_is_idempotent_when_admin_exists():
    session = setup_session()
    session.add(User(email="first@admin.com", hashed_password="x", role="Admin"))
    session.commit()

    created, message = ensure_default_admin(session=session)

    assert not created
    assert "Ya existe un administrador" in message
    assert session.query(User).filter_by(role="Admin").count() == 1


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("plaintext")
    assert hashed != "plaintext"
    assert verify_password("plaintext", hashed)
    assert not verify_password("wrong", hashed)


def test_create_user_rejects_duplicate_email():
    session = setup_session()

    create_user(email="dup@test.com", hashed_password="abc", session=session)

    with pytest.raises(ValidationError):
        create_user(email="dup@test.com", hashed_password="xyz", session=session)
