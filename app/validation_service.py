from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CableStateVersion, SensorInstallation


class ValidationError(ValueError):
    """Error de validación de reglas de negocio."""


def _overlaps(candidate_from: datetime, candidate_to: datetime, other_from: datetime, other_to: datetime | None) -> bool:
    other_end = other_to or datetime.max
    candidate_end = candidate_to or datetime.max
    return candidate_from <= other_end and candidate_end >= other_from


def ensure_installation_window_available(
    session: Session, sensor_id: int, candidate_from: datetime, candidate_to: datetime | None
) -> None:
    """Valida que no existan instalaciones traslapadas para un sensor."""

    existing = session.scalars(
        select(SensorInstallation).where(SensorInstallation.sensor_id == sensor_id)
    ).all()
    for installation in existing:
        if _overlaps(candidate_from, candidate_to, installation.installed_from, installation.installed_to):
            raise ValidationError("El sensor ya tiene una instalación en el rango indicado.")


def ensure_no_open_cable_version(session: Session, cable_id: int) -> None:
    """Evita múltiples versiones abiertas del mismo tirante."""

    open_version = session.scalars(
        select(CableStateVersion).where(
            CableStateVersion.cable_id == cable_id,
            CableStateVersion.valid_to.is_(None),
        )
    ).first()
    if open_version:
        raise ValidationError("Ya existe una versión abierta para el tirante.")


def ensure_cable_version_window(session: Session, candidate: CableStateVersion) -> None:
    """Valida solapes y reglas de antivandálico para versiones de tirante."""

    if candidate.antivandalic_enabled:
        if candidate.antivandalic_length_m is None or candidate.antivandalic_length_m <= 0:
            raise ValidationError("La longitud antivandálica debe ser mayor a cero cuando está habilitada.")
        if candidate.antivandalic_length_m > candidate.length_effective_m:
            raise ValidationError("La longitud antivandálica no puede exceder la longitud efectiva.")

    if candidate.valid_to is None:
        ensure_no_open_cable_version(session, candidate.cable_id)

    overlapping = session.scalars(
        select(CableStateVersion).where(CableStateVersion.cable_id == candidate.cable_id)
    ).all()
    for version in overlapping:
        if _overlaps(candidate.valid_from, candidate.valid_to, version.valid_from, version.valid_to):
            raise ValidationError("El rango de vigencia se solapa con otra versión del tirante.")

