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
    )
    _REQUIRED = ("frequency_khz", "current_limit_a", "switch_voltage_limit_v")
    _STATE_FA = {
        "accepted": "پذیرفته‌شده",
        "extracted": "فقط استخراج‌شده",
        "missing": "مجهول",
    }

    def run(self, context: ToolContext) -> None:
        from .dialog import FlybackDesignerDialog

        prefill = {}
        meta = {}
        profile = getattr(context, "controller_profile", None)
        if profile is not None:
            engine = profile.engine_view()
            accepted = engine.values
            raw = {f.name: f for f in profile.fields}

            # P0 rule: automatic prefill uses ONLY reviewed/verified values.
            for key in self._PREFILL_KEYS:
                source = accepted.get(key)
                if source is None:
                    continue
                value = source.value
                if value is None:
                    value = getattr(source, "value_typ", None)
                if value is not None:
                    prefill[key] = value
            prefill["ic_id"] = profile.part_number  # identity, not a value

            # Extracted-only values are surfaced as inactive suggestions;
            # applying each one stays an explicit user action.
            suggestions = [
                f"{name}={raw[name].value} (استخراج‌شده، اعمال‌نشده)"
                for name in self._PREFILL_KEYS
                if name in raw and name not in accepted
                and raw[name].value is not None
            ]

            # Per-required-field completeness, never a whole-profile claim.
            required_states = []
            for name in self._REQUIRED:
                if name in accepted:
                    state = self._STATE_FA["accepted"]
                elif name in raw:
                    state = self._STATE_FA["extracted"]
                else:
                    state = self._STATE_FA["missing"]
                required_states.append(f"{name}: {state}")
            accepted_count = sum(1 for n in self._REQUIRED if n in accepted)
            meta = {
                "manufacturer": profile.manufacturer,
                "part_number": profile.part_number,
                "profile_version": profile.profile_version,
                "status": (
                    f"مقادیر پذیرفته‌شدهٔ لازم: {accepted_count} از {len(self._REQUIRED)}"
                    " — پیش‌پر فقط با مقادیر پذیرفته‌شده"
                ),
                "required_fields": " | ".join(required_states),
                "suggestions": "؛ ".join(suggestions),
                "unknowns": "، ".join(engine.unknowns[:6]),
            }
        FlybackDesignerDialog(
            context.parent, prefill=prefill or None, controller_meta=meta or None
        ).exec()

