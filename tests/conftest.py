import os

import pytest

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "Se requiere TEST_DATABASE_URL apuntando a PostgreSQL para ejecutar las pruebas.",
        allow_module_level=True,
    )

# Configuración de base de datos para las pruebas antes de importar la app
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

from app.db import Base, get_engine, get_session_local


@pytest.fixture
def session():
    engine = get_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(TEST_DATABASE_URL, engine=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
