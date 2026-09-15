"""Domain schema for the engineering knowledge base.

Implements the Phase 2 contract in
``docs/modules/KNOWLEDGE_BASE_SCHEMA.md``: versioned record types with
strict validation, canonical serialization, duplicate identity, and
path-safety rules.  This module is pure stdlib — no Qt, no network, no
filesystem writes — so it stays testable as a domain layer.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from datetime import datetime
import json
import re
from typing import Any, Mapping

SCHEMA_VERSION = 2

REVIEW_STATES = ("unreviewed", "extracted", "reviewed", "verified", "rejected")
HUMAN_REVIEW_STATES = ("reviewed", "verified", "rejected")
ALIAS_KINDS = ("part-number", "ordering-code", "oem", "marketing", "other")
MAGNETICS_KINDS = ("core", "core-set", "material", "bobbin")
DOCUMENT_TYPES = (
    "datasheet",
    "reference-manual",
    "application-note",
    "errata",
    "catalogue",
    "other",
)

ALLOWED_LIBRARY_ROOTS = (
    "records/",
    "objects/",
    "extracted/",
    "catalogs/",
    "projects/",
    "ai-runs/",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UUID_RE = re.compile(r"^[0-9a-f]{32}$")


class RecordValidationError(ValueError):
    """A knowledge-base record is structurally or semantically invalid."""


class KnowledgeBaseVersionError(RecordValidationError):
    """The record envelope carries an unsupported schema version."""


# ---------------------------------------------------------------------------
# scalar validation helpers


def _require_str(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise RecordValidationError(f"«{label}» باید متن باشد.")
    if not allow_empty and not value.strip():
        raise RecordValidationError(f"«{label}» نباید خالی باشد.")
    return value


def _optional_str(value: object, label: str) -> str:
    if value is None:
        return ""
    return _require_str(value, label, allow_empty=True)


def _require_finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecordValidationError(f"«{label}» باید عدد باشد.")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise RecordValidationError(f"«{label}» باید عدد متناهی باشد.")
    return number


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _require_finite_number(value, label)


def _require_int(value: object, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecordValidationError(f"«{label}» باید عدد صحیح باشد.")
    if minimum is not None and value < minimum:
        raise RecordValidationError(f"«{label}» نباید از {minimum} کمتر باشد.")
    return value


def _require_sha256(value: object, label: str) -> str:
    text = _require_str(value, label)
    if not _SHA256_RE.match(text):
        raise RecordValidationError(
            f"«{label}» باید یک هش SHA-256 با ۶۴ کاراکتر مبنای ۱۶ کوچک باشد."
        )
    return text


def normalize_iso_datetime(value: object, label: str) -> str:
    """Validate an ISO-8601 timestamp and return it with ``Z`` normalized."""

    text = _require_str(value, label)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RecordValidationError(
            f"«{label}» باید یک تاریخ/ساعت ISO-8601 معتبر باشد."
        ) from exc
    return normalized


def validate_relative_path(
    path: object,
    label: str = "مسیر",
    allowed_roots: tuple[str, ...] = ALLOWED_LIBRARY_ROOTS,
) -> str:
    """Validate a library-root-relative POSIX path per the Phase 2 contract."""

    text = _require_str(path, label)
    if "\\" in text:
        raise RecordValidationError(f"«{label}» باید از جداکننده '/' استفاده کند.")
    if re.match(r"^[A-Za-z]:", text) or text.startswith("/"):
        raise RecordValidationError(f"«{label}» نباید مسیر مطلق باشد.")
    segments = text.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise RecordValidationError(
            f"«{label}» نباید بخش خالی، '.' یا '..' داشته باشد."
        )
    if not any(text.startswith(root) for root in allowed_roots):
        raise RecordValidationError(
            f"«{label}» باید داخل یکی از ریشه‌های مجاز باشد: "
            + "، ".join(allowed_roots)
        )
    return text


def _require_string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise RecordValidationError(f"«{label}» باید یک فهرست باشد.")
    items = tuple(_require_str(item, label) for item in value)
    if len(set(items)) != len(items):
        raise RecordValidationError(f"«{label}» نباید مقدار تکراری داشته باشد.")
    return items


def _require_positive_number(value: object, label: str) -> float:
    number = _require_finite_number(value, label)
    if number <= 0:
        raise RecordValidationError(f"«{label}» باید مثبت باشد.")
    return number


def is_automated_assignable(review_state: str) -> bool:
    """Whether an importer/AI run may set this review state on its own."""

    return review_state in ("unreviewed", "extracted")


# ---------------------------------------------------------------------------
# provenance-bearing engineering facts


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where an engineering fact came from, per the knowledge-base contract."""

    source_hash: str
    page: int | None = None
    table_or_figure: str = ""
    extractor_version: str = ""
    imported_at: str = ""
    confidence: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_hash", _require_sha256(self.source_hash, "هش منبع")
        )
        if self.page is not None:
            object.__setattr__(
                self, "page", _require_int(self.page, "صفحه", minimum=1)
            )
        object.__setattr__(
            self, "table_or_figure", _optional_str(self.table_or_figure, "جدول/شکل")
        )
        object.__setattr__(
            self,
            "extractor_version",
            _optional_str(self.extractor_version, "نسخه استخراج‌کننده"),
        )
        if self.imported_at:
            object.__setattr__(
                self,
                "imported_at",
                normalize_iso_datetime(self.imported_at, "زمان درون‌ریزی"),
            )
        if self.confidence is not None:
            confidence = _require_finite_number(self.confidence, "اطمینان")
            if not 0.0 <= confidence <= 1.0:
                raise RecordValidationError("«اطمینان» باید بین ۰ و ۱ باشد.")
            object.__setattr__(self, "confidence", confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_hash": self.source_hash,
            "page": self.page,
            "table_or_figure": self.table_or_figure,
            "extractor_version": self.extractor_version,
            "imported_at": self.imported_at,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Provenance":
        _reject_unknown_keys(data, "provenance", cls)
        return cls(
            source_hash=data["source_hash"],
            page=data.get("page"),
            table_or_figure=data.get("table_or_figure", ""),
            extractor_version=data.get("extractor_version", ""),
            imported_at=data.get("imported_at", ""),
            confidence=data.get("confidence"),
        )


@dataclass(frozen=True, slots=True)
class EvidenceField:
    """One named engineering value with full provenance and review state."""

    name: str
    value: float | str | bool | None
    unit: str = ""
    value_min: float | None = None
    value_typ: float | None = None
    value_max: float | None = None
    conditions: str = ""
    provenance: Provenance | None = None
    review_state: str = "unreviewed"
    reviewed_by: str = ""
    reviewed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_str(self.name, "نام فیلد"))
        if not isinstance(self.value, (int, float, str, bool)) and (
            self.value is not None
        ):
            raise RecordValidationError("مقدار فیلد باید عدد، متن، بولی یا تهی باشد.")
        if isinstance(self.value, float) and (
            self.value != self.value or self.value in (float("inf"), float("-inf"))
        ):
            raise RecordValidationError("مقدار عددی فیلد باید متناهی باشد.")
        object.__setattr__(self, "unit", _optional_str(self.unit, "یکند"))
        object.__setattr__(
            self, "conditions", _optional_str(self.conditions, "شرایط")
        )
        bounds = [
            _optional_number(value, label)
            for label, value in (
                ("حداقل مقدار", self.value_min),
                ("مقدار نوعی", self.value_typ),
                ("حداکثر مقدار", self.value_max),
            )
        ]
        present = [bound for bound in bounds if bound is not None]
        if present != sorted(present):
            raise RecordValidationError(
                "ترتیب min/typ/max فیلد باید ناوردا باشد (min ≤ typ ≤ max)."
            )
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise RecordValidationError("سندیت فیلد معتبر نیست.")
        if self.review_state not in REVIEW_STATES:
            raise RecordValidationError(
                "وضعیت بازبینی باید یکی از این‌ها باشد: " + "، ".join(REVIEW_STATES)
            )
        object.__setattr__(
            self, "reviewed_by", _optional_str(self.reviewed_by, "بازبین")
        )
        if self.reviewed_at:
            object.__setattr__(
                self,
                "reviewed_at",
                normalize_iso_datetime(self.reviewed_at, "زمان بازبینی"),
            )
        if self.review_state == "verified":
            if not self.reviewed_by or not self.reviewed_at:
                raise RecordValidationError(
                    "فیلد «verified» باید بازبین و زمان بازبینی داشته باشد."
                )
        if (self.reviewed_by or self.reviewed_at) and (
            self.review_state not in HUMAN_REVIEW_STATES
        ):
            raise RecordValidationError(
                "بازبین/زمان بازبینی فقط برای وضعیت‌های بازبینی انسانی معتبر است."
            )

    @property
    def is_human_verified(self) -> bool:
        return self.review_state == "verified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "value_min": self.value_min,
            "value_typ": self.value_typ,
            "value_max": self.value_max,
            "conditions": self.conditions,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "review_state": self.review_state,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceField":
        _reject_unknown_keys(data, "field", cls)
        provenance = data.get("provenance")
        return cls(
            name=data["name"],
            value=data.get("value"),
            unit=data.get("unit", ""),
            value_min=data.get("value_min"),
            value_typ=data.get("value_typ"),
            value_max=data.get("value_max"),
            conditions=data.get("conditions", ""),
            provenance=(
                Provenance.from_dict(provenance) if provenance is not None else None
            ),
            review_state=data.get("review_state", "unreviewed"),
            reviewed_by=data.get("reviewed_by", ""),
            reviewed_at=data.get("reviewed_at", ""),
        )


