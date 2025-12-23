from datetime import datetime, timedelta, timezone

import pytest

from app.services.business import (
    CableStateVersion,
    KCalibration,
    SensorInstallation,
    effective_fu,
    select_cable_state_version,
    select_k_for_timestamp,
    validate_installations_no_overlap,
)


def ts(hours: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)


def test_select_cable_state_version_prefers_covering():
    states = [
        CableStateVersion(1, ts(0), ts(10), 10.0, 7, 7, None, 100.0),
        CableStateVersion(1, ts(10), None, 10.0, 7, 7, None, 100.0),
    ]
    chosen = select_cable_state_version(states, ts(5))
    assert chosen.valid_from == ts(0)


def test_select_cable_state_version_falls_back_to_latest_before():
    states = [
        CableStateVersion(1, ts(0), ts(10), 10.0, 7, 7, None, 100.0),
        CableStateVersion(1, ts(20), None, 10.0, 7, 7, None, 100.0),
    ]
    chosen = select_cable_state_version(states, ts(15))
    assert chosen.valid_from == ts(0)


def test_select_cable_state_version_raises_on_overlap():
    states = [
        CableStateVersion(1, ts(0), ts(20), 10.0, 7, 7, None, 100.0),
        CableStateVersion(1, ts(10), None, 10.0, 7, 7, None, 100.0),
    ]
    with pytest.raises(ValueError):
        select_cable_state_version(states, ts(12))


def test_select_k_for_timestamp_chooses_covering():
    calibrations = [
        KCalibration(1, 1.5, ts(0), ts(10)),
        KCalibration(1, 2.0, ts(10), None),
    ]
    chosen = select_k_for_timestamp(calibrations, ts(11))
    assert chosen.k_value == 2.0


def test_select_k_for_timestamp_latest_before_when_no_cover():
    calibrations = [
        KCalibration(1, 1.5, ts(0), ts(10)),
        KCalibration(1, 2.0, ts(20), None),
    ]
    chosen = select_k_for_timestamp(calibrations, ts(15))
    assert chosen.k_value == 1.5


def test_select_k_for_timestamp_raises_on_overlap():
    calibrations = [
        KCalibration(1, 1.5, ts(0), ts(15)),
        KCalibration(1, 2.0, ts(10), None),
    ]
    with pytest.raises(ValueError):
        select_k_for_timestamp(calibrations, ts(12))


def test_validate_installations_no_overlap_passes():
    installations = [
        SensorInstallation(1, 1, ts(0), ts(10)),
        SensorInstallation(1, 2, ts(10), None),
    ]
    validate_installations_no_overlap(installations)  # should not raise


def test_validate_installations_no_overlap_detects_overlap():
    installations = [
        SensorInstallation(1, 1, ts(0), ts(10)),
        SensorInstallation(1, 2, ts(9), None),
    ]
    with pytest.raises(ValueError):
        validate_installations_no_overlap(installations)


def test_effective_fu_uses_override_when_present():
    state = CableStateVersion(1, ts(0), None, 10.0, 7, 7, 120.0, 100.0)
    assert effective_fu(state) == 120.0


def test_effective_fu_defaults_to_strand_fu():
    state = CableStateVersion(1, ts(0), None, 10.0, 7, 7, None, 100.0)
    assert effective_fu(state) == 100.0
