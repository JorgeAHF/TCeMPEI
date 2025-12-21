from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db import Base, get_engine, get_session_local
from app.models import (
    Cable,
    CableStateVersion,
    KCalibration,
    SensorInstallation,
    StrandType,
    Bridge,
    User,
)
from app.services import (
    ValidationError,
    create_cable_state_version,
    register_installation,
    select_cable_state_for_date,
    select_k_calibration,
    validate_installation_overlap,
)


def seed_basic(session: Session):
    user = User(email="test@example.com", hashed_password="x", role="Admin")
    bridge = Bridge(nombre="Puente 1")
    cable = Cable(bridge=bridge, nombre_en_puente="C1")
    strand_type = StrandType(
        nombre="7T", diametro_mm=15.2, area_mm2=140.0, e_mpa=200000, fu_default=250.0
    )
    session.add_all([user, bridge, cable, strand_type])
    session.flush()
    return user, bridge, cable, strand_type


def test_select_cable_state_prefers_open_range(tmp_path):
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    older = CableStateVersion(
        cable_id=cable.id,
        valid_from=datetime(2020, 1, 1),
        valid_to=datetime(2021, 1, 1),
        length_effective_m=100.0,
        strands_total=10,
        strands_active=8,
        strands_inactive=2,
        strand_type_id=strand_type.id,
        diametro_mm=15.2,
        area_mm2=140.0,
        e_mpa=200000,
        mu_total_kg_m=120.0,
        mu_active_basis_kg_m=100.0,
        design_tension_tf=500.0,
    )
    open_version = CableStateVersion(
        cable_id=cable.id,
        valid_from=datetime(2021, 1, 2),
        valid_to=None,
        length_effective_m=110.0,
        strands_total=10,
        strands_active=9,
        strands_inactive=1,
        strand_type_id=strand_type.id,
        diametro_mm=15.2,
        area_mm2=140.0,
        e_mpa=200000,
        mu_total_kg_m=125.0,
        mu_active_basis_kg_m=105.0,
        design_tension_tf=520.0,
    )
    session.add_all([older, open_version])
    session.commit()

    found = select_cable_state_for_date(session, cable.id, datetime(2022, 5, 1))
    assert found.id == open_version.id

    past = select_cable_state_for_date(session, cable.id, datetime(2020, 6, 1))
    assert past.id == older.id


def test_select_k_calibration_chooses_valid_range():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    k1 = KCalibration(
        cable_id=cable.id,
        derived_from_weighing_measurement_id=1,
        config_snapshot_id=1,
        k_value=0.5,
        valid_from=datetime(2020, 1, 1),
        valid_to=datetime(2020, 12, 31),
        algorithm_version="1.0.0",
        computed_by_user_id=user.id,
    )
    k2 = KCalibration(
        cable_id=cable.id,
        derived_from_weighing_measurement_id=2,
        config_snapshot_id=2,
        k_value=0.55,
        valid_from=datetime(2021, 1, 1),
        valid_to=None,
        algorithm_version="1.0.0",
        computed_by_user_id=user.id,
    )
    session.add_all([k1, k2])
    session.commit()

    assert select_k_calibration(session, cable.id, datetime(2021, 6, 1)).id == k2.id
    assert select_k_calibration(session, cable.id, datetime(2019, 12, 1)) is None


def test_validate_installation_overlap():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    inst = SensorInstallation(
        sensor_id=1,
        cable_id=cable.id,
        installed_from=datetime(2022, 1, 1),
        installed_to=datetime(2022, 6, 1),
        height_m=5.0,
    )
    session.add(inst)
    session.commit()

    assert not validate_installation_overlap(
        session, 1, datetime(2022, 3, 1), datetime(2022, 4, 1)
    )
    assert validate_installation_overlap(session, 1, datetime(2023, 1, 1), None)


def test_register_installation_rejects_overlap():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    session.add(
        SensorInstallation(
            sensor_id=1,
            cable_id=cable.id,
            installed_from=datetime(2024, 1, 1),
            installed_to=datetime(2024, 6, 1),
            height_m=6.0,
        )
    )
    session.commit()

    with pytest.raises(ValidationError):
        register_installation(
            SensorInstallation(
                sensor_id=1,
                cable_id=cable.id,
                installed_from=datetime(2024, 5, 1),
                installed_to=None,
                height_m=7.0,
            ),
            session=session,
        )


def test_register_installation_rejects_overlap_with_open_range():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    session.add(
        SensorInstallation(
            sensor_id=1,
            cable_id=cable.id,
            installed_from=datetime(2024, 3, 1),
            installed_to=None,
            height_m=6.0,
        )
    )
    session.commit()

    with pytest.raises(ValidationError):
        register_installation(
            SensorInstallation(
                sensor_id=1,
                cable_id=cable.id,
                installed_from=datetime(2024, 5, 1),
                installed_to=datetime(2024, 6, 1),
                height_m=7.0,
            ),
            session=session,
        )


