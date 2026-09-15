"""Registry entry for the native Flyback Designer."""

from __future__ import annotations

from dataclasses import dataclass

from datasheet_studio.tools.registry import ToolContext


@dataclass(frozen=True, slots=True)
class FlybackDesignerTool:
    id: str = "flyback-designer"
    name: str = "طراح فلای‌بک…"
    category: str = "Power Design"
    description: str = "Native Persian DCM flyback pre-design and transformer calculator."

    _PREFILL_KEYS = (
        "frequency_khz",
        "current_limit_a",
        "switch_voltage_limit_v",
        "duty_max",
        "ovp_threshold_v",
        "switch_type",
        "ic_id",
    )

    def run(self, context: ToolContext) -> None:
        from .dialog import FlybackDesignerDialog

        prefill = {}
        meta = {}
        profile = getattr(context, "controller_profile", None)
        if profile is not None:
            engine = profile.engine_view()
            accepted_values = engine.values
            has_accepted = any(
                v.review_state in ("reviewed", "verified")
                for v in accepted_values.values()
            )
            meta = {
                "manufacturer": profile.manufacturer,
                "part_number": profile.part_number,
                "profile_version": profile.profile_version,
                "status": (
                    "پذیرفته‌شده (بازبینی/تأیید)"
                    if has_accepted
                    else "بررسی‌نشده — نیازمند بازبینی انسانی"
                ),
                "unknowns": "، ".join(engine.unknowns[:6]),
            }
            raw = {f.name: f for f in profile.fields}
            for key in self._PREFILL_KEYS:
                if key == "ic_id":
                    prefill[key] = profile.part_number
                    continue
                source = accepted_values.get(key) or raw.get(key)
                if source is None:
                    continue
                value = source.value
                if value is None:
                    value = getattr(source, "value_typ", None)
                if value is not None:
                    prefill[key] = value
        FlybackDesignerDialog(
            context.parent, prefill=prefill or None, controller_meta=meta or None
        ).exec()

