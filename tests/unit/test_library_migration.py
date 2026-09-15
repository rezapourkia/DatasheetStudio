"""Tests for the safe v1 -> v2 library migration service."""

from pathlib import Path

import pytest

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.infrastructure.storage.library_store import LibraryStore
from datasheet_studio.services.library_migration import (
    LibraryMigrator,
    MigrationCancelled,
    MigrationError,
)


def make_pdf(path: Path, text: str = "DK124") -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def v1_library(tmp_path: Path) -> Path:
    root = tmp_path / "v1"
    store = LibraryStore.create(root, name="My Library")
    source_dir = tmp_path / "sources"
    source_dir.mkdir()

    good1 = source_dir / "dk124.pdf"
    make_pdf(good1, "DK124 controller")
    store.add_item_from_source(
        good1,
        manufacturer_folder="Linkage",
        manufacturer="Linkage",
        title="DK124 Datasheet",
        part_number="DK124",
        tags=["flyback"],
        summary_text="خلاصهٔ DK124",
    )
    good2 = source_dir / "bq25798.pdf"
    make_pdf(good2, "BQ25798 charger")
    store.add_item_from_source(
        good2,
        manufacturer_folder="TI",
        manufacturer="TI",
        title="BQ25798 Datasheet",
        part_number="BQ25798",
    )
    return root


def manifest_bytes(root: Path) -> bytes:
    return (root / "library.json").read_bytes()


