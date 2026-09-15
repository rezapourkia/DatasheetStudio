"""Offline tests for download + preview-before-save into the v2 vault."""

from pathlib import Path

import pymupdf
import pytest

from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.infrastructure.web.http_client import HttpClient, InvalidPdfError
from datasheet_studio.services.online_import import OnlineImportError, OnlineImportService

from tests.unit.test_http_client import FakeResponse, FakeTransport


def make_source_pdf(tmp_path: Path, text: str = "DK124 online datasheet") -> Path:
    path = tmp_path / "online.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


def make_service(tmp_path: Path, vault_root: Path | None, chunks=None) -> OnlineImportService:
    source = make_source_pdf(tmp_path)
    body = source.read_bytes()
    transport = FakeTransport(
        [FakeResponse([body[:8], body[8:]], url="https://example.com/dk124.pdf")]
    )
    return OnlineImportService(
        vault_path_getter=lambda: str(vault_root) if vault_root else "",
        http=HttpClient(transport),
    )


@pytest.fixture()
def accepted_vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    vault = KnowledgeVault.create(root, "Online Vault")
    vault.mark_accepted()
    return root


def test_download_pdf_validates_and_hashes(tmp_path, accepted_vault):
    service = make_service(tmp_path, accepted_vault)
    downloaded = service.download_pdf("https://example.com/dk124.pdf")

    assert downloaded.path.is_file()
    assert downloaded.path.read_bytes().startswith(b"%PDF-")
    assert downloaded.sha256 and downloaded.size_bytes > 0


def test_download_pdf_rejects_non_pdf(tmp_path, accepted_vault):
    service = OnlineImportService(
        vault_path_getter=lambda: str(accepted_vault),
        http=HttpClient(FakeTransport([FakeResponse([b"<html>no</html>"])])),
    )
    with pytest.raises(OnlineImportError, match="PDF"):
        service.download_pdf("https://example.com/bad.pdf")


def test_save_to_vault_makes_result_searchable_and_openable(tmp_path, accepted_vault):
    service = make_service(tmp_path, accepted_vault)
    downloaded = service.download_pdf("https://example.com/dk124.pdf")

    outcome = service.save_to_vault(
        downloaded, manufacturer="Linkage", part_number="DK124", title="DK124 Datasheet"
    )

    assert not outcome.duplicate
    vault = KnowledgeVault(accepted_vault)
    assert vault.object_path(outcome.sha256).is_file()
    assert (vault.root / outcome.record_path).is_file()
    with KnowledgeIndex.open(vault.index_path) as index:
        hits = index.search("dk124", kinds=("document",))
        assert hits and "DK124" in hits[0].title


def test_saving_duplicate_content_reports_one_object(tmp_path, accepted_vault):
    service = make_service(tmp_path, accepted_vault)
    downloaded = service.download_pdf("https://example.com/dk124.pdf")

    first = service.save_to_vault(
        downloaded, manufacturer="Linkage", part_number="DK124"
    )
    second = service.save_to_vault(
        downloaded, manufacturer="Other", part_number="DK124-ALT"
    )

    assert not first.duplicate and second.duplicate
    objects = list((accepted_vault / "objects" / "sha256").rglob("*.pdf"))
    assert len(objects) == 1
    records = list((accepted_vault / "records").rglob("record.json"))
    assert len(records) == 2


def test_save_requires_accepted_vault(tmp_path):
    unaccepted = tmp_path / "vault"
    KnowledgeVault.create(unaccepted, "Not Accepted")
    service = make_service(tmp_path, unaccepted)
    downloaded = service.download_pdf("https://example.com/dk124.pdf")

    with pytest.raises(OnlineImportError, match="تأیید"):
        service.save_to_vault(downloaded, manufacturer="x", part_number="y")


def test_save_without_vault_gives_clear_guidance(tmp_path):
    service = make_service(tmp_path, None)
    downloaded = service.download_pdf("https://example.com/dk124.pdf")

    with pytest.raises(OnlineImportError, match="Upgrade Library to v2"):
        service.save_to_vault(downloaded, manufacturer="x", part_number="y")
