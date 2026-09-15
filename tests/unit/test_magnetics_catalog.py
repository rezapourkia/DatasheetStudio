"""Tests for the real magnetics catalogue (Phase 12)."""

import pytest

from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.models.magnetics_catalog import (
    BobbinRecord,
    CatalogValidationError,
    CatalogPack,
    CoreRecord,
    MaterialRecord,
    dump_pack,
    load_pack,
    pack_diff,
)


def core(**over):
    data = dict(
        manufacturer="TDK", family="EE19/17", ordering_code="B66208-G-X187",
        ae_mm2=32.0, aw_mm2=42.0, le_mm=39.4, mlt_mm=41.0, ve_mm3=1260.0,
        b_max_t=0.39, material_code="N87", bobbin_codes=("B66208-W-X187",),
        source_hash="f" * 64, page=4,
    )
    data.update(over)
    return CoreRecord(**data)


def material(**over):
    data = dict(
        manufacturer="TDK", code="N87", permeability=2200.0,
        freq_min_khz=25.0, freq_max_khz=500.0, temp_min_c=25.0, temp_max_c=100.0,
        source_hash="f" * 64, page=7,
    )
    data.update(over)
    return MaterialRecord(**data)


def bobbin(**over):
    data = dict(
        manufacturer="TDK", code="B66208-W-X187",
        winding_width_mm=9.0, winding_height_mm=5.0, winding_area_mm2=45.0,
        creepage_mm=3.0, compatible_core_codes=("B66208-G-X187",),
        source_hash="f" * 64, page=9,
    )
    data.update(over)
    return BobbinRecord(**data)


def pack(**over):
    data = dict(
        provider="tdk-official", pack_version="2026.09",
        cores=(core(),), materials=(material(),), bobbins=(bobbin(),),
    )
    data.update(over)
    return CatalogPack(**data)


def test_valid_pack_round_trips():
    original = pack()
    loaded = load_pack(dump_pack(original))
    assert loaded == original


def test_missing_positive_geometry_is_rejected():
    with pytest.raises(CatalogValidationError):
        core(ae_mm2=0)


def test_invalid_curve_domains_are_rejected():
    with pytest.raises(CatalogValidationError):
        material(freq_min_khz=500.0, freq_max_khz=100.0)
    with pytest.raises(CatalogValidationError):
        material(temp_min_c=100.0, temp_max_c=25.0)


def test_missing_material_reference_is_rejected():
    with pytest.raises(CatalogValidationError):
        pack().validate() if False else CatalogPack(
            provider="p", pack_version="1",
            cores=(core(material_code="PC95-missing"),),
            materials=(material(),), bobbins=(bobbin(),),
        ).validate()


def test_mixed_manufacturer_assumption_is_rejected():
    other_maker = bobbin(manufacturer="EPCOS")
    with pytest.raises(CatalogValidationError, match="سازنده"):
        pack(bobbins=(other_maker,)).validate()
    with pytest.raises(CatalogValidationError, match="سازنده"):
        pack(materials=(material(manufacturer="Ferrocube"),)).validate()


def test_bobbin_without_declared_compatibility_is_rejected():
    bad = bobbin(compatible_core_codes=("some-other-core",))
    with pytest.raises(CatalogValidationError, match="اعلام نکرده"):
        pack(bobbins=(bad,)).validate()


def test_verified_can_never_be_imported():
    with pytest.raises(CatalogValidationError, match="verified"):
        core(review_state="verified")


def test_pack_diff_previews_update():
    v1 = pack()
    v2 = pack(pack_version="2026.10", cores=(core(), core(ordering_code="NEW-1")))
    diff = pack_diff(v1, v2)
    assert diff["added"] == ["NEW-1"] and diff["removed"] == [] and diff["changed"] == []
    changed = pack(
        pack_version="2026.10", cores=(core(ae_mm2=33.0),)
    )
    assert pack_diff(v1, changed)["changed"] == [core().ordering_code]


def test_vault_pack_install_offline_reload_and_rollback(tmp_path):
    vault = KnowledgeVault.create(tmp_path / "vault", "Mag Vault")
    vault.write_catalog_pack(pack())
    vault.write_catalog_pack(pack(pack_version="2026.10"))

    packs = vault.catalog_packs()
    assert [p.pack_version for p in packs] == ["2026.09", "2026.10"]
    assert vault.latest_catalog_pack("tdk-official").pack_version == "2026.10"

    vault.rollback_catalog_pack("tdk-official", "2026.10")
    assert [p.pack_version for p in vault.catalog_packs()] == ["2026.09"]


def test_flyback_dialog_lists_catalog_core(qapp_instance, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
    from datasheet_studio.tools.flyback_designer.dialog import FlybackDesignerDialog

    vault = KnowledgeVault.create(tmp_path / "vault2", "Combo Vault")
    vault.write_catalog_pack(pack())
    settings = QSettings()
    settings.setValue("knowledgeBasePath", str(vault.root))
    try:
        dialog = FlybackDesignerDialog()
        names = [
            dialog._core_combo.itemText(i)
            for i in range(dialog._core_combo.count())
        ]
        assert any("B66208-G-X187" in name and "TDK" in name for name in names)
        # selecting the catalogue core fills the geometry spins
        index = next(
            i for i, n in enumerate(names) if "B66208-G-X187" in n
        )
        dialog._core_combo.setCurrentIndex(index)
        assert dialog._fields["ae_mm2"].value() == pytest.approx(32.0)
        dialog.close()
    finally:
        settings.remove("knowledgeBasePath")
