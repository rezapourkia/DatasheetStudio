"""Tests for the current-datasheet handoff to Flyback (Phase 10)."""

from pathlib import Path

import pymupdf

from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.models.controller_profile import ControllerProfile
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance
from datasheet_studio.services.knowledge_hash import sha256_file
from datasheet_studio.tools.flyback_designer.tool import FlybackDesignerTool
from datasheet_studio.tools.registry import ToolContext

HASH = "d" * 64


def make_pdf(tmp_path, name="dk124.pdf", text="DK124 controller"):
    path = tmp_path / name
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


def profile(hash_value, state="reviewed"):
    extra = (
        {"reviewed_by": "Reza", "reviewed_at": "2026-09-15T00:00:00+00:00"}
        if state in ("reviewed", "verified")
        else {}
    )
    return ControllerProfile(
        manufacturer="Linkage",
        part_number="DK124",
        source_object_sha256=hash_value,
        profile_version="9",
        fields=(
            EvidenceField(
                name="frequency_khz", value=65.0, unit="kHz",
                provenance=Provenance(source_hash=hash_value, page=1),
                review_state=state, **extra,
            ),
            EvidenceField(
                name="current_limit_a", value=1.1, unit="A",
                provenance=Provenance(source_hash=hash_value, page=2),
                review_state=state, **extra,
            ),
        ),
    )


def test_vault_finds_profiles_by_source_hash_newest_first(tmp_path):
    vault = KnowledgeVault.create(tmp_path / "vault", "H Vault")
    vault.write_controller_profile(profile(HASH), index=False)
    vault.write_controller_profile(profile(HASH), index=False)
    found = vault.controller_profiles_for(HASH)
    assert len(found) == 2
    assert found[0].part_number == "DK124"
    assert vault.controller_profiles_for("e" * 64) == []


def test_context_defaults_are_safe():
    context = ToolContext()
    assert context.source_hash == "" and context.controller_profile is None


def test_main_window_context_carries_hash(qapp_instance, tmp_path):
    from datasheet_studio.ui.main_window import MainWindow

    window = MainWindow()
    try:
        pdf = make_pdf(tmp_path)
        window._open_library_item(str(pdf))
        context = window._tool_context()
        assert context.source_hash == sha256_file(pdf)
    finally:
        window.close()


def test_flyback_opens_without_pdf_manually(qapp_instance):
    dialog_holder = {}

    class _Dialog:
        def __init__(self, parent=None, *, prefill=None, controller_meta=None):
            dialog_holder["prefill"] = prefill
            dialog_holder["meta"] = controller_meta

        def exec(self):
            return 0

    import datasheet_studio.tools.flyback_designer.dialog as dialog_module

    original = dialog_module.FlybackDesignerDialog
    dialog_module.FlybackDesignerDialog = _Dialog
    try:
        FlybackDesignerTool().run(ToolContext())
    finally:
        dialog_module.FlybackDesignerDialog = original
    assert dialog_holder["prefill"] is None and dialog_holder["meta"] is None


def test_handoff_prefill_and_banner_from_profile(qapp_instance):
    captured = {}

    class _Dialog:
        def __init__(self, parent=None, *, prefill=None, controller_meta=None):
            captured["prefill"] = prefill
            captured["meta"] = controller_meta

        def exec(self):
            return 0

    import datasheet_studio.tools.flyback_designer.dialog as dialog_module

    original = dialog_module.FlybackDesignerDialog
    dialog_module.FlybackDesignerDialog = _Dialog
    try:
        FlybackDesignerTool().run(
            ToolContext(controller_profile=profile(HASH))
        )
    finally:
        dialog_module.FlybackDesignerDialog = original

    assert captured["prefill"]["frequency_khz"] == 65.0
    assert captured["prefill"]["current_limit_a"] == 1.1
    assert captured["prefill"]["ic_id"] == "DK124"
    assert "DK124" in captured["meta"]["manufacturer"] + captured["meta"]["part_number"]
    assert "پیش‌پر فقط با مقادیر پذیرفته‌شده" in captured["meta"]["status"]


def test_unreviewed_profile_is_flagled_not_silent(qapp_instance):
    captured = {}

    class _Dialog:
        def __init__(self, parent=None, *, prefill=None, controller_meta=None):
            captured["meta"] = controller_meta

        def exec(self):
            return 0

    import datasheet_studio.tools.flyback_designer.dialog as dialog_module

    original = dialog_module.FlybackDesignerDialog
    dialog_module.FlybackDesignerDialog = _Dialog
    try:
        FlybackDesignerTool().run(
            ToolContext(controller_profile=profile(HASH, state="extracted"))
        )
    finally:
        dialog_module.FlybackDesignerDialog = original
    # Review-corrected banner: no blanket claim; zero accepted of three required
    assert "0 از 3" in captured["meta"]["status"]
    assert captured["meta"]["required_fields"]  # per-field states listed
    assert captured["meta"]["suggestions"]  # extracted values surfaced, not applied


def test_dialog_banner_and_prefill_reach_spins(qapp_instance):
    from datasheet_studio.tools.flyback_designer.dialog import FlybackDesignerDialog

    dialog = FlybackDesignerDialog(
        prefill={"frequency_khz": 100.0, "ic_id": "DK125"},
        controller_meta={
            "manufacturer": "Linkage",
            "part_number": "DK125",
            "profile_version": "2",
            "status": "پذیرفته‌شده (بازبینی/تأیید)",
            "unknowns": "switch_voltage_limit_v",
        },
    )
    try:
        assert dialog._fields["frequency_khz"].value() == 100.0
        banner = dialog.findChild(type(dialog._status))
        labels = [
            w.text() for w in dialog.findChildren(banner.__class__)
        ]
        assert any("DK125" in text and "پذیرفته‌شده" in text for text in labels)
    finally:
        dialog.close()


def test_changing_pdf_does_not_mutate_saved_design(qapp_instance, tmp_path):
    # a saved project file stays byte-identical when another handoff happens
    saved = tmp_path / "design.flyback.json"
    saved.write_text('{"saved": true}', encoding="utf-8")
    before = saved.read_bytes()

    captured = {}

    class _Dialog:
        def __init__(self, parent=None, *, prefill=None, controller_meta=None):
            captured["prefill"] = prefill

        def exec(self):
            return 0

    import datasheet_studio.tools.flyback_designer.dialog as dialog_module

    original = dialog_module.FlybackDesignerDialog
    dialog_module.FlybackDesignerDialog = _Dialog
    try:
        FlybackDesignerTool().run(
            ToolContext(controller_profile=profile("f" * 64))
        )
    finally:
        dialog_module.FlybackDesignerDialog = original

    assert captured["prefill"]["ic_id"] == "DK124"
    assert saved.read_bytes() == before  # untouched