def _require_fields(
    values: object, label: str
) -> tuple[EvidenceField, ...]:
    if not isinstance(values, (list, tuple)):
        raise RecordValidationError(f"«{label}» باید یک فهرست باشد.")
    fields_tuple = tuple(
        value if isinstance(value, EvidenceField) else EvidenceField.from_dict(value)
        for value in values
    )
    names = [field.name for field in fields_tuple]
    if len(set(names)) != len(names):
        raise RecordValidationError(f"«{label}» نباید نام فیلد تکراری داشته باشد.")
    return fields_tuple


# ---------------------------------------------------------------------------
# identity types


@dataclass(frozen=True, slots=True)
class Alias:
    """An alternate name by which a part or document is known."""

    value: str
    kind: str = "part-number"
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_str(self.value, "نام مستعار"))
        if self.kind not in ALIAS_KINDS:
            raise RecordValidationError(
                "نوع نام مستعار باید یکی از این‌ها باشد: " + "، ".join(ALIAS_KINDS)
            )
        object.__setattr__(self, "note", _optional_str(self.note, "یادداشت مستعار"))

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "kind": self.kind, "note": self.note}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Alias":
        _reject_unknown_keys(data, "alias", cls)
        return cls(
            value=data["value"],
            kind=data.get("kind", "part-number"),
            note=data.get("note", ""),
        )


