from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CableStateVersion, KCalibration, SensorInstallation


def select_cable_state_for_date(session: Session, cable_id: int, at: datetime) -> Optional[CableStateVersion]:
    """Select the active cable state version for a given timestamp.

    Chooses the record where valid_from <= at and (valid_to is null or valid_to >= at).
    If none matches, returns the most recent version before the date.
    """

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


def select_k_calibration(session: Session, cable_id: int, at: datetime) -> Optional[KCalibration]:
    """Select K per business rule (valid range or latest before date)."""

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


def validate_installation_overlap(session: Session, sensor_id: int, candidate_from: datetime, candidate_to: datetime | None) -> bool:
    """Returns True when there is no overlap for the sensor installation."""

    candidate_end = candidate_to or datetime.max
    overlapping = session.scalars(
        select(SensorInstallation).where(
            SensorInstallation.sensor_id == sensor_id,
            SensorInstallation.installed_from <= candidate_end,
            (SensorInstallation.installed_to.is_(None))
            | (SensorInstallation.installed_to >= candidate_from),
        )
    ).first()
    return overlapping is None


def compute_tension_from_f0(f0_hz: float, k_value: float) -> float:
    return f0_hz ** 2 * k_value


__all__ = [
    "select_cable_state_for_date",
    "select_k_calibration",
    "validate_installation_overlap",
    "compute_tension_from_f0",
]
