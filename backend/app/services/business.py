from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class CableStateVersion:
    cable_id: int
    valid_from: datetime
    valid_to: Optional[datetime]
    length_effective_m: float
    strands_active: int
    strands_total: int
    fu_override: Optional[float]
    strand_type_fu_default: float


@dataclass(frozen=True)
class KCalibration:
    cable_id: int
    k_value: float
    valid_from: datetime
    valid_to: Optional[datetime]
    calibration_id: Optional[int] = None
    algorithm_version: Optional[str] = None


@dataclass(frozen=True)
class SensorInstallation:
    sensor_id: int
    cable_id: int
    installed_from: datetime
    installed_to: Optional[datetime]


def select_cable_state_version(
    states: Sequence[CableStateVersion], at: datetime
) -> CableStateVersion:
    """
    Picks the cable state version whose validity range includes `at`.
    If none cover the date, the latest version whose valid_from <= at is returned.
    Raises ValueError on ambiguity (overlaps) or when nothing qualifies.
    """
    relevant = [s for s in states if s.valid_from <= at and (s.valid_to is None or s.valid_to >= at)]
    if len(relevant) > 1:
        raise ValueError("Multiple cable_state_versions overlap for the given timestamp")
    if len(relevant) == 1:
        return relevant[0]

    candidates = [s for s in states if s.valid_from <= at]
    if not candidates:
        raise ValueError("No cable_state_version found before the given timestamp")
    return sorted(candidates, key=lambda s: s.valid_from)[-1]


def select_k_for_timestamp(calibrations: Sequence[KCalibration], at: datetime) -> KCalibration:
    """
    Implements the validity-selection rule for K:
    - Prefer the calibration whose validity window covers `at`.
    - If none cover, choose the most recent calibration whose valid_from <= at.
    Raises ValueError on overlaps or when no calibration exists before `at`.
    """
    covering = [k for k in calibrations if k.valid_from <= at and (k.valid_to is None or k.valid_to >= at)]
    if len(covering) > 1:
        raise ValueError("Multiple K calibrations overlap for the given timestamp")
    if covering:
        return covering[0]

    candidates = [k for k in calibrations if k.valid_from <= at]
    if not candidates:
        raise ValueError("No K calibration found before the given timestamp")
    return sorted(candidates, key=lambda k: k.valid_from)[-1]


def validate_installations_no_overlap(installations: Iterable[SensorInstallation]) -> None:
    """
    Ensures a sensor is not installed on multiple cables at the same time.
    Uses closed-open intervals [from, to).
    Raises ValueError with a short message on overlap.
    """
    by_sensor: dict[int, List[SensorInstallation]] = {}
    for inst in installations:
        by_sensor.setdefault(inst.sensor_id, []).append(inst)

    for sensor_id, insts in by_sensor.items():
        sorted_insts = sorted(insts, key=lambda x: x.installed_from)
        for current, nxt in zip(sorted_insts, sorted_insts[1:]):
            current_end = current.installed_to or datetime.max
            if nxt.installed_from < current_end:
                raise ValueError(
                    f"Sensor {sensor_id} has overlapping installations on cables "
                    f"{current.cable_id} and {nxt.cable_id}"
                )


def effective_fu(state: CableStateVersion) -> float:
    """Return Fu for the cable state following override/default rule."""
    return state.fu_override if state.fu_override is not None else state.strand_type_fu_default


def validate_k_no_overlap(calibrations: Iterable[KCalibration], new_one: KCalibration) -> None:
    """
    Ensure no overlapping validity ranges for the same cable.
    Closed-open intervals [valid_from, valid_to or infinity).
    Raises ValueError on overlap.
    """
    for existing in calibrations:
        existing_id = getattr(existing, "calibration_id", None) or getattr(existing, "id", None)
        new_id = getattr(new_one, "calibration_id", None) or getattr(new_one, "id", None)
        if existing_id is not None and new_id is not None and existing_id == new_id:
            continue
        if existing.cable_id != new_one.cable_id:
            continue
        start_a = existing.valid_from
        end_a = existing.valid_to or datetime.max
        start_b = new_one.valid_from
        end_b = new_one.valid_to or datetime.max
        if start_a < end_b and start_b < end_a:
            raise ValueError("Overlapping K calibration validity range for this cable")
