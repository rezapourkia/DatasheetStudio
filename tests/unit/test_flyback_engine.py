"""Numerical and validation tests for the pure Python DCM engine."""

from copy import deepcopy
import math

import pytest

from datasheet_studio.tools.flyback_designer.defaults import (
    SAMPLE_CORES,
    SAMPLE_PARTS,
    default_project,
)
from datasheet_studio.tools.flyback_designer.engine import (
    ComponentSpec,
    OutputSpec,
    calculate,
)
from datasheet_studio.tools.flyback_designer.persistence import (
    FlybackProjectFileError,
    bundle_from_dict,
    bundle_to_dict,
    load_bundle,
    save_bundle,
)


def run(project=None, core=None):
    return calculate(
        project or default_project(),
        core or deepcopy(SAMPLE_CORES[1]),
        SAMPLE_PARTS,
    )


def test_default_reference_values_are_reproduced():
    result = run()

    assert result.errors == ()
    assert result.magnetising_inductance_h * 1e6 == pytest.approx(379.5128, rel=1e-5)
    assert result.primary_peak_a == pytest.approx(1.540436, rel=1e-5)
    assert result.primary_turns == 74
    assert result.outputs[0].turns == 12
    assert result.flux_density_t == pytest.approx(0.197505, rel=1e-5)
    assert result.window_fill_ratio == pytest.approx(0.4661, rel=2e-3)
    assert result.snubber_resistance_ohm / 1000 == pytest.approx(18.527, rel=2e-3)
    assert result.snubber_capacitance_f * 1e9 == pytest.approx(8.304, rel=2e-3)


def test_energy_balance_and_primary_volt_seconds():
    project = default_project()
    result = run(project)
    frequency_hz = project.frequency_khz * 1000

    assert (
        0.5
        * result.magnetising_inductance_h
        * result.primary_peak_a**2
        * frequency_hz
        == pytest.approx(result.output_power_w / (project.efficiency_pct / 100))
    )
    assert result.magnetising_inductance_h * result.primary_peak_a == pytest.approx(
        project.vin_min_v * project.duty / frequency_hz
    )


def test_integer_turns_hold_flux_target_and_al_identity():
    project = default_project()
    for core in SAMPLE_CORES:
        result = run(project, deepcopy(core))
        assert isinstance(result.primary_turns, int)
        assert result.flux_density_t <= project.b_target_t
        assert result.al_nh_turn2 * result.primary_turns**2 == pytest.approx(
            result.magnetising_inductance_h * 1e9
        )


def test_larger_core_reduces_turns_and_window_occupation():
    small = run(core=deepcopy(SAMPLE_CORES[0]))
    large = run(core=deepcopy(SAMPLE_CORES[-1]))

    assert large.primary_turns < small.primary_turns
    assert large.window_fill_ratio < small.window_fill_ratio


def test_expected_limit_warnings_are_not_suppressed():
    project = default_project()
    project.current_limit_a = 0.1
    project.fill_factor = 0.01
    core = deepcopy(SAMPLE_CORES[1])
    core.bmax_t = 0.01
    result = run(project, core)

    assert any("جریان پیک" in warning for warning in result.warnings)
    assert any("جا نمی‌شود" in warning for warning in result.warnings)
    assert any("چگالی شار" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vin_min_v", 0),
        ("frequency_khz", math.nan),
        ("efficiency_pct", 100),
        ("duty", 1),
        ("leakage_pct", -1),
        ("current_density_a_mm2", math.inf),
    ],
)
def test_invalid_inputs_stop_before_calculation(field, value):
    project = default_project()
    setattr(project, field, value)

    assert run(project).errors


def test_no_outputs_is_invalid():
    project = default_project()
    project.outputs = []

    assert run(project).errors


def test_boolean_is_not_accepted_as_a_numeric_input():
    project = default_project()
    project.duty = True

    assert run(project).errors