def test_create_cable_state_version_guards_open_ranges():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    existing = CableStateVersion(
        cable_id=cable.id,
        valid_from=datetime(2024, 1, 1),
        valid_to=None,
        length_effective_m=100.0,
        strands_total=10,
        strands_active=8,
        strands_inactive=2,
        strand_type_id=strand_type.id,
        diametro_mm=15.2,
        area_mm2=140.0,
        e_mpa=200000,
        mu_total_kg_m=120.0,
        mu_active_basis_kg_m=100.0,
        design_tension_tf=500.0,
        antivandalic_enabled=True,
        antivandalic_length_m=10.0,
    )
    session.add(existing)
    session.commit()

    with pytest.raises(ValidationError):
        create_cable_state_version(
            CableStateVersion(
                cable_id=cable.id,
                valid_from=datetime(2024, 7, 1),
                valid_to=None,
                length_effective_m=101.0,
                strands_total=10,
                strands_active=8,
                strands_inactive=2,
                strand_type_id=strand_type.id,
                diametro_mm=15.2,
                area_mm2=140.0,
                e_mpa=200000,
                mu_total_kg_m=121.0,
                mu_active_basis_kg_m=101.0,
                design_tension_tf=505.0,
                antivandalic_enabled=True,
                antivandalic_length_m=20.0,
            ),
            session=session,
        )


def test_create_cable_state_version_validates_antivandalic():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    with pytest.raises(ValidationError):
        create_cable_state_version(
            CableStateVersion(
                cable_id=cable.id,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                length_effective_m=100.0,
                strands_total=10,
                strands_active=8,
                strands_inactive=2,
                strand_type_id=strand_type.id,
                diametro_mm=15.2,
                area_mm2=140.0,
                e_mpa=200000,
                mu_total_kg_m=120.0,
                mu_active_basis_kg_m=100.0,
                design_tension_tf=500.0,
                antivandalic_enabled=True,
                antivandalic_length_m=None,
            ),
            session=session,
        )


def test_create_cable_state_version_blocks_overlaps():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    session.add(
        CableStateVersion(
            cable_id=cable.id,
            valid_from=datetime(2023, 1, 1),
            valid_to=datetime(2023, 12, 31),
            length_effective_m=100.0,
            strands_total=10,
            strands_active=8,
            strands_inactive=2,
            strand_type_id=strand_type.id,
            diametro_mm=15.2,
            area_mm2=140.0,
            e_mpa=200000,
            mu_total_kg_m=120.0,
            mu_active_basis_kg_m=100.0,
            design_tension_tf=500.0,
            antivandalic_enabled=False,
        )
    )
    session.commit()

    with pytest.raises(ValidationError):
        create_cable_state_version(
            CableStateVersion(
                cable_id=cable.id,
                valid_from=datetime(2023, 6, 1),
                valid_to=datetime(2024, 6, 1),
                length_effective_m=101.0,
                strands_total=10,
                strands_active=8,
                strands_inactive=2,
                strand_type_id=strand_type.id,
                diametro_mm=15.2,
                area_mm2=140.0,
                e_mpa=200000,
                mu_total_kg_m=121.0,
                mu_active_basis_kg_m=101.0,
                design_tension_tf=505.0,
                antivandalic_enabled=False,
            ),
            session=session,
        )


def test_create_cable_state_version_validates_antivandalic_length_bounds():
    url = "sqlite+pysqlite:///:memory:"
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    SessionLocal = get_session_local(url, engine=engine)
    session = SessionLocal()
    user, bridge, cable, strand_type = seed_basic(session)

    with pytest.raises(ValidationError):
        create_cable_state_version(
            CableStateVersion(
                cable_id=cable.id,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                length_effective_m=100.0,
                strands_total=10,
                strands_active=8,
                strands_inactive=2,
                strand_type_id=strand_type.id,
                diametro_mm=15.2,
                area_mm2=140.0,
                e_mpa=200000,
                mu_total_kg_m=120.0,
                mu_active_basis_kg_m=100.0,
                design_tension_tf=500.0,
                antivandalic_enabled=True,
                antivandalic_length_m=-1.0,
            ),
            session=session,
        )

    with pytest.raises(ValidationError):
        create_cable_state_version(
            CableStateVersion(
                cable_id=cable.id,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                length_effective_m=10.0,
                strands_total=10,
                strands_active=8,
                strands_inactive=2,
                strand_type_id=strand_type.id,
                diametro_mm=15.2,
                area_mm2=140.0,
                e_mpa=200000,
                mu_total_kg_m=120.0,
                mu_active_basis_kg_m=100.0,
                design_tension_tf=500.0,
                antivandalic_enabled=True,
                antivandalic_length_m=20.0,
            ),
            session=session,
        )

