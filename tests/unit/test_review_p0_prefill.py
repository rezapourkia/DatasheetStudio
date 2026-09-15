"""Review P0: unreviewed AI values must not prefill Flyback inputs."""

import pytest

from datasheet_studio.models.controller_profile import ControllerProfile
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance
from datasheet_studio.tools.flyback_designer.tool import FlybackDesignerTool
from datasheet_studio.tools.registry import ToolContext

HASH = "a" * 64


def field(name, value, state):
    extra = (
        {"reviewed_by": "Reza", "reviewed_at": "2026-09-15T00:00:00+00:00"}
        if state in ("reviewed", "verified")
        else {}
    )
    return EvidenceField(
        name=name, value=value, unit={"frequency_khz": "kHz",
        "current_limit_a": "A", "switch_voltage_limit_v": "V"}[name],
        provenance=Provenance(source_hash=HASH, page=1),
        review_state=state, **extra,
    )


def run_tool(profile):
    captured = {}

    class _Dialog:
        def __init__(self, parent=None, *, prefill=None, controller_meta=None):
            captured["prefill"] = prefill or {}
            captured["meta"] = controller_meta or {}

        def exec(self):
            return 0

    import datasheet_studio.tools.flyback_designer.dialog as dialog_module

    original = dialog_module.FlybackDesignerDialog
    dialog_module.FlybackDesignerDialog = _Dialog
    try:
        FlybackDesignerTool().run(ToolContext(controller_profile=profile))
    finally:
        dialog_module.FlybackDesignerDialog = original
    return captured["prefill"], captured["meta"]


def test_mixed_profile_prefills_only_accepted_values():
    profile = ControllerProfile(
        manufacturer="Linkage", part_number="DK124", source_object_sha256=HASH,
        fields=(
            field("frequency_khz", 65.0, "reviewed"),
            field("current_limit_a", 1.1, "extracted"),
        ),
    )
    prefill, _meta = run_tool(profile)
    assert prefill.get("frequency_khz") == 65.0
    assert "current_limit_a" not in prefill  # extracted must NOT prefill


def test_all_extracted_profile_prefills_no_engineering_values():
    profile = ControllerProfile(
        manufacturer="Linkage", part_number="DK124", source_object_sha256=HASH,
        fields=(
            field("frequency_khz", 65.0, "extracted"),
            field("current_limit_a", 1.1, "extracted"),
        ),
    )
    prefill, _meta = run_tool(profile)
    for key in ("frequency_khz", "current_limit_a", "switch_voltage_limit_v"):
        assert key not in prefill
    # identity is not an engineering value and may still identify the part
    assert prefill.get("ic_id") == "DK124"


def test_banner_reports_per_required_field_not_whole_profile_acceptance():
    profile = ControllerProfile(
        manufacturer="Linkage", part_number="DK124", source_object_sha256=HASH,
        fields=(field("frequency_khz", 65.0, "reviewed"),),
    )
    _prefill, meta = run_tool(profile)
    text = meta.get("required_fields", "")
    # per-field states must be listed, not a blanket accepted/unreviewed claim
    assert "frequency_khz" in text and "پذیرفته" in text
    assert "current_limit_a" in text and "مجهول" in text
    assert meta.get("status") != "پذیرفته‌شده (بازبینی/تأیید)"


def test_extracted_values_are_surfaced_as_inactive_suggestions():
    profile = ControllerProfile(
        manufacturer="Linkage", part_number="DK124", source_object_sha256=HASH,
        fields=(
            field("frequency_khz", 65.0, "reviewed"),
            field("current_limit_a", 1.1, "extracted"),
        ),
    )
    _prefill, meta = run_tool(profile)
    suggestions = meta.get("suggestions", "")
    assert "current_limit_a" in suggestions and "1.1" in suggestions