def test_invalid_component_parameters_return_errors_instead_of_crashing():
    bad_parts = (
        ComponentSpec(
            "dk124",
            "DK124",
            "ic",
            {"current_limit_a": "not-a-number"},
        ),
    )

    result = calculate(default_project(), deepcopy(SAMPLE_CORES[1]), bad_parts)

    assert result.errors
    assert any("پارامترهای عددی قطعه" in error for error in result.errors)


def test_duplicate_component_ids_are_rejected():
    duplicate_parts = (deepcopy(SAMPLE_PARTS[0]), deepcopy(SAMPLE_PARTS[0]))

    result = calculate(default_project(), deepcopy(SAMPLE_CORES[1]), duplicate_parts)

    assert any("شناسه قطعه تکراری" in error for error in result.errors)


def test_unhashable_project_component_id_is_rejected_safely():
    project = default_project()
    project.ic_id = []

    result = run(project)

    assert result.errors


def test_multioutput_preserves_requested_power_and_reference_output():
    project = default_project()
    project.outputs.append(OutputSpec("5V", 5, 1, 0.5))
    result = run(project)

    assert result.output_power_w == pytest.approx(29)
    assert len(result.outputs) == 2
    assert result.outputs[0].ideal_voltage_v == pytest.approx(
        project.outputs[0].voltage_v
    )


def test_rcd_power_resistance_and_ripple_are_consistent():
    project = default_project()
    result = run(project)

    assert project.clamp_above_bus_v**2 / result.snubber_resistance_ohm == pytest.approx(
        result.snubber_power_w
    )
    assert 1 / (
        result.snubber_resistance_ohm
        * result.snubber_capacitance_f
        * project.frequency_khz
        * 1000
    ) == pytest.approx(project.clamp_ripple_pct / 100)

    project.clamp_above_bus_v = 1
    invalid_clamp = run(project)
    assert invalid_clamp.snubber_resistance_ohm is None
    assert any("کلمپ" in warning for warning in invalid_clamp.warnings)


def test_bjt_and_mosfet_conduction_models_are_separate():
    project = default_project()
    project.switch_type = "bjt"
    project.vce_v = 1.2
    bjt = run(project)
    assert bjt.switch_conduction_loss_w == pytest.approx(
        1.2 * bjt.primary_peak_a * project.duty / 2
    )

    project.switch_type = "mosfet"
    mosfet = run(project)
    assert mosfet.switch_conduction_loss_w == pytest.approx(
        mosfet.primary.rms_a**2 * 2
    )


def test_output_diode_and_capacitor_warnings_work():
    project = default_project()
    project.outputs[0].voltage_v = 150
    project.outputs[0].current_a = 6
    result = run(project)

    assert any("معکوس" in warning for warning in result.warnings)
    assert any("نامی دیود" in warning for warning in result.warnings)
    assert any("خازن" in warning for warning in result.warnings)


def test_rounded_wire_area_carries_rms_current():
    project = default_project()
    result = run(project)

    windings = [result.primary, *(output.winding for output in result.outputs)]
    assert all(
        winding.rms_a / winding.copper_area_mm2
        <= project.current_density_a_mm2 + 1e-9
        for winding in windings
    )


def test_project_json_round_trip(tmp_path):
    project = default_project()
    project.outputs.append(OutputSpec("کمکی", 15, 0.2, 0.7))
    core = deepcopy(SAMPLE_CORES[2])
    path = tmp_path / "design.flyback.json"

    save_bundle(path, project, core, SAMPLE_PARTS)
    loaded_project, loaded_core, loaded_parts = load_bundle(path)

    assert loaded_project == project
    assert loaded_core == core
    assert loaded_parts == SAMPLE_PARTS


def test_project_bundle_rejects_unknown_schema():
    data = bundle_to_dict(default_project(), deepcopy(SAMPLE_CORES[1]), SAMPLE_PARTS)
    data["schema_version"] = 999

    with pytest.raises(FlybackProjectFileError):
        bundle_from_dict(data)
