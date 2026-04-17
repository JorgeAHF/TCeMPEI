from app.models import Acquisition, CableStateVersion, StrandType, WeighingCampaign, WeighingMeasurement


def test_uppercase_domain_fields_map_to_lowercase_sql_columns():
    expected_column_names = {
        (StrandType, "E_MPa"): "e_mpa",
        (StrandType, "Fu_default"): "fu_default",
        (CableStateVersion, "E_MPa"): "e_mpa",
        (CableStateVersion, "Fu_override"): "fu_override",
        (Acquisition, "Fs_Hz"): "fs_hz",
        (WeighingCampaign, "temperature_C"): "temperature_c",
        (WeighingMeasurement, "measured_temperature_C"): "measured_temperature_c",
    }

    for (model, attr_name), expected_name in expected_column_names.items():
        column = getattr(model, attr_name).property.columns[0]
        assert column.name == expected_name
