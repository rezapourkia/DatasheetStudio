"""Schema tests for controller profiles (Phase 8)."""

from pathlib import Path

import pytest

from datasheet_studio.models.controller_profile import (
    FIELD_SPECS,
    ControllerProfile,
    ControllerProfileError,
    dump_controller_profile,
    load_controller_profile,
)
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance
from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault

HASH = "a" * 64


def f(name, value, *, unit=None, state="reviewed", page=3):
    spec = FIELD_SPECS[name]
    return EvidenceField(
        name=name,
        value=value,
        unit=unit if unit is not None else spec.unit,
        provenance=Provenance(source_hash=HASH, page=page, table_or_figure="Table 1"),
        review_state=state,
        **({"reviewed_by": "Reza", "reviewed_at": "2026-09-15T00:00:00+00:00"}
           if state in ("reviewed", "verified") else {}),
    )


def complete_profile():
    return ControllerProfile(
        manufacturer="Linkage",
        part_number="DK124",
        source_object_sha256=HASH,
        fields=(
            f("frequency_khz", 65.0),
            f("current_limit_a", 1.1),
            f("switch_voltage_limit_v", 700.0),
            f("control_mode", "fixed-frequency"),
        ),
    )


def test_complete_fixture_engine_view_has_required_values():
    engine = complete_profile().engine_view()
    assert engine.values["frequency_khz"].value == 65.0
    assert engine.values["frequency_khz"].unit == "kHz"
    assert engine.values["frequency_khz"].page == 3
    assert not engine.has_required_unknowns
    assert "control_mode" in engine.values
    # optional unset fields are explicit unknowns, never zeros
    assert "rdson_ohm" in engine.unknowns


def test_partial_fixture_lists_unknowns_including_required():
    profile = ControllerProfile(
        manufacturer="X",
        part_number="Y",
        source_object_sha256=HASH,
        fields=(f("frequency_khz", 65.0),),
    )
    engine = profile.engine_view()
    assert "current_limit_a" in engine.unknowns
    assert engine.has_required_unknowns is True
    assert not profile.is_structurally_complete


def test_extracted_only_field_is_not_accepted_for_engine():
    profile = ControllerProfile(
        manufacturer="X", part_number="Y", source_object_sha256=HASH,
        fields=(f("current_limit_a", 1.2, state="extracted"),),
    )
    engine = profile.engine_view()
    assert "current_limit_a" not in engine.values
    assert "current_limit_a" in engine.unknowns


def test_contradictions_surface_in_engine_view():
    profile = ControllerProfile(
        manufacturer="X", part_number="Y", source_object_sha256=HASH,
        fields=(f("frequency_khz", 65.0),),
        contradictions=("تناقض: جریان حدی ۱٫۱ یا ۱٫۲ آمپر؟"),
    )
    assert profile.engine_view().contradictions


def test_wrong_unit_is_rejected():
    with pytest.raises(ControllerProfileError, match="kHz"):
        ControllerProfile(
            manufacturer="X", part_number="Y", source_object_sha256=HASH,
            fields=(f("frequency_khz", 65000.0, unit="Hz"),),
        )


def test_wrong_page_is_rejected():
    with pytest.raises(Exception):
        EvidenceField(
            name="frequency_khz", value=65.0, unit="kHz",
            provenance=Provenance(source_hash=HASH, page=0),
        )


def test_unsupported_mode_is_rejected():
    with pytest.raises(ControllerProfileError, match="باید یکی از این"):
        ControllerProfile(
            manufacturer="X", part_number="Y", source_object_sha256=HASH,
            fields=(f("control_mode", "hyperspace"),),
        )


def test_out_of_range_value_is_rejected():
    with pytest.raises(ControllerProfileError, match="حد مجاز"):
        ControllerProfile(
            manufacturer="X", part_number="Y", source_object_sha256=HASH,
            fields=(f("frequency_khz", 999999.0),),
        )


def test_unknown_field_name_is_rejected():
    with pytest.raises(ControllerProfileError, match="شناخته نشد"):
        ControllerProfile(
            manufacturer="X", part_number="Y", source_object_sha256=HASH,
            fields=(EvidenceField(name="warp_drive", value=1, provenance=Provenance(source_hash=HASH)),),
        )


def test_ai_extraction_cannot_create_reviewed_field():
    with pytest.raises(ControllerProfileError, match="reviewed.verified"):
        ControllerProfile.from_extraction(
            manufacturer="X", part_number="Y", source_object_sha256=HASH,
            fields=(f("frequency_khz", 65.0, state="verified"),),
        )


def test_envelope_round_trip():
    profile = complete_profile()
    loaded = load_controller_profile(dump_controller_profile(profile))
    assert loaded == profile


def test_envelope_rejects_wrong_kind_and_version():
    with pytest.raises(ControllerProfileError):
        load_controller_profile('{"schema_version": 2, "record_kind": "other", "record": {}}')
    with pytest.raises(Exception):
        load_controller_profile('{"schema_version": 1, "record_kind": "controller-profile", "record": {}}')


def test_vault_round_trip_indexes_profile(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", "CP Vault")
    vault.mark_accepted()
    target = vault.write_controller_profile(complete_profile())
    assert target.is_file()

    loaded = load_controller_profile(target.read_text(encoding="utf-8"))
    assert loaded.part_number == "DK124"

    with KnowledgeIndex.open(vault.index_path) as index:
        hits = index.search("dk124", kinds=("component",))
        assert hits and "DK124" in hits[0].title
