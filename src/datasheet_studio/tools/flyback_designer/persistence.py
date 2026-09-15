"""Versioned JSON persistence for native Flyback Designer projects."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .engine import ComponentSpec, CoreSpec, FlybackProject, OutputSpec


SCHEMA_VERSION = 1


class FlybackProjectFileError(ValueError):
    """Raised when a saved Flyback Designer file is invalid or unsupported."""


def bundle_to_dict(
    project: FlybackProject,
    core: CoreSpec,
    parts: Sequence[ComponentSpec],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": asdict(project),
        "core": asdict(core),
        "parts": [asdict(part) for part in parts],
    }


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FlybackProjectFileError(f"بخش «{label}» در فایل معتبر نیست.")
    return value


def bundle_from_dict(
    data: Mapping[str, Any],
) -> tuple[FlybackProject, CoreSpec, tuple[ComponentSpec, ...]]:
    if not isinstance(data, Mapping):
        raise FlybackProjectFileError("ساختار اصلی فایل معتبر نیست.")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise FlybackProjectFileError("نسخه فایل پروژه پشتیبانی نمی‌شود.")

    try:
        project_data = dict(_mapping(data.get("project"), "project"))
        outputs_data = project_data.pop("outputs")
        if not isinstance(outputs_data, list):
            raise FlybackProjectFileError("فهرست خروجی‌ها معتبر نیست.")
        project = FlybackProject(
            **project_data,
            outputs=[OutputSpec(**dict(_mapping(item, "output"))) for item in outputs_data],
        )
        core = CoreSpec(**dict(_mapping(data.get("core"), "core")))
        parts_data = data.get("parts", [])
        if not isinstance(parts_data, list):
            raise FlybackProjectFileError("فهرست قطعات معتبر نیست.")
        parts = tuple(
            ComponentSpec(**dict(_mapping(item, "part"))) for item in parts_data
        )
    except FlybackProjectFileError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise FlybackProjectFileError(f"فایل پروژه ناقص یا نامعتبر است: {exc}") from exc

    return project, core, parts


def save_bundle(
    path: str | Path,
    project: FlybackProject,
    core: CoreSpec,
    parts: Sequence[ComponentSpec],
) -> None:
    payload = json.dumps(
        bundle_to_dict(project, core, parts),
        ensure_ascii=False,
        indent=2,
    )
    Path(path).write_text(payload + "\n", encoding="utf-8")


def load_bundle(
    path: str | Path,
) -> tuple[FlybackProject, CoreSpec, tuple[ComponentSpec, ...]]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FlybackProjectFileError(f"خواندن فایل پروژه ممکن نشد: {exc}") from exc
    return bundle_from_dict(data)

