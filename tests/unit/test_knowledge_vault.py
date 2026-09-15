"""Tests for the v2 knowledge-vault layout writer."""

from pathlib import Path

import pytest

from datasheet_studio.infrastructure.storage.knowledge_vault import (
    KnowledgeVault,
    VaultError,
)
from datasheet_studio.models.knowledge_base import DocumentRevision, load_record


def make_pdf(path: Path, text: str = "DK124 test page") -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def make_revision(sha: str, record_path: str) -> DocumentRevision:
    return DocumentRevision(
        manufacturer="Linkage",
        part_number="DK124",
        document_type="datasheet",
        revision="migrated-1",
        object_sha256=sha,
        record_path=record_path,
        title="DK124",
    )


def test_create_writes_layout_and_identity(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", name="کتابخانه من")
    assert (vault.root / "library.toml").is_file()
    assert (vault.root / "objects" / "sha256").is_dir()
    assert (vault.root / "records").is_dir()
    identity, accepted = vault.read_identity()
    assert identity.name == "کتابخانه من"
    assert identity.schema_version == 2
    assert accepted is False


def test_create_refuses_nonempty_folder(tmp_path: Path):
    target = tmp_path / "vault"
    target.mkdir()
    (target / "something.txt").write_text("x", encoding="utf-8")
    with pytest.raises(VaultError):
        KnowledgeVault.create(target, name="x")


def test_import_source_dedups_by_hash(tmp_path: Path):
    import shutil

    vault = KnowledgeVault.create(tmp_path / "vault", name="v")
    first = tmp_path / "a.pdf"
    make_pdf(first, "same content")
    second = tmp_path / "b.pdf"
    shutil.copy2(first, second)  # byte-identical content

    sha1, size1, copied1 = vault.import_source(first)
    sha2, size2, copied2 = vault.import_source(second)

    assert sha1 == sha2
    assert size1 == size2
    assert copied1 is True and copied2 is False
    assert vault.object_path(sha1).is_file()
    objects = list((vault.root / "objects" / "sha256").rglob("*.pdf"))
    assert len(objects) == 1


def test_write_document_record_envelope_round_trip(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", name="v")
    record_dir = vault.unique_record_dir("Linkage", "DK124", "migrated-1")
    relative = record_dir.relative_to(vault.root).as_posix() + "/record.md"
    revision = make_revision("a" * 64, relative)
    markdown = "# DK124\n\nخلاصهٔ نمونه"
    vault.write_document_record(record_dir, revision, markdown)

    assert (record_dir / "record.md").read_text(encoding="utf-8") == markdown
    loaded = load_record((record_dir / "record.json").read_text(encoding="utf-8"))
    assert loaded == revision


def test_unique_record_dir_appends_suffix_on_collision(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", name="v")
    first = vault.unique_record_dir("M", "P", "r")
    second = vault.unique_record_dir("M", "P", "r")
    assert first.name == "r"
    assert second.name == "r-2"


def test_mark_accepted_flips_flag(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", name="v")
    vault.mark_accepted()
    _, accepted = vault.read_identity()
    assert accepted is True
    vault.mark_accepted()  # idempotent
    assert vault.read_identity()[1] is True


def test_rollback_removes_vault(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", name="v")
    make_pdf(tmp_path / "x.pdf")
    vault.import_source(tmp_path / "x.pdf")
    assert vault.exists()
    vault.rollback()
    assert not vault.exists()
    vault.rollback()  # idempotent


def test_backup_manifest_and_report(tmp_path: Path):
    vault = KnowledgeVault.create(tmp_path / "vault", name="v")
    manifest = tmp_path / "library.json"
    manifest.write_text('{"schema_version": 1}', encoding="utf-8")
    vault.backup_manifest(manifest)
    assert (vault.root / "migration" / "backup-library.json").read_text(
        encoding="utf-8"
    ) == '{"schema_version": 1}'
    vault.write_migration_report('{"entries": []}', "# گزارش")
    assert (vault.root / "migration" / "report.md").read_text(encoding="utf-8").startswith(
        "# گزارش"
    )
