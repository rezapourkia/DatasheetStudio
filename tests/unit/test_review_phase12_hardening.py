"""Review P1/Phase 12: catalogue provenance, uniqueness, and ordering."""

from pathlib import Path

import pytest

from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.models.magnetics_catalog import (
    CatalogPack,
    CatalogValidationError,
    CoreRecord,
)

from tests.unit.test_magnetics_catalog import bobbin, core, material, pack


def test_provenance_is_required_on_every_record():
    with pytest.raises(CatalogValidationError, match="منبع"):
        core(source_hash="")
    with pytest.raises(CatalogValidationError, match="صفحه"):
        core(page=None)


def test_duplicate_ordering_codes_are_rejected_not_collapsed():
    duplicated = pack(cores=(core(), core()))
    with pytest.raises(CatalogValidationError, match="تکراری"):
        duplicated.validate()


def test_partial_loss_coefficients_are_rejected():
    with pytest.raises(CatalogValidationError, match="ضریب"):
        material(loss_k=100.0, loss_alpha=None, loss_beta=2.0)


def test_invalid_gap_options_are_rejected():
    with pytest.raises(CatalogValidationError, match="گپ"):
        core(gap_options_um=(0.0, -50.0))


def test_latest_pack_orders_by_import_time_not_lexicographic(tmp_path):
    vault = KnowledgeVault.create(tmp_path / "vault", "Ord Vault")
    vault.write_catalog_pack(pack(pack_version="9"))
    vault.write_catalog_pack(pack(pack_version="10"))
    # lexicographic "9" > "10"; import order must win instead
    assert vault.latest_catalog_pack("tdk-official").pack_version == "10"