def all_files(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


# --- success ---------------------------------------------------------------


def test_successful_migration(v1_library: Path, tmp_path: Path):
    before = all_files(v1_library)
    target = tmp_path / "vault"

    report = LibraryMigrator().migrate(v1_library, target)

    # v1 untouched (byte-identical)
    assert all_files(v1_library) == before

    assert report.count("imported") == 2
    assert report.count("failed") == 0 and report.count("skipped") == 0

    vault = KnowledgeVault(target)
    identity, accepted = vault.read_identity()
    assert identity.name == "My Library" and accepted is False
    assert (vault.root / "migration" / "backup-library.json").read_bytes() == manifest_bytes(
        v1_library
    )
    assert (vault.root / "migration" / "report.json").is_file()

    # two distinct objects + records
    objects = list((vault.root / "objects" / "sha256").rglob("*.pdf"))
    assert len(objects) == 2
    records = list((vault.root / "records").rglob("record.json"))
    assert len(records) == 2

    # summary converted to markdown
    record_md = next(
        p for p in (vault.root / "records").rglob("record.md")
        if "DK124" in p.read_text(encoding="utf-8") and "خلاصهٔ DK124" in p.read_text(encoding="utf-8")
    )
    assert "objects/sha256" in record_md.read_text(encoding="utf-8")

    # index built and searchable by part number
    with KnowledgeIndex.open(vault.index_path) as index:
        hits = index.search("dk124", kinds=("document",))
        assert hits and "DK124" in hits[0].title


def test_ambiguous_items_are_reported_but_imported(v1_library: Path, tmp_path: Path):
    store = LibraryStore(v1_library)
    plain = tmp_path / "plain.pdf"
    make_pdf(plain, "no metadata")
    store.add_item_from_source(plain, manufacturer_folder="Unsorted", manufacturer="")
    target = tmp_path / "vault"

    report = LibraryMigrator().migrate(v1_library, target)

    assert report.count("ambiguous") == 1
    assert report.count("imported") == 3
    entry = next(e for e in report.entries if e.kind == "ambiguous")
    assert "شماره قطعه" in entry.reason


# --- duplicates --------------------------------------------------------------


def test_duplicate_content_creates_one_object_two_records(tmp_path: Path):
    root = tmp_path / "v1"
    store = LibraryStore.create(root, name="dup")
    source = tmp_path / "same.pdf"
    make_pdf(source, "identical")
    store.add_item_from_source(
        source, manufacturer_folder="M", manufacturer="M", part_number="AAA"
    )
    store.add_item_from_source(
        source, manufacturer_folder="M", manufacturer="M", part_number="BBB"
    )
    target = tmp_path / "vault"

    report = LibraryMigrator().migrate(root, target)

    assert report.count("imported") == 1
    assert report.count("duplicate") == 1
    objects = list((target / "objects" / "sha256").rglob("*.pdf"))
    assert len(objects) == 1
    records = list((target / "records").rglob("record.json"))
    assert len(records) == 2


# --- skipped: invalid pdf and missing file --------------------------------------


def test_invalid_pdf_and_missing_file_are_skipped(tmp_path: Path):
    root = tmp_path / "v1"
    store = LibraryStore.create(root, name="mixed")
    bad = tmp_path / "not-a-pdf.pdf"
    bad.write_text("this is just text", encoding="utf-8")
    store.add_item_from_source(
        bad, manufacturer_folder="X", manufacturer="X", part_number="BAD1"
    )
    good = tmp_path / "good.pdf"
    make_pdf(good)
    store.add_item_from_source(
        good, manufacturer_folder="X", manufacturer="X", part_number="GOOD1"
    )
    # break one item by deleting its stored file
    item = store.items[1]
    (root / item.relative_path).unlink()
    target = tmp_path / "vault"

    report = LibraryMigrator().migrate(root, target)

    skipped = [e for e in report.entries if e.kind == "skipped"]
    assert len(skipped) == 2
    reasons = " | ".join(e.reason for e in skipped)
    assert "PDF" in reasons and "یافت نشد" in reasons
    assert report.count("imported") == 0


# --- failure: permission error on copy ------------------------------------------


def test_permission_failure_is_reported_and_migration_continues(
    v1_library: Path, tmp_path: Path, monkeypatch
):
    import shutil as shutil_module

    import datasheet_studio.infrastructure.storage.knowledge_vault as vault_module

    real_copy = shutil_module.copy2

    def flaky_copy(src, dst, **kwargs):
        if str(src).endswith(".pdf") and "objects" in str(dst):
            raise PermissionError("denied")
        return real_copy(src, dst, **kwargs)

    monkeypatch.setattr(vault_module.shutil, "copy2", flaky_copy)
    target = tmp_path / "vault"

    report = LibraryMigrator().migrate(v1_library, target)

    assert report.count("failed") == 2  # both object copies denied
    assert report.count("imported") == 0
    assert all("denied" in e.reason for e in report.entries if e.kind == "failed")
    # the manifest backup (not an objects copy) still succeeded
    assert (target / "migration" / "backup-library.json").is_file()


# --- interruption ----------------------------------------------------------------


def test_cancellation_mid_run_removes_partial_vault(v1_library: Path, tmp_path: Path):
    before = all_files(v1_library)
    target = tmp_path / "vault"

    with pytest.raises(MigrationCancelled):
        LibraryMigrator().migrate(
            v1_library, target, should_cancel=lambda: True  # cancel immediately
        )

    assert not target.exists()
    assert all_files(v1_library) == before


def test_unexpected_error_removes_partial_vault(v1_library: Path, tmp_path: Path):
    target = tmp_path / "vault"

    def boom(*args, **kwargs):
        raise RuntimeError("disk exploded")

    import datasheet_studio.infrastructure.storage.knowledge_vault as vault_module

    original = vault_module.KnowledgeVault.rebuild_index
    vault_module.KnowledgeVault.rebuild_index = boom
    try:
        with pytest.raises(MigrationError):
            LibraryMigrator().migrate(v1_library, target)
    finally:
        vault_module.KnowledgeVault.rebuild_index = original

    assert not target.exists()


# --- rollback ---------------------------------------------------------------------


def test_rollback_after_success(v1_library: Path, tmp_path: Path):
    target = tmp_path / "vault"
    LibraryMigrator().migrate(v1_library, target)
    assert target.exists()

    LibraryMigrator().rollback(target)

    assert not target.exists()
    assert (v1_library / "library.json").is_file()


# --- preview ----------------------------------------------------------------------


def test_preview_counts(v1_library: Path):
    store = LibraryStore(v1_library)
    item = store.items[0]
    (v1_library / item.relative_path).unlink()

    preview = LibraryMigrator().preview(v1_library)

    assert preview.item_count == 2
    assert preview.files_found == 1
    assert preview.files_missing == 1
    assert preview.total_bytes > 0
