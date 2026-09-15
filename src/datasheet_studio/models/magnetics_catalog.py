"""Real magnetics catalogue domain (Phase 12).

Exact manufacturer records (core sets, materials, bobbins) with typed
geometry, loss-curve domains, compatibility links, and provenance/review
states. Validation enforces the four catalogue rules from
``docs/modules/MAGNETICS_CATALOG.md``; imported data can never be
``verified``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping

CATALOG_SCHEMA_VERSION = 2
ALLOWED_REVIEW_STATES = ("extracted", "reviewed")


class CatalogValidationError(ValueError):
    """A catalogue pack violates the magnetics contract."""


def _positive(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise CatalogValidationError(f"«{label}» باید عددی مثبت باشد.")
    return float(value)


def _require(text: object, label: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise CatalogValidationError(f"«{label}» الزامی است.")
    return text.strip()


def _review_state(state: object) -> str:
    value = str(state or "").strip()
    if value not in ALLOWED_REVIEW_STATES:
        raise CatalogValidationError(
            "وضعیت رکورد کاتالوگ باید extracted یا reviewed باشد؛"
            " ورود خودکار verified ممنوع است."
        )
    return value


@dataclass(frozen=True, slots=True)
class CoreRecord:
    manufacturer: str
    family: str            # e.g. "EE19/17" (alias only; ordering_code is truth)
    ordering_code: str     # exact orderable code
    ae_mm2: float
    aw_mm2: float
    le_mm: float
    mlt_mm: float
    ve_mm3: float
    b_max_t: float
    material_code: str
    bobbin_codes: tuple[str, ...] = ()
    gap_options_um: tuple[float, ...] = ()
    source_hash: str = ""
    page: int | None = None
    review_state: str = "extracted"

    def __post_init__(self) -> None:
        _require(self.manufacturer, "سازنده هسته")
        _require(self.family, "خانواده هسته")
        _require(self.ordering_code, "کد سفارش هسته")
        _require(self.material_code, "کد جنس هسته")
        for name, value in (
            ("Ae", self.ae_mm2), ("Aw", self.aw_mm2), ("le", self.le_mm),
            ("MLT", self.mlt_mm), ("Ve", self.ve_mm3), ("Bmax", self.b_max_t),
        ):
            _positive(value, f"هندسه {name}")
        _review_state(self.review_state)


@dataclass(frozen=True, slots=True)
class MaterialRecord:
    manufacturer: str
    code: str
    permeability: float
    freq_min_khz: float
    freq_max_khz: float
    temp_min_c: float
    temp_max_c: float
    loss_k: float | None = None
    loss_alpha: float | None = None
    loss_beta: float | None = None
    source_hash: str = ""
    page: int | None = None
    review_state: str = "extracted"

    def __post_init__(self) -> None:
        _require(self.manufacturer, "سازنده جنس")
        _require(self.code, "کد جنس")
        _positive(self.permeability, "تراوایی")
        if self.freq_min_khz >= self.freq_max_khz:
            raise CatalogValidationError("دامنهٔ فرکانس جنس نامعتبر است (min ≥ max).")
        if self.temp_min_c >= self.temp_max_c:
            raise CatalogValidationError("دامنهٔ دمای جنس نامعتبر است (min ≥ max).")
        _review_state(self.review_state)


@dataclass(frozen=True, slots=True)
class BobbinRecord:
    manufacturer: str
    code: str
    winding_width_mm: float
    winding_height_mm: float
    winding_area_mm2: float
    creepage_mm: float
    compatible_core_codes: tuple[str, ...] = ()
    source_hash: str = ""
    page: int | None = None
    review_state: str = "extracted"

    def __post_init__(self) -> None:
        _require(self.manufacturer, "سازنده بوبین")
        _require(self.code, "کد بوبین")
        for name, value in (
            ("عرض پنجره", self.winding_width_mm),
            ("ارتفاع پنجره", self.winding_height_mm),
            ("مساحت پنجره", self.winding_area_mm2),
            ("فاصله خزشی", self.creepage_mm),
        ):
            _positive(value, f"بوبین {name}")
        _review_state(self.review_state)


@dataclass(frozen=True, slots=True)
class CatalogPack:
    provider: str
    pack_version: str
    cores: tuple[CoreRecord, ...] = ()
    materials: tuple[MaterialRecord, ...] = ()
    bobbins: tuple[BobbinRecord, ...] = ()
    manifest_hash: str = ""

    def validate(self) -> None:
        cores = {core.ordering_code: core for core in self.cores}
        bobbins = {bobbin.code: bobbin for bobbin in self.bobbins}
        materials = {material.code: material for material in self.materials}
        # Rule: every core's material must exist and share the manufacturer.
        for core in self.cores:
            material = materials.get(core.material_code)
            if material is None:
                raise CatalogValidationError(
                    f"جنس «{core.material_code}» هسته «{core.ordering_code}» در پک نیست."
                )
            if material.manufacturer != core.manufacturer:
                raise CatalogValidationError(
                    "فرض ترکیب سازنده‌ها ممنوع است: هسته «"
                    f"{core.ordering_code}» ({core.manufacturer}) به جنس «"
                    f"{material.code}» ({material.manufacturer}) اشاره می‌کند."
                )
            for code in core.bobbin_codes:
                bobbin = bobbins.get(code)
                if bobbin is None:
                    raise CatalogValidationError(
                        f"بوبین «{code}» هسته «{core.ordering_code}» در پک نیست."
                    )
                if bobbin.manufacturer != core.manufacturer:
                    raise CatalogValidationError(
                        "فرض ترکیب سازنده‌ها ممنوع است: بوبین «"
                        f"{code}» با هسته «{core.ordering_code}» سازنده یکسان ندارد."
                    )
                if core.ordering_code not in bobbin.compatible_core_codes:
                    raise CatalogValidationError(
                        f"بوبین «{code}» سازگاریش را با هسته «{core.ordering_code}» اعلام نکرده است."
                    )

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "provider": self.provider,
            "pack_version": self.pack_version,
            "manifest_hash": self.manifest_hash,
            "cores": [asdict(c) for c in self.cores],
            "materials": [asdict(m) for m in self.materials],
            "bobbins": [asdict(b) for b in self.bobbins],
        }


def pack_from_dict(data: Mapping[str, Any]) -> CatalogPack:
    if data.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogValidationError("نسخهٔ اسکیمای کاتالوگ پشتیبانی نمی‌شود.")
    pack = CatalogPack(
        provider=_require(data.get("provider"), "ارائه‌دهندهٔ پک"),
        pack_version=_require(data.get("pack_version"), "نسخهٔ پک"),
        cores=tuple(
            CoreRecord(
                manufacturer=c["manufacturer"], family=c["family"],
                ordering_code=c["ordering_code"],
                ae_mm2=c["ae_mm2"], aw_mm2=c["aw_mm2"], le_mm=c["le_mm"],
                mlt_mm=c["mlt_mm"], ve_mm3=c["ve_mm3"], b_max_t=c["b_max_t"],
                material_code=c["material_code"],
                bobbin_codes=tuple(c.get("bobbin_codes", ())),
                gap_options_um=tuple(c.get("gap_options_um", ())),
                source_hash=c.get("source_hash", ""),
                page=c.get("page"),
                review_state=c.get("review_state", "extracted"),
            )
            for c in data.get("cores", [])
        ),
        materials=tuple(
            MaterialRecord(
                manufacturer=m["manufacturer"], code=m["code"],
                permeability=m["permeability"],
                freq_min_khz=m["freq_min_khz"], freq_max_khz=m["freq_max_khz"],
                temp_min_c=m["temp_min_c"], temp_max_c=m["temp_max_c"],
                loss_k=m.get("loss_k"), loss_alpha=m.get("loss_alpha"),
                loss_beta=m.get("loss_beta"),
                source_hash=m.get("source_hash", ""),
                page=m.get("page"),
                review_state=m.get("review_state", "extracted"),
            )
            for m in data.get("materials", [])
        ),
        bobbins=tuple(
            BobbinRecord(
                manufacturer=b["manufacturer"], code=b["code"],
                winding_width_mm=b["winding_width_mm"],
                winding_height_mm=b["winding_height_mm"],
                winding_area_mm2=b["winding_area_mm2"],
                creepage_mm=b["creepage_mm"],
                compatible_core_codes=tuple(b.get("compatible_core_codes", ())),
                source_hash=b.get("source_hash", ""),
                page=b.get("page"),
                review_state=b.get("review_state", "extracted"),
            )
            for b in data.get("bobbins", [])
        ),
        manifest_hash=str(data.get("manifest_hash", "")),
    )
    pack.validate()
    return pack


def dump_pack(pack: CatalogPack) -> str:
    pack.validate()
    return json.dumps(pack.to_dict(), ensure_ascii=False, indent=2) + "\n"


def load_pack(text: str | Mapping[str, Any]) -> CatalogPack:
    data = json.loads(text) if isinstance(text, str) else text
    return pack_from_dict(data)


def pack_diff(installed: CatalogPack | None, candidate: CatalogPack) -> dict[str, list[str]]:
    """Update preview: which core codes are new or changed."""

    old = {core.ordering_code: core for core in (installed.cores if installed else ())}
    new = {core.ordering_code: core for core in candidate.cores}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(
        code for code in set(old) & set(new) if old[code] != new[code]
    )
    return {"added": added, "removed": removed, "changed": changed}
