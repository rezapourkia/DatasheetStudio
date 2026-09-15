"""Domain-v2 tests: unbounded outputs, scenarios, upgrade (Phase 11)."""

import pytest

from datasheet_studio.tools.flyback_designer.engine import (
    MAX_OUTPUTS,
    FlybackProject,
    OutputSpec,
    ScenarioSpec,
    calculate,
    power_summary,
)
from datasheet_studio.tools.flyback_designer.persistence import (
    bundle_from_dict,
    bundle_to_dict,
)
from datasheet_studio.tools.flyback_designer.defaults import default_core


def test_sixty_four_outputs_are_accepted_nine_rejected():
    project = FlybackProject(
        outputs=[OutputSpec(f"out{i}", 5.0 + i, 0.1) for i in range(MAX_OUTPUTS)]
    )
    result = calculate(project, default_core())
    assert result.errors == ()

    too_many = FlybackProject(
        outputs=[OutputSpec(f"out{i}", 5.0, 0.1) for i in range(MAX_OUTPUTS + 1)]
    )
    assert calculate(too_many, default_core()).errors


def test_power_accounting_across_scenarios_and_groups():
    project = FlybackProject(
        outputs=[
            OutputSpec("main12", 12.0, 2.0, output_id="o1", isolation_group="g1"),
            OutputSpec("iso5", 5.0, 1.0, output_id="o2", isolation_group="g2"),
            OutputSpec("aux12", 12.0, 0.5, output_id="o3", isolation_group="g1"),
        ]
    )
    rows = power_summary(
        project,
        [
            ScenarioSpec("light", bus_v=127.0, load_fraction=0.25),
            ScenarioSpec("full", bus_v=373.0, load_fraction=1.0),
        ],
    )
    light, full = rows
    assert light.output_power_w["o1"] == pytest.approx(12 * 2 * 0.25)
    assert light.group_power_w["g1"] == pytest.approx((12 * 2 + 12 * 0.5) * 0.25)
    assert light.group_power_w["g2"] == pytest.approx(5 * 1 * 0.25)
    assert light.total_power_w == pytest.approx(sum(light.output_power_w.values()))
    assert full.total_power_w == pytest.approx(12 * 2 + 5 * 1 + 12 * 0.5)
    assert full.total_power_w > light.total_power_w


def test_default_project_has_min_nom_max_bus_scenarios():
    project = FlybackProject()
    assert [s.name for s in project.scenarios] == [
        "bus-min", "bus-nominal", "bus-max",
    ]


def test_v1_project_upgrades_without_data_loss():
    # A v1-shaped payload: only the fields the old dataclass had.
    v1_payload = {
        "name": "منبع قدیمی",
        "outputs": [
            {"name": "out1", "voltage_v": 5.0, "current_a": 1.0,
             "diode_drop_v": 0.5, "diode_id": "generic-diode"},
        ],
    }
    from dataclasses import asdict

    project, core, parts = bundle_from_dict(
        {
            "schema_version": 1,
            "project": v1_payload,
            "core": asdict(default_core()),
            "parts": [],
        }
    )
    assert project.outputs[0].name == "out1"
    assert project.outputs[0].isolation_group == "main"  # v2 default applied
    assert len(project.scenarios) == 3

    round_trip = bundle_to_dict(project, core, parts)
    assert round_trip["project"]["outputs"][0]["isolation_group"] == "main"
    project2, _core2, _parts2 = bundle_from_dict(round_trip)
    assert project2 == project  # no data lost in the v2 round-trip


def test_invalid_group_and_load_range_are_engine_errors():
    bad = FlybackProject(
        outputs=[
            OutputSpec("x", 5.0, 1.0, isolation_group=" "),
            OutputSpec("y", 5.0, 1.0, load_min_a=2.0, load_max_a=1.0),
            OutputSpec("z", 5.0, 1.0, priority=-1),
        ]
    )
    errors = calculate(bad, default_core()).errors
    assert any("ایزولاسیون" in e for e in errors)
    assert any("بار" in e for e in errors)
    assert any("اولویت" in e for e in errors)
