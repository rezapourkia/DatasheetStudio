"""Pure numerical engine for the native DCM Flyback Designer.

Input units are explicit in the dataclass field names.  This module deliberately
has no Qt, file-system, PDF, settings, or network dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping, Sequence


@dataclass(slots=True)
class OutputSpec:
    name: str
    voltage_v: float
    current_a: float
    diode_drop_v: float = 0.6
    diode_id: str = "generic-diode"


@dataclass(slots=True)
class CoreSpec:
    core_id: str
    name: str
    ae_mm2: float
    aw_mm2: float
    le_mm: float
    mlt_mm: float
    ve_mm3: float
    bmax_t: float
    verified: bool = False
    source: str = ""


@dataclass(slots=True)
class ComponentSpec:
    component_id: str
    name: str
    component_type: str
    params: dict[str, float] = field(default_factory=dict)
    verified: bool = False
    source: str = ""


@dataclass(slots=True)
class FlybackProject:
    name: str = "منبع تغذیه فلای‌بک ۲۴ وات"
    vin_min_v: float = 100.0
    vin_max_v: float = 375.0
    frequency_khz: float = 65.0
    efficiency_pct: float = 82.0
    duty: float = 0.38
    b_target_t: float = 0.20
    current_density_a_mm2: float = 4.0
    fill_factor: float = 0.30
    current_limit_a: float = 1.1
    switch_voltage_limit_v: float = 700.0
    switch_type: str = "bjt"
    vce_v: float = 1.0
    rdson_ohm: float = 2.0
    switch_rise_ns: float = 40.0
    switch_fall_ns: float = 40.0
    bridge_drop_v: float = 0.9
    leakage_pct: float = 2.0
    clamp_above_bus_v: float = 150.0
    clamp_ripple_pct: float = 10.0
    max_strand_diameter_mm: float = 0.4
    insulation_mm: float = 0.1
    core_loss_density_kw_m3: float = 100.0
    feedback_type: str = "tl431"
    tl431_bottom_kohm: float = 10.0
    optocoupler_ctr_pct: float = 50.0
    optocoupler_led_current_ma: float = 2.0
    optocoupler_vf_v: float = 1.2
    ic_id: str = "dk124"
    switch_id: str = "generic-mosfet"
    bridge_id: str = "generic-bridge"
    capacitor_id: str = "generic-cap"
    notes: str = ""
    outputs: list[OutputSpec] = field(
        default_factory=lambda: [OutputSpec("خروجی اصلی", 12.0, 2.0)]
    )


@dataclass(frozen=True, slots=True)
class WindingResult:
    turns: int
    rms_a: float
    peak_a: float
    strands: int
    wire_diameter_mm: float
    copper_area_mm2: float
    occupied_area_mm2: float
    resistance_ohm: float
    copper_loss_w: float


@dataclass(frozen=True, slots=True)
class OutputResult:
    spec: OutputSpec
    turns: int
    ideal_voltage_v: float
    voltage_error_pct: float
    demagnetisation_peak_a: float
    winding: WindingResult
    reverse_voltage_v: float
    diode_loss_w: float
    reverse_recovery_loss_w: float


@dataclass(frozen=True, slots=True)
class FeedbackResult:
    top_resistor_kohm: float
    led_resistor_kohm: float
    collector_current_ma: float


@dataclass(frozen=True, slots=True)
class CalculationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    output_power_w: float = 0.0
    input_power_w: float = 0.0
    primary_peak_a: float = 0.0
    magnetising_inductance_h: float = 0.0
    primary_turns: int = 0
    reflected_voltage_v: float = 0.0
    demagnetisation_duty: float = 0.0
    high_line_duty: float = 0.0
    flux_density_t: float = 0.0
    primary: WindingResult | None = None
    outputs: tuple[OutputResult, ...] = ()
    window_fill_ratio: float = 0.0
    air_gap_mm: float = 0.0
    al_nh_turn2: float = 0.0
    switch_stress_v: float = 0.0
    snubber_power_w: float | None = None
    snubber_resistance_ohm: float | None = None
    snubber_capacitance_f: float | None = None
    switch_conduction_loss_w: float = 0.0
    switch_switching_loss_w: float = 0.0
    copper_loss_w: float = 0.0
    core_loss_w: float = 0.0
    bridge_loss_w: float = 0.0
    total_loss_w: float = 0.0
    estimated_efficiency_pct: float = 0.0
    first_output_ripple_v: float = 0.0
    first_capacitor_ripple_a: float = 0.0
    feedback: FeedbackResult | None = None
    skin_depth_mm: float = 0.0


def _finite(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _part_map(parts: Sequence[ComponentSpec]) -> Mapping[str, ComponentSpec]:
    return {part.component_id: part for part in parts}


def calculate(
    project: FlybackProject,
    core: CoreSpec,
    parts: Sequence[ComponentSpec] = (),
) -> CalculationResult:
    """Calculate a preliminary constant-frequency DCM flyback design."""

    errors: list[str] = []
    positive_values = {
        "حداقل ولتاژ باس": project.vin_min_v,
        "حداکثر ولتاژ باس": project.vin_max_v,
        "فرکانس": project.frequency_khz,
        "بازده فرضی": project.efficiency_pct,
        "دیوتی": project.duty,
        "چگالی شار هدف": project.b_target_t,
        "چگالی جریان": project.current_density_a_mm2,
        "ضریب پرشدگی": project.fill_factor,
        "حد جریان": project.current_limit_a,
        "حد ولتاژ کلید": project.switch_voltage_limit_v,
        "ولتاژ کلمپ": project.clamp_above_bus_v,
        "ریپل کلمپ": project.clamp_ripple_pct,
        "حداکثر قطر رشته": project.max_strand_diameter_mm,
        "مقاومت پایین TL431": project.tl431_bottom_kohm,
        "CTR": project.optocoupler_ctr_pct,
        "جریان LED اپتو": project.optocoupler_led_current_ma,
    }
    for label, value in positive_values.items():
        if not _finite(value) or float(value) <= 0:
            errors.append(f"برای «{label}» مقدار معتبر و مثبت لازم است.")

    nonnegative_values = {
        "RDS(on)": project.rdson_ohm,
        "افت پل": project.bridge_drop_v,
        "اندوکتانس نشتی": project.leakage_pct,
        "چگالی تلفات هسته": project.core_loss_density_kw_m3,
        "ضخامت عایق": project.insulation_mm,
        "افت LED اپتو": project.optocoupler_vf_v,
        "VCE": project.vce_v,
        "زمان صعود کلید": project.switch_rise_ns,
        "زمان نزول کلید": project.switch_fall_ns,
    }
    for label, value in nonnegative_values.items():
        if not _finite(value) or float(value) < 0:
            errors.append(f"برای «{label}» مقدار معتبر و نامنفی لازم است.")

    if _finite(project.vin_min_v) and _finite(project.vin_max_v):
        if project.vin_max_v < project.vin_min_v:
            errors.append("حداکثر ولتاژ باس نباید از حداقل آن کمتر باشد.")
    if _finite(project.efficiency_pct) and project.efficiency_pct >= 100:
        errors.append("بازده فرضی باید کمتر از ۱۰۰ درصد باشد.")
    if _finite(project.duty) and project.duty >= 0.8:
        errors.append("دیوتی باید کمتر از ۰٫۸ باشد.")
    if _finite(project.fill_factor) and project.fill_factor >= 0.8:
        errors.append("ضریب پرشدگی باید کمتر از ۰٫۸ باشد.")
    if _finite(project.clamp_ripple_pct) and project.clamp_ripple_pct >= 100:
        errors.append("ریپل کلمپ باید کمتر از ۱۰۰ درصد باشد.")
    if (
        not isinstance(project.switch_type, str)
        or project.switch_type not in {"bjt", "mosfet"}
    ):
        errors.append("نوع کلید باید BJT یا MOSFET باشد.")

    project_ids = {
        "آی‌سی": project.ic_id,
        "کلید": project.switch_id,
        "پل": project.bridge_id,
        "خازن": project.capacitor_id,
    }
    for label, value in project_ids.items():
        if not isinstance(value, str) or not value.strip():
            errors.append(f"شناسه «{label}» باید یک متن غیرخالی باشد.")

    seen_part_ids: set[str] = set()
    for index, part in enumerate(parts, start=1):
        if not isinstance(part, ComponentSpec):
            errors.append(f"ساختار قطعه {index} معتبر نیست.")
            continue
        if not isinstance(part.component_id, str) or not part.component_id.strip():
            errors.append(f"شناسه قطعه {index} معتبر نیست.")
        elif part.component_id in seen_part_ids:
            errors.append(f"شناسه قطعه تکراری است: {part.component_id}")
        else:
            seen_part_ids.add(part.component_id)
        if not isinstance(part.name, str) or not part.name.strip():
            errors.append(f"نام قطعه {index} معتبر نیست.")
        if not isinstance(part.component_type, str) or not part.component_type.strip():
            errors.append(f"نوع قطعه {index} معتبر نیست.")
        if not isinstance(part.params, dict):
            errors.append(f"پارامترهای قطعه {index} باید یک نگاشت باشند.")
            continue
        for key, value in part.params.items():
            if not isinstance(key, str) or not key.strip() or not _finite(value):
                errors.append(f"پارامترهای عددی قطعه {index} معتبر نیستند.")
                break

    core_values = (
        core.ae_mm2,
        core.aw_mm2,
        core.le_mm,
        core.mlt_mm,
        core.ve_mm3,
        core.bmax_t,
    )
    if any(not _finite(value) or float(value) <= 0 for value in core_values):
        errors.append("مشخصات هندسی یا مغناطیسی هسته نامعتبر است.")

    if not 1 <= len(project.outputs) <= 8:
        errors.append("تعداد خروجی‌ها باید بین یک تا هشت باشد.")
    for index, output in enumerate(project.outputs, start=1):
        if not isinstance(output.name, str) or not output.name.strip():
            errors.append(f"نام خروجی {index} معتبر نیست.")
        if not isinstance(output.diode_id, str) or not output.diode_id.strip():
            errors.append(f"شناسه دیود خروجی {index} معتبر نیست.")
        if (
            not _finite(output.voltage_v)
            or output.voltage_v <= 0
            or not _finite(output.current_a)
            or output.current_a <= 0
            or not _finite(output.diode_drop_v)
            or output.diode_drop_v < 0
        ):
            errors.append(f"مقادیر خروجی {index} نامعتبر است.")

    if errors:
        return CalculationResult(errors=tuple(errors))

    part_by_id = _part_map(parts)
    frequency_hz = project.frequency_khz * 1000.0
    efficiency = project.efficiency_pct / 100.0
    output_power_w = sum(o.voltage_v * o.current_a for o in project.outputs)
    input_power_w = output_power_w / efficiency
    primary_peak_a = (
        2.0 * input_power_w / (project.vin_min_v * project.duty)
    )
    magnetising_inductance_h = (
        project.vin_min_v * project.duty / (primary_peak_a * frequency_hz)
    )
    primary_turns = math.ceil(
        magnetising_inductance_h
        * primary_peak_a
        / (project.b_target_t * core.ae_mm2 * 1e-6)
    )
    reference_output = project.outputs[0]
    target_reflected_v = (
        project.vin_min_v * project.duty / (0.88 - project.duty)
    )
    reference_turns = max(
        1,
        round(
            primary_turns
            * (reference_output.voltage_v + reference_output.diode_drop_v)
            / target_reflected_v
        ),
    )
    reflected_voltage_v = (
        primary_turns
        / reference_turns
        * (reference_output.voltage_v + reference_output.diode_drop_v)
    )
    demagnetisation_duty = (
        project.vin_min_v * project.duty / reflected_voltage_v
    )
    high_line_duty = project.vin_min_v * project.duty / project.vin_max_v
    flux_density_t = (
        magnetising_inductance_h
        * primary_peak_a
        / (primary_turns * core.ae_mm2 * 1e-6)
    )
    primary_rms_a = primary_peak_a * math.sqrt(project.duty / 3.0)

    def winding(rms_a: float, peak_a: float, turns: int) -> WindingResult:
        required_area = rms_a / project.current_density_a_mm2
        max_strand_area = math.pi * project.max_strand_diameter_mm**2 / 4.0
        strands = max(1, math.ceil(required_area / max_strand_area))
        diameter_mm = (
            math.ceil(math.sqrt(4.0 * required_area / (math.pi * strands)) * 100)
            / 100.0
        )
        actual_area = strands * math.pi * diameter_mm**2 / 4.0
        occupied_area = (
            turns * strands * math.pi * (diameter_mm + 0.04) ** 2 / 4.0
        )
        resistance = (
            0.0175 * (turns * core.mlt_mm / 1000.0) / actual_area
        )
        return WindingResult(
            turns=turns,
            rms_a=rms_a,
            peak_a=peak_a,
            strands=strands,
            wire_diameter_mm=diameter_mm,
            copper_area_mm2=actual_area,
            occupied_area_mm2=occupied_area,
            resistance_ohm=resistance,
            copper_loss_w=rms_a**2 * resistance,
        )

    primary = winding(primary_rms_a, primary_peak_a, primary_turns)
    output_results: list[OutputResult] = []
    for index, output in enumerate(project.outputs):
        turns = (
            reference_turns
            if index == 0
            else max(
                1,
                round(
                    primary_turns
                    * (output.voltage_v + output.diode_drop_v)
                    / reflected_voltage_v
                ),
            )
        )
        ideal_voltage = reflected_voltage_v * turns / primary_turns - output.diode_drop_v
        peak_a = 2.0 * output.current_a / demagnetisation_duty
        rms_a = peak_a * math.sqrt(demagnetisation_duty / 3.0)
        reverse_voltage = output.voltage_v + project.vin_max_v * turns / primary_turns
        diode = part_by_id.get(output.diode_id)
        reverse_recovery_ns = diode.params.get("trr_ns", 0.0) if diode else 0.0
        output_results.append(
            OutputResult(
                spec=output,
                turns=turns,
                ideal_voltage_v=ideal_voltage,
                voltage_error_pct=(ideal_voltage - output.voltage_v) * 100.0 / output.voltage_v,
                demagnetisation_peak_a=peak_a,
                winding=winding(rms_a, peak_a, turns),
                reverse_voltage_v=reverse_voltage,
                diode_loss_w=output.current_a * output.diode_drop_v,
                reverse_recovery_loss_w=(
                    0.5
                    * reverse_voltage
                    * peak_a
                    * reverse_recovery_ns
                    * 1e-9
                    * frequency_hz
                ),
            )
        )

    window_fill_ratio = (
        primary.occupied_area_mm2
        + sum(o.winding.occupied_area_mm2 for o in output_results)
    ) / core.aw_mm2
    air_gap_mm = (
        4.0
        * math.pi
        * 1e-7
        * primary_turns**2
        * core.ae_mm2
        * 1e-6
        / magnetising_inductance_h
        * 1000.0
    )
    al_nh_turn2 = magnetising_inductance_h * 1e9 / primary_turns**2

    leakage_h = magnetising_inductance_h * project.leakage_pct / 100.0
    if project.clamp_above_bus_v > reflected_voltage_v:
        snubber_power_w = (
            0.5
            * leakage_h
            * primary_peak_a**2
            * frequency_hz
            * project.clamp_above_bus_v
            / (project.clamp_above_bus_v - reflected_voltage_v)
        )
        snubber_resistance_ohm = (
            project.clamp_above_bus_v**2 / snubber_power_w
        )
        snubber_capacitance_f = 1.0 / (
            snubber_resistance_ohm
            * frequency_hz
            * project.clamp_ripple_pct
            / 100.0
        )
    else:
        snubber_power_w = None
        snubber_resistance_ohm = None
        snubber_capacitance_f = None

    switch_stress_v = project.vin_max_v + max(
        reflected_voltage_v, project.clamp_above_bus_v
    )
    switch_part = part_by_id.get(project.switch_id)
    rdson = (
        switch_part.params.get("rdson_ohm", project.rdson_ohm)
        if switch_part
        else project.rdson_ohm
    )
    switch_part_limit = (
        project.switch_voltage_limit_v
        if project.switch_type == "bjt"
        else (
            switch_part.params.get("vds_v", project.switch_voltage_limit_v)
            if switch_part
            else project.switch_voltage_limit_v
        )
    )
    if project.switch_type == "bjt":
        switch_conduction_loss_w = (
            project.vce_v * primary_peak_a * project.duty / 2.0
        )
        transition_ns = project.switch_rise_ns + project.switch_fall_ns
    else:
        switch_conduction_loss_w = primary_rms_a**2 * rdson
        transition_ns = (
            switch_part.params.get("tr_ns", project.switch_rise_ns)
            + switch_part.params.get("tf_ns", project.switch_fall_ns)
            if switch_part
            else project.switch_rise_ns + project.switch_fall_ns
        )
    switch_switching_loss_w = (
        0.5
        * (project.vin_max_v + reflected_voltage_v)
        * primary_peak_a
        * transition_ns
        * 1e-9
        * frequency_hz
    )

    copper_loss_w = primary.copper_loss_w + sum(
        o.winding.copper_loss_w for o in output_results
    )
    core_loss_w = core.ve_mm3 * 1e-9 * project.core_loss_density_kw_m3 * 1000.0
    bridge_loss_w = 2.0 * project.bridge_drop_v * input_power_w / project.vin_min_v
    capacitor = part_by_id.get(project.capacitor_id)
    capacitance_uf = capacitor.params.get("capacitance_uf", 470.0) if capacitor else 470.0
    capacitor_esr = capacitor.params.get("esr_ohm", 0.08) if capacitor else 0.08
    first_capacitor_ripple_a = math.sqrt(
        max(0.0, output_results[0].winding.rms_a**2 - reference_output.current_a**2)
    )
    first_output_ripple_v = (
        reference_output.current_a
        * (1.0 - demagnetisation_duty)
        / (capacitance_uf * 1e-6 * frequency_hz)
        + output_results[0].demagnetisation_peak_a * capacitor_esr
    )
    total_loss_w = (
        copper_loss_w
        + core_loss_w
        + bridge_loss_w
        + switch_conduction_loss_w
        + switch_switching_loss_w
        + (snubber_power_w or 0.0)
        + sum(o.diode_loss_w + o.reverse_recovery_loss_w for o in output_results)
        + first_capacitor_ripple_a**2 * capacitor_esr
    )
    feedback = FeedbackResult(
        top_resistor_kohm=project.tl431_bottom_kohm
        * (reference_output.voltage_v / 2.495 - 1.0),
        led_resistor_kohm=(
            reference_output.voltage_v - project.optocoupler_vf_v - 2.495
        )
        / project.optocoupler_led_current_ma,
        collector_current_ma=(
            project.optocoupler_led_current_ma
            * project.optocoupler_ctr_pct
            / 100.0
        ),
    )

    warnings: list[str] = []

    def warn(condition: bool, message: str) -> None:
        if condition:
            warnings.append(message)

    controller = part_by_id.get(project.ic_id)
    if controller:
        warn(
            bool(controller.params.get("current_limit_a"))
            and primary_peak_a > controller.params["current_limit_a"],
            "جریان محاسبه‌شده از حداقل آستانه حفاظت دیتاشیت آی‌سی بیشتر است.",
        )
        warn(
            bool(controller.params.get("ovp_min_v"))
            and switch_stress_v >= controller.params["ovp_min_v"],
            "تنش کلید به آستانه حداقل حفاظت ولتاژ آی‌سی رسیده است.",
        )
        warn(
            bool(controller.params.get("duty_max"))
            and project.duty > controller.params["duty_max"],
            "دیوتی از حد دیتاشیت آی‌سی بیشتر است.",
        )
        warn(
            bool(controller.params.get("wide_power_w"))
            and output_power_w > controller.params["wide_power_w"],
            "توان از مقدار مرجع دیتاشیت آی‌سی برای ورودی گسترده بیشتر است.",
        )
    warn(
        project.switch_type == "bjt",
        "تلفات BJT با VCE و زمان‌های دستی تخمین زده شده؛ تلفات بیس و زمان ذخیره کامل مدل نشده‌اند.",
    )
    bridge = part_by_id.get(project.bridge_id)
    if bridge:
        warn(
            bridge.params.get("reverse_voltage_v", math.inf) < project.vin_max_v * 1.2,
            "ولتاژ معکوس دیود پل ورودی کافی نیست.",
        )
        warn(
            bridge.params.get("average_current_a", math.inf) < input_power_w / project.vin_min_v / 2.0,
            "جریان متوسط دیود پل ورودی کافی نیست.",
        )
    warn(
        not core.verified,
        "ابعاد هسته نمونه‌اند؛ Ae و پنجره بوبین واقعی تأیید نشده‌اند.",
    )
    warn(
        controller is None or not controller.verified,
        "دیتاشیت آی‌سی تأیید نشده؛ فرکانس و محدودیت‌ها فرض دستی هستند.",
    )
    warn(flux_density_t > core.bmax_t, "چگالی شار از حد تعیین‌شده هسته بیشتر است.")
    warn(
        window_fill_ratio > project.fill_factor,
        "سیم‌پیچ با ضریب پرشدگی مجاز در پنجره جا نمی‌شود.",
    )
    warn(
        primary_peak_a > project.current_limit_a,
        "جریان پیک از حد تنظیم‌شده آی‌سی بیشتر است.",
    )
    warn(
        project.duty + demagnetisation_duty >= 1.0,
        "تخلیه شار کامل نیست؛ فرض DCM نامعتبر است.",
    )
    warn(
        switch_stress_v > 0.85 * min(switch_part_limit, project.switch_voltage_limit_v),
        "حاشیه ولتاژ کلید کمتر از ۱۵٪ است.",
    )
    warn(
        project.clamp_above_bus_v <= reflected_voltage_v,
        "ولتاژ کلمپ باید از ولتاژ بازتابی بیشتر باشد.",
    )
    for index, output in enumerate(output_results, start=1):
        diode = part_by_id.get(output.spec.diode_id)
        warn(
            abs(output.voltage_error_pct) > 5.0,
            f"خروجی {index}: خطای نسبت دور بیش از ۵٪؛ تنظیم متقاطع تضمین نمی‌شود.",
        )
        if diode:
            warn(
                diode.params.get("reverse_voltage_v", math.inf) < output.reverse_voltage_v * 1.2,
                f"خروجی {index}: ولتاژ معکوس دیود کافی نیست.",
            )
            warn(
                diode.params.get("average_current_a", math.inf) < output.spec.current_a,
                f"خروجی {index}: جریان نامی دیود کافی نیست.",
            )
    if capacitor:
        warn(
            capacitor.params.get("voltage_v", math.inf) < reference_output.voltage_v * 1.2,
            "ولتاژ نامی خازن خروجی اول کافی نیست.",
        )
        warn(
            capacitor.params.get("ripple_current_a", math.inf) < first_capacitor_ripple_a,
            "جریان ریپل خازن خروجی اول بیش از حد نامی است.",
        )
    warn(
        project.feedback_type == "tl431"
        and (feedback.top_resistor_kohm <= 0 or feedback.led_resistor_kohm <= 0),
        "ولتاژ خروجی برای این آرایش TL431 کافی نیست.",
    )

    return CalculationResult(
        errors=(),
        warnings=tuple(warnings),
        output_power_w=output_power_w,
        input_power_w=input_power_w,
        primary_peak_a=primary_peak_a,
        magnetising_inductance_h=magnetising_inductance_h,
        primary_turns=primary_turns,
        reflected_voltage_v=reflected_voltage_v,
        demagnetisation_duty=demagnetisation_duty,
        high_line_duty=high_line_duty,
        flux_density_t=flux_density_t,
        primary=primary,
        outputs=tuple(output_results),
        window_fill_ratio=window_fill_ratio,
        air_gap_mm=air_gap_mm,
        al_nh_turn2=al_nh_turn2,
        switch_stress_v=switch_stress_v,
        snubber_power_w=snubber_power_w,
        snubber_resistance_ohm=snubber_resistance_ohm,
        snubber_capacitance_f=snubber_capacitance_f,
        switch_conduction_loss_w=switch_conduction_loss_w,
        switch_switching_loss_w=switch_switching_loss_w,
        copper_loss_w=copper_loss_w,
        core_loss_w=core_loss_w,
        bridge_loss_w=bridge_loss_w,
        total_loss_w=total_loss_w,
        estimated_efficiency_pct=100.0 * output_power_w / (output_power_w + total_loss_w),
        first_output_ripple_v=first_output_ripple_v,
        first_capacitor_ripple_a=first_capacitor_ripple_a,
        feedback=feedback,
        skin_depth_mm=66.0 / math.sqrt(frequency_hz),
    )
