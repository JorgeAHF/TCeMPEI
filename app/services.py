"""Enrutador de servicios legacy.

Los servicios se separaron en módulos especializados para aislar la lógica de
validación y el manejo de sesiones respecto al dashboard de Dash. Este módulo
mantiene importaciones de conveniencia y compatibilidad hacia el código
existente.
"""

from .auth_service import create_user, get_user_by_email
from .catalog_service import compute_tension_from_f0, select_k_calibration
from .cable_version_service import create_cable_state_version, select_cable_state_for_date
from .installation_service import register_installation, validate_installation_overlap
from .validation_service import (
    ValidationError,
    ensure_cable_version_window,
    ensure_installation_window_available,
    ensure_no_open_cable_version,
)

__all__ = [
    "compute_tension_from_f0",
    "create_cable_state_version",
    "create_user",
    "get_user_by_email",
    "register_installation",
    "select_cable_state_for_date",
    "select_k_calibration",
    "validate_installation_overlap",
    "ValidationError",
    "ensure_cable_version_window",
    "ensure_installation_window_available",
    "ensure_no_open_cable_version",
]

