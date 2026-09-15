"""Controller IC profile schema with per-field evidence (Phase 8).

Builds on the Phase 2 ``EvidenceField``/review-state machinery and adds the
strict controller field registry (units, ranges, enums), envelope
serialization, the AI/import cap, and the engine-facing view that exposes
only accepted values plus explicit unknowns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping

from datasheet_studio.models.knowledge_base import (
    SCHEMA_VERSION,
    EvidenceField,
    RecordValidationError,
    is_automated_assignable,
)

PROFILE_RECORD_KIND = "controller-profile"

SECTION_LABELS_FA = {
    "limits": "حدود کلیدی",
    "timing": "زمان‌بندی",
    "switch": "مدل کلید",
    "startup": "راه‌اندازی و بایاس",
    "protection": "حفاظت‌ها",
    "feedback": "فیدبک",
    "mode": "حالت کار",
    "application": "محدودیت‌های کاربرد",
}


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    section: str
    label_fa: str
    kind: str  # "number" | "enum" | "text"
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    enum_values: tuple[str, ...] = ()
    required: bool = False


def _spec(name, section, label, kind="number", unit="", minimum=None,
          maximum=None, enum_values=(), required=False) -> FieldSpec:
    return FieldSpec(name, section, label, kind, unit, minimum, maximum,
                     tuple(enum_values), required)


FIELD_SPECS: dict[str, FieldSpec] = {
    s.name: s
    for s in (
        # limits
        _spec("vdd_min_v", "limits", "حداقل ولتاژ تغذیه", unit="V", minimum=0, maximum=1000),
        _spec("vdd_max_v", "limits", "حداکثر ولتاژ تغذیه", unit="V", minimum=0, maximum=1000),
        _spec("current_limit_a", "limits", "حد جریان کلید", unit="A", minimum=0.001, maximum=100, required=True),
        _spec("switch_voltage_limit_v", "limits", "حد ولتاژ کلید", unit="V", minimum=10, maximum=5000, required=True),
        _spec("ovp_threshold_v", "limits", "آستانه حفاظت اضافه‌ولتاژ", unit="V", minimum=0, maximum=5000),
        _spec("duty_max", "limits", "حداکثر دیوتی", minimum=0.01, maximum=1.0),
        # timing
        _spec("frequency_khz", "timing", "فرکانس سوئیچینگ", unit="kHz", minimum=1, maximum=2000, required=True),
        _spec("frequency_min_khz", "timing", "حداقل فرکانس", unit="kHz", minimum=1, maximum=2000),
        _spec("frequency_max_khz", "timing", "حداکثر فرکانس", unit="kHz", minimum=1, maximum=2000),
        _spec("max_on_time_us", "timing", "حداکثر زمان روشن", unit="µs", minimum=0.1, maximum=1000),
        # switch
        _spec("switch_type", "switch", "نوع کلید", kind="enum", enum_values=("bjt", "mosfet", "external-mosfet-driver")),
        _spec("vce_sat_v", "switch", "اشباع VCE", unit="V", minimum=0, maximum=20),
        _spec("vds_rating_v", "switch", "رده VDS", unit="V", minimum=10, maximum=5000),
        _spec("rdson_ohm", "switch", "RDS(on)", unit="Ω", minimum=0, maximum=1000),
        _spec("rise_ns", "switch", "زمان صعود", unit="ns", minimum=0, maximum=10000),
        _spec("fall_ns", "switch", "زمان نزول", unit="ns", minimum=0, maximum=10000),
        # startup / bias
        _spec("vcc_start_v", "startup", "آستانه شروع VCC", unit="V", minimum=0, maximum=100),
        _spec("vcc_stop_v", "startup", "آستانه توقف VCC", unit="V", minimum=0, maximum=100),
        _spec("startup_current_ma", "startup", "جریان راه‌اندازی", unit="mA", minimum=0, maximum=1000),
        _spec("vcc_operating_ma", "startup", "جریان کاری VCC", unit="mA", minimum=0, maximum=1000),
        # protection
        _spec("uvlo_v", "protection", "آستانه UVLO", unit="V", minimum=0, maximum=1000),
        _spec("otp_c", "protection", "دمای حفاظت حرارتی", unit="°C", minimum=50, maximum=250),
        # feedback
        _spec("feedback_type", "feedback", "نوع فیدبک", kind="enum",
              enum_values=("direct", "optocoupler", "primary-side-regulation", "internal")),
        _spec("vref_v", "feedback", "ولتاژ مرجع فیدبک", unit="V", minimum=0, maximum=30),
        # mode
        _spec("control_mode", "mode", "حالت کنترل", kind="enum",
              enum_values=("fixed-frequency", "quasi-resonant", "multi-mode", "burst-capable")),
        # application
        _spec("max_power_w", "application", "حداکثر توان پیشنهادی", unit="W", minimum=0.1, maximum=10000),
        _spec("ambient_min_c", "application", "حداقل دمای محیط", unit="°C", minimum=-60, maximum=100),
        _spec("ambient_max_c", "application", "حداکثر دمای محیط", unit="°C", minimum=0, maximum=200),
    )
}

REQUIRED_FIELDS = tuple(name for name, spec in FIELD_SPECS.items() if spec.required)
ACCEPTED_STATES = ("reviewed", "verified")


class ControllerProfileError(RecordValidationError):
    """A controller-profile constraint was violated."""


@dataclass(frozen=True, slots=True)
class EngineViewValue:
    value: float | str
    unit: str
    page: int | None
    review_state: str


@dataclass(frozen=True, slots=True)
class ControllerEngineView:
    """What a deterministic engine may consume: accepted values + unknowns."""

    values: dict[str, EngineViewValue]
    unknowns: tuple[str, ...]
    contradictions: tuple[str, ...]
    unsupported: tuple[str, ...]

    @property
    def has_required_unknowns(self) -> bool:
        return any(name in REQUIRED_FIELDS for name in self.unknowns)


def _validate_field(field: EvidenceField) -> None:
    spec = FIELD_SPECS.get(field.name)
    if spec is None:
        raise ControllerProfileError(
            f"فیلد پروفایل کنترلر شناخته نشد: {field.name}"
        )
    if field.unit and spec.unit and field.unit != spec.unit:
        raise ControllerProfileError(
            f"واحد فیلد «{field.name}» باید «{spec.unit}» باشد، نه «{field.unit}»."
        )
    if spec.kind == "enum":
        if not isinstance(field.value, str) or field.value not in spec.enum_values:
            allowed = "، ".join(spec.enum_values)
            raise ControllerProfileError(
                f"مقدار فیلد «{field.name}» باید یکی از این‌ها باشد: {allowed}"
            )
        return
    if spec.kind == "number":
        for label, value in (
            ("value", field.value),
            ("value_min", field.value_min),
            ("value_typ", field.value_typ),
            ("value_max", field.value_max),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                if label == "value":
                    raise ControllerProfileError(
                        f"فیلد «{field.name}» مقدار عددی لازم دارد."
                    )
                continue
            if spec.minimum is not None and value < spec.minimum:
                raise ControllerProfileError(
                    f"مقدار «{field.name}» ({value}) کمتر از حد مجاز ({spec.minimum}) است."
                )
            if spec.maximum is not None and value > spec.maximum:
                raise ControllerProfileError(
                    f"مقدار «{field.name}» ({value}) بیشتر از حد مجاز ({spec.maximum}) است."
                )


@dataclass(frozen=True, slots=True)
class ControllerProfile:
    """One controller IC profile: identity + evidence fields."""

    manufacturer: str
    part_number: str
    source_object_sha256: str
    profile_version: str = "1"
    package: str = ""
    source_revision: str = ""
    fields: tuple[EvidenceField, ...] = ()
    contradictions: tuple[str, ...] = ()
    unknown_facts: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("سازنده", self.manufacturer),
            ("شماره قطعه", self.part_number),
            ("هش منبع", self.source_object_sha256),
        ):
            if not str(value).strip():
                raise ControllerProfileError(f"«{label}» الزامی است.")
        seen: set[str] = set()
        for item in self.fields:
            _validate_field(item)
            if item.name in seen:
                raise ControllerProfileError(
                    f"فیلد تکراری در پروفایل: {item.name}"
                )
            seen.add(item.name)

    # -- factories ---------------------------------------------------------

    @classmethod
    def from_extraction(cls, **kwargs: Any) -> "ControllerProfile":
        """AI/import path: reviewed/verified fields are rejected outright."""

        for item in kwargs.get("fields", ()) or ():
            if not is_automated_assignable(item.review_state):
                raise ControllerProfileError(
                    "استخراج خودکار نمی‌تواند فیلد reviewed/verified بسازد: "
                    f"{item.name}"
                )
        return cls(**kwargs)

    # -- views ---------------------------------------------------------------

    def engine_view(self) -> ControllerEngineView:
        values: dict[str, EngineViewValue] = {}
        accepted_names: set[str] = set()
        for item in self.fields:
            if item.review_state in ACCEPTED_STATES:
                accepted_names.add(item.name)
                values[item.name] = EngineViewValue(
                    value=item.value if item.value is not None else item.value_typ,
                    unit=item.unit or FIELD_SPECS[item.name].unit,
                    page=item.provenance.page if item.provenance else None,
                    review_state=item.review_state,
                )
        unknowns = tuple(sorted(set(FIELD_SPECS) - accepted_names))
        return ControllerEngineView(
            values=values,
            unknowns=unknowns,
            contradictions=tuple(self.contradictions),
            unsupported=tuple(self.unsupported),
        )

    @property
    def is_structurally_complete(self) -> bool:
        present = {item.name for item in self.fields}
        return all(name in present for name in REQUIRED_FIELDS)

    # -- serialization ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "source_object_sha256": self.source_object_sha256,
            "profile_version": self.profile_version,
            "package": self.package,
            "source_revision": self.source_revision,
            "fields": [f.to_dict() for f in self.fields],
            "contradictions": list(self.contradictions),
            "unknown_facts": list(self.unknown_facts),
            "unsupported": list(self.unsupported),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ControllerProfile":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        unknown = sorted(set(data) - known)
        if unknown:
            raise ControllerProfileError(
                "کلیدهای ناشناخته در پروفایل کنترلر: " + "، ".join(unknown)
            )
        return cls(
            manufacturer=data["manufacturer"],
            part_number=data["part_number"],
            source_object_sha256=data["source_object_sha256"],
            profile_version=str(data.get("profile_version", "1")),
            package=str(data.get("package", "")),
            source_revision=str(data.get("source_revision", "")),
            fields=tuple(
                EvidenceField.from_dict(f) for f in data.get("fields", ())
            ),
            contradictions=tuple(data.get("contradictions", ())),
            unknown_facts=tuple(data.get("unknown_facts", ())),
            unsupported=tuple(data.get("unsupported", ())),
            notes=str(data.get("notes", "")),
        )


def dump_controller_profile(profile: ControllerProfile) -> str:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "record_kind": PROFILE_RECORD_KIND,
        "record": profile.to_dict(),
    }
    return json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"


def load_controller_profile(data: str | Mapping[str, Any]) -> ControllerProfile:
    from datasheet_studio.models.knowledge_base import KnowledgeBaseVersionError

    parsed = json.loads(data) if isinstance(data, str) else data
    if not isinstance(parsed, Mapping):
        raise ControllerProfileError("ساختار پروفایل باید یک نگاشت باشد.")
    if parsed.get("schema_version") != SCHEMA_VERSION:
        raise KnowledgeBaseVersionError(
            f"نسخه اسکیمای پروفایل {parsed.get('schema_version')!r} پشتیبانی نمی‌شود."
        )
    if parsed.get("record_kind") != PROFILE_RECORD_KIND:
        raise ControllerProfileError("نوع رکورد، پروفایل کنترلر نیست.")
    payload = parsed.get("record")
    if not isinstance(payload, Mapping):
        raise ControllerProfileError("بدنهٔ پروفایل باید یک نگاشت باشد.")
    return ControllerProfile.from_dict(payload)