def _require_aliases(values: object, label: str) -> tuple[Alias, ...]:
    if not isinstance(values, (list, tuple)):
        raise RecordValidationError(f"«{label}» باید یک فهرست باشد.")
    aliases = tuple(
        value if isinstance(value, Alias) else Alias.from_dict(value)
        for value in values
    )
    keys = [(alias.value.casefold(), alias.kind) for alias in aliases]
    if len(set(keys)) != len(keys):
        raise RecordValidationError(f"«{label}» نباید مورد تکراری داشته باشد.")
    return aliases


@dataclass(frozen=True, slots=True)
class SourceObject:
    """One immutable source file, identified only by its content hash."""

    sha256: str
    size_bytes: int
    media_type: str
    original_filename: str
    source_urls: tuple[str, ...] = ()
    aliases: tuple[Alias, ...] = ()
    imported_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "هش شیء"))
        object.__setattr__(
            self, "size_bytes", _require_int(self.size_bytes, "حجم بایت", minimum=0)
        )
        object.__setattr__(
            self, "media_type", _require_str(self.media_type, "نوع رسانه")
        )
        filename = _require_str(self.original_filename, "نام فایل اصلی")
        if "/" in filename or "\\" in filename or re.match(r"^[A-Za-z]:", filename):
            raise RecordValidationError("نام فایل اصلی نباید مسیر باشد.")
        object.__setattr__(self, "original_filename", filename)
        object.__setattr__(
            self,
            "source_urls",
            _require_string_tuple(self.source_urls, "نشانی منبع"),
        )
        object.__setattr__(self, "aliases", _require_aliases(self.aliases, "مستعارات"))
        if self.imported_at:
            object.__setattr__(
                self,
                "imported_at",
                normalize_iso_datetime(self.imported_at, "زمان درون‌ریزی"),
            )

    def merged(self, other: "SourceObject") -> "SourceObject":
        """Deterministically resolve a duplicate (same-hash) source object."""

        if other.sha256 != self.sha256:
            raise RecordValidationError(
                "ادغام اشیاء منبع فقط برای هش‌های یکسان تعریف شده است."
            )
        if other.size_bytes != self.size_bytes:
            raise RecordValidationError(
                "حجم دو شیء منبع با هش یکسان نباید متفاوت باشد."
            )

        def union_first(pairs: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
            seen: list[tuple[str, str]] = []
            for pair in pairs:
                if pair not in seen:
                    seen.append(pair)
            return tuple(seen)

        alias_pairs = union_first(
            tuple((alias.value, alias.kind) for alias in self.aliases)
            + tuple((alias.value, alias.kind) for alias in other.aliases)
        )
        alias_notes = {(alias.value, alias.kind): alias.note for alias in other.aliases}
        for alias in self.aliases:
            key = (alias.value, alias.kind)
            alias_notes[key] = alias.note or alias_notes.get(key, "")
        url_union = tuple(
            dict.fromkeys(self.source_urls + other.source_urls)
        )
        return SourceObject(
            sha256=self.sha256,
            size_bytes=self.size_bytes,
            media_type=self.media_type or other.media_type,
            original_filename=self.original_filename or other.original_filename,
            source_urls=url_union,
            aliases=tuple(
                Alias(
                    value=value,
                    kind=kind,
                    note=alias_notes[(value, kind)],
                )
                for value, kind in alias_pairs
            ),
            imported_at=self.imported_at or other.imported_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "original_filename": self.original_filename,
            "source_urls": list(self.source_urls),
            "aliases": [alias.to_dict() for alias in self.aliases],
            "imported_at": self.imported_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceObject":
        _reject_unknown_keys(data, "source object", cls)
        return cls(
            sha256=data["sha256"],
            size_bytes=data["size_bytes"],
            media_type=data["media_type"],
            original_filename=data["original_filename"],
            source_urls=tuple(data.get("source_urls", ())),
            aliases=tuple(
                Alias.from_dict(alias) for alias in data.get("aliases", ())
            ),
            imported_at=data.get("imported_at", ""),
        )


@dataclass(frozen=True, slots=True)
class DocumentRevision:
    """A specific revision of a document bound to one source object."""

    manufacturer: str
    part_number: str
    document_type: str
    revision: str
    object_sha256: str
    record_path: str
    title: str = ""
    date: str = ""
    page_count: int | None = None
    aliases: tuple[Alias, ...] = ()
    tags: tuple[str, ...] = ()
    summary: str = ""
    fields: tuple[EvidenceField, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "manufacturer", _require_str(self.manufacturer, "سازنده")
        )
        object.__setattr__(
            self, "part_number", _require_str(self.part_number, "شماره قطعه")
        )
        if self.document_type not in DOCUMENT_TYPES:
            raise RecordValidationError(
                "نوع سند باید یکی از این‌ها باشد: " + "، ".join(DOCUMENT_TYPES)
            )
        object.__setattr__(self, "revision", _require_str(self.revision, "نسخه سند"))
        object.__setattr__(
            self, "object_sha256", _require_sha256(self.object_sha256, "هش شیء منبع")
        )
        object.__setattr__(
            self,
            "record_path",
            validate_relative_path(self.record_path, "مسیر رکورد"),
        )
        object.__setattr__(self, "title", _optional_str(self.title, "عنوان"))
        object.__setattr__(self, "date", _optional_str(self.date, "تاریخ سند"))
        if self.page_count is not None:
            object.__setattr__(
                self,
                "page_count",
                _require_int(self.page_count, "تعداد صفحه", minimum=1),
            )
        object.__setattr__(self, "aliases", _require_aliases(self.aliases, "مستعارات"))
        object.__setattr__(self, "tags", _require_string_tuple(self.tags, "برچسب‌ها"))
        object.__setattr__(self, "summary", _optional_str(self.summary, "خلاصه"))
        object.__setattr__(self, "fields", _require_fields(self.fields, "فیلدها"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "document_type": self.document_type,
            "revision": self.revision,
            "object_sha256": self.object_sha256,
            "record_path": self.record_path,
            "title": self.title,
            "date": self.date,
            "page_count": self.page_count,
            "aliases": [alias.to_dict() for alias in self.aliases],
            "tags": list(self.tags),
            "summary": self.summary,
            "fields": [field.to_dict() for field in self.fields],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DocumentRevision":
        _reject_unknown_keys(data, "document revision", cls)
        return cls(
            manufacturer=data["manufacturer"],
            part_number=data["part_number"],
            document_type=data["document_type"],
            revision=data["revision"],
            object_sha256=data["object_sha256"],
            record_path=data["record_path"],
            title=data.get("title", ""),
            date=data.get("date", ""),
            page_count=data.get("page_count"),
            aliases=tuple(Alias.from_dict(a) for a in data.get("aliases", ())),
            tags=tuple(data.get("tags", ())),
            summary=data.get("summary", ""),
            fields=tuple(
                EvidenceField.from_dict(f) for f in data.get("fields", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class ComponentProfile:
    """Reviewed engineering facts for one component document revision."""

    manufacturer: str
    part_number: str
    profile_version: str
    source_object_sha256: str
    source_revision: str = ""
    package: str = ""
    device_type: str = ""
    aliases: tuple[Alias, ...] = ()
    fields: tuple[EvidenceField, ...] = ()
    contradictions: tuple[str, ...] = ()
    unknown_facts: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "manufacturer", _require_str(self.manufacturer, "سازنده")
        )
        object.__setattr__(
            self, "part_number", _require_str(self.part_number, "شماره قطعه")
        )
        object.__setattr__(
            self,
            "profile_version",
            _require_str(self.profile_version, "نسخه پروفایل"),
        )
        object.__setattr__(
            self,
            "source_object_sha256",
            _require_sha256(self.source_object_sha256, "هش شیء منبع"),
        )
        object.__setattr__(
            self,
            "source_revision",
            _optional_str(self.source_revision, "نسخه سند منبع"),
        )
        object.__setattr__(self, "package", _optional_str(self.package, "پکیج"))
        object.__setattr__(
            self, "device_type", _optional_str(self.device_type, "نوع قطعه")
        )
        object.__setattr__(self, "aliases", _require_aliases(self.aliases, "مستعارات"))
        object.__setattr__(self, "fields", _require_fields(self.fields, "فیلدها"))
        object.__setattr__(
            self,
            "contradictions",
            _require_string_tuple(self.contradictions, "تناقض‌ها"),
        )
        object.__setattr__(
            self,
            "unknown_facts",
            _require_string_tuple(self.unknown_facts, "نکات مجهول"),
        )
        object.__setattr__(self, "notes", _optional_str(self.notes, "یادداشت"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "part_number": self.part_number,
            "profile_version": self.profile_version,
            "source_object_sha256": self.source_object_sha256,
            "source_revision": self.source_revision,
            "package": self.package,
            "device_type": self.device_type,
            "aliases": [alias.to_dict() for alias in self.aliases],
            "fields": [field.to_dict() for field in self.fields],
            "contradictions": list(self.contradictions),
            "unknown_facts": list(self.unknown_facts),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ComponentProfile":
        _reject_unknown_keys(data, "component profile", cls)
        return cls(
            manufacturer=data["manufacturer"],
            part_number=data["part_number"],
            profile_version=data["profile_version"],
            source_object_sha256=data["source_object_sha256"],
            source_revision=data.get("source_revision", ""),
            package=data.get("package", ""),
            device_type=data.get("device_type", ""),
            aliases=tuple(Alias.from_dict(a) for a in data.get("aliases", ())),
            fields=tuple(
                EvidenceField.from_dict(f) for f in data.get("fields", ())
            ),
            contradictions=tuple(data.get("contradictions", ())),
            unknown_facts=tuple(data.get("unknown_facts", ())),
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True, slots=True)
class MagneticsRecord:
    """A core, core-set, material, or bobbin record with sourced fields."""

    manufacturer: str
    family: str
    kind: str
    designation: str
    fields: tuple[EvidenceField, ...] = ()
    compatible_bobbins: tuple[str, ...] = ()
    aliases: tuple[Alias, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "manufacturer", _require_str(self.manufacturer, "سازنده")
        )
        object.__setattr__(self, "family", _require_str(self.family, "خانواده"))
        if self.kind not in MAGNETICS_KINDS:
            raise RecordValidationError(
                "نوع رکورد مغناطیسی باید یکی از این‌ها باشد: "
                + "، ".join(MAGNETICS_KINDS)
            )
        object.__setattr__(
            self, "designation", _require_str(self.designation, "شناسه قطعه")
        )
        object.__setattr__(self, "fields", _require_fields(self.fields, "فیلدها"))
        object.__setattr__(
            self,
            "compatible_bobbins",
            _require_string_tuple(
                self.compatible_bobbins, "بوبین‌های سازگار"
            ),
        )
        object.__setattr__(self, "aliases", _require_aliases(self.aliases, "مستعارات"))
        object.__setattr__(self, "notes", _optional_str(self.notes, "یادداشت"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "family": self.family,
            "kind": self.kind,
            "designation": self.designation,
            "fields": [field.to_dict() for field in self.fields],
            "compatible_bobbins": list(self.compatible_bobbins),
            "aliases": [alias.to_dict() for alias in self.aliases],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MagneticsRecord":
        _reject_unknown_keys(data, "magnetics record", cls)
        return cls(
            manufacturer=data["manufacturer"],
            family=data["family"],
            kind=data["kind"],
            designation=data["designation"],
            fields=tuple(
                EvidenceField.from_dict(f) for f in data.get("fields", ())
            ),
            compatible_bobbins=tuple(data.get("compatible_bobbins", ())),
            aliases=tuple(Alias.from_dict(a) for a in data.get("aliases", ())),
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True, slots=True)
class LibraryIdentity:
    """The portable library identity stored in ``library.toml``."""

    library_id: str
    name: str
    created_at: str
    last_modified_at: str = ""
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _UUID_RE.match(_require_str(self.library_id, "شناسه کتابخانه")):
            raise RecordValidationError(
                "شناسه کتابخانه باید یک UUID مبنای ۱۶ بدون خط تیره باشد."
            )
        object.__setattr__(self, "name", _require_str(self.name, "نام کتابخانه"))
        object.__setattr__(
            self,
            "created_at",
            normalize_iso_datetime(self.created_at, "زمان ساخت"),
        )
        if self.last_modified_at:
            object.__setattr__(
                self,
                "last_modified_at",
                normalize_iso_datetime(
                    self.last_modified_at, "زمان آخرین تغییر"
                ),
            )
        if self.schema_version != SCHEMA_VERSION:
            raise KnowledgeBaseVersionError(
                f"نسخه اسکیمای کتابخانه {self.schema_version} پشتیبانی نمی‌شود؛ "
                f"نسخه جاری {SCHEMA_VERSION} است."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "library_id": self.library_id,
            "name": self.name,
            "created_at": self.created_at,
            "last_modified_at": self.last_modified_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LibraryIdentity":
        _reject_unknown_keys(data, "library identity", cls)
        return cls(
            library_id=data["library_id"],
            name=data["name"],
            created_at=data["created_at"],
            last_modified_at=data.get("last_modified_at", ""),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


# ---------------------------------------------------------------------------
# envelope (de)serialization


RECORD_KINDS: dict[str, type] = {
    "source-object": SourceObject,
    "document-revision": DocumentRevision,
    "component-profile": ComponentProfile,
    "magnetics-record": MagneticsRecord,
}

RECORD_KIND_BY_TYPE: dict[type, str] = {v: k for k, v in RECORD_KINDS.items()}


def _reject_unknown_keys(
    data: Mapping[str, Any], label: str, record_type: type
) -> None:
    if not isinstance(data, Mapping):
        raise RecordValidationError(f"ساختار {label} باید یک نگاشت باشد.")
    known = {field.name for field in dataclass_fields(record_type)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise RecordValidationError(
            f"{label} کلیدهای ناشناخته دارد و پذیرفته نمی‌شود: "
            + "، ".join(unknown)
        )


def dump_record(record: object) -> str:
    """Serialize one record into its versioned envelope as UTF-8 JSON."""

    kind = RECORD_KIND_BY_TYPE.get(type(record))
    if kind is None:
        raise RecordValidationError("نوع رکورد برای سریال‌سازی پشتیبانی نمی‌شود.")
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "record_kind": kind,
        "record": record.to_dict(),  # type: ignore[attr-defined]
    }
    return json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"


def load_record(data: str | Mapping[str, Any]) -> object:
    """Load and validate one record from its versioned envelope."""

    if isinstance(data, str):
        try:
            parsed: Any = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RecordValidationError(f"رکورد JSON معتبر نیست: {exc}") from exc
    else:
        parsed = data
    if not isinstance(parsed, Mapping):
        raise RecordValidationError("ساختار پوشهٔ رکورد باید یک نگاشت باشد.")
    version = parsed.get("schema_version")
    if version != SCHEMA_VERSION:
        raise KnowledgeBaseVersionError(
            f"نسخه اسکیمای رکورد {version!r} پشتیبانی نمی‌شود؛ "
            f"نسخه جاری {SCHEMA_VERSION} است."
        )
    kind = parsed.get("record_kind")
    record_type = RECORD_KINDS.get(kind) if isinstance(kind, str) else None
    if record_type is None:
        raise RecordValidationError(f"نوع رکورد ناشناخته است: {kind!r}")
    payload = parsed.get("record")
    if not isinstance(payload, Mapping):
        raise RecordValidationError("بدنهٔ رکورد باید یک نگاشت باشد.")
    return record_type.from_dict(payload)


def dump_library_identity(identity: LibraryIdentity) -> str:
    return json.dumps(identity.to_dict(), ensure_ascii=False, indent=2) + "\n"


def load_library_identity(data: str | Mapping[str, Any]) -> LibraryIdentity:
    if isinstance(data, str):
        try:
            parsed: Any = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RecordValidationError(f"شناسه کتابخانه JSON معتبر نیست: {exc}") from exc
    else:
        parsed = data
    if not isinstance(parsed, Mapping):
        raise RecordValidationError("شناسه کتابخانه باید یک نگاشت باشد.")
    return LibraryIdentity.from_dict(parsed)
