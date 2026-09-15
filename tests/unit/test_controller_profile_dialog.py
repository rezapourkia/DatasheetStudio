"""Offscreen tests for the controller profile form (Phase 8)."""

from PySide6.QtWidgets import QFileDialog

from datasheet_studio.models.controller_profile import (
    ControllerProfile,
    dump_controller_profile,
    load_controller_profile,
)
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance
from datasheet_studio.ui.dialogs.controller_profile_dialog import ControllerProfileDialog

HASH = "b" * 64


def sample_profile():
    return ControllerProfile(
        manufacturer="Linkage",
        part_number="DK124",
        source_object_sha256=HASH,
        fields=(
            EvidenceField(
                name="frequency_khz", value=65.0, unit="kHz",
                provenance=Provenance(source_hash=HASH, page=2, table_or_figure="T1"),
                review_state="reviewed",
                reviewed_by="Reza", reviewed_at="2026-09-15T00:00:00+00:00",
            ),
        ),
    )


def test_form_covers_all_spec_fields_and_loads_profile(qapp_instance):
    dialog = ControllerProfileDialog(part_number="DK124", manufacturer="Linkage")
    assert set(dialog._rows) == set(dialog._rows)  # populated
    assert len(dialog._rows) >= 25

    dialog.load_profile(sample_profile())
    assert dialog._rows["frequency_khz"]["value"].text() == "65.0"
    assert dialog._rows["frequency_khz"]["page"].value() == 2
    state_data = dialog._rows["frequency_khz"]["state"].currentData()
    assert state_data == "reviewed"
    dialog.close()


def test_collect_and_round_trip_through_file(qapp_instance, tmp_path, monkeypatch):
    dialog = ControllerProfileDialog(
        part_number="DK124", manufacturer="Linkage", source_hash=HASH
    )
    dialog._rows["frequency_khz"]["value"].setText("65")
    dialog._rows["frequency_khz"]["state"].setCurrentIndex(3)  # verified
    dialog._rows["current_limit_a"]["value"].setText("1.1")
    dialog._rows["current_limit_a"]["state"].setCurrentIndex(2)  # reviewed

    profile = dialog._collect_profile()
    assert profile.engine_view().values["frequency_khz"].value == 65.0
    assert profile.engine_view().values["frequency_khz"].review_state == "verified"

    target = tmp_path / "dk124.controller.json"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    dialog._vault_path_getter = lambda: ""  # force file save
    dialog._save_profile()
    assert target.is_file()
    loaded = load_controller_profile(target.read_text(encoding="utf-8"))
    assert loaded.part_number == "DK124"
    dialog.close()


def test_registry_contains_controller_profile_tool():
    from datasheet_studio.tools import create_default_tool_registry

    registry = create_default_tool_registry()
    assert registry.get("controller-profile").category == "Knowledge Base"
