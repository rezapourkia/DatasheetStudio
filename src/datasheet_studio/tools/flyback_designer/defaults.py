"""Illustrative, explicitly unverified seed data for Flyback Designer."""

from __future__ import annotations

from copy import deepcopy

from .engine import ComponentSpec, CoreSpec, FlybackProject


SAMPLE_CORES: tuple[CoreSpec, ...] = (
    CoreSpec("ee19", "EE19 · نمونه", 23, 30, 40, 42, 920, 0.22),
    CoreSpec("ee25", "EE25 · نمونه", 40, 55, 58, 55, 2320, 0.22),
    CoreSpec("ee28", "EE28 · نمونه", 82, 85, 66, 65, 5412, 0.22),
    CoreSpec("etd34", "ETD34 · نمونه", 97, 123, 79, 72, 7663, 0.22),
)

SAMPLE_PARTS: tuple[ComponentSpec, ...] = (
    ComponentSpec(
        "dk124",
        "DK124 · Linkage v1.6",
        "ic",
        {
            "frequency_khz": 65,
            "current_limit_a": 1.1,
            "switch_voltage_limit_v": 700,
            "ovp_min_v": 540,
            "duty_max": 0.70,
            "wide_power_w": 18,
        },
        False,
        "Linkage DK124 v1.6، صفحات ۱ تا ۳؛ نسخه قطعه واقعی تطبیق داده شود.",
    ),
    ComponentSpec(
        "generic-bridge",
        "دیود پل نمونه 1000V / 2A",
        "diode",
        {"vf_v": 0.9, "reverse_voltage_v": 1000, "average_current_a": 2, "trr_ns": 0},
        False,
        "فرض آموزشی؛ قطعه تجاری نیست.",
    ),
    ComponentSpec(
        "generic-diode",
        "دیود نمونه 100V / 5A",
        "diode",
        {"vf_v": 0.6, "reverse_voltage_v": 100, "average_current_a": 5, "trr_ns": 30},
        False,
        "فرض آموزشی؛ قطعه تجاری نیست.",
    ),
    ComponentSpec(
        "generic-mosfet",
        "MOSFET نمونه 700V",
        "mosfet",
        {"vds_v": 700, "rdson_ohm": 2, "tr_ns": 40, "tf_ns": 40},
        False,
        "فرض آموزشی؛ قطعه تجاری نیست.",
    ),
    ComponentSpec(
        "generic-cap",
        "خازن نمونه 470µF",
        "capacitor",
        {"capacitance_uf": 470, "esr_ohm": 0.08, "voltage_v": 25, "ripple_current_a": 1.5},
        False,
        "فرض آموزشی؛ قطعه تجاری نیست.",
    ),
)


def default_project() -> FlybackProject:
    """Return a new mutable default project, never shared between dialogs."""

    return FlybackProject(
        notes=(
            "پین‌ها قراردادی هستند؛ با نقشه بوبین واقعی تطبیق داده شوند. "
            "فاصله خزشی و هوایی و آزمون عایقی طبق استاندارد محصول تعیین شود."
        )
    )


def default_core() -> CoreSpec:
    return deepcopy(SAMPLE_CORES[1])

