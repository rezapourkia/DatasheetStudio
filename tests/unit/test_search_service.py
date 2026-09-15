"""Tests for the provider-neutral Phase-5 search service."""

from pathlib import Path

import pymupdf

from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.models.knowledge_base import DocumentRevision
from datasheet_studio.services.search_service import (
    LocalKnowledgeProvider,
    MockOnlineProvider,
    SearchResult,
    SearchService,
)


def _accepted_vault(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "DK124.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "DK124 current limit 1.1 A")
    document.save(str(source))
    document.close()

    root = tmp_path / "vault"
    vault = KnowledgeVault.create(root, "Test Vault")
    digest, _size, _copied = vault.import_source(source)
    revision = DocumentRevision(
        manufacturer="Linkage",
        part_number="DK124",
        document_type="datasheet",
        revision="v1.6",
        object_sha256=digest,
        record_path="records/datasheets/Linkage/DK124/v1.6/record.md",
        title="DK124 Datasheet",
        summary="Offline flyback controller",
    )
    vault.rebuild_index(
        [revision],
        [(digest, 1, "DK124 electrical characteristics current limit 1.1 A")],
    )
    vault.mark_accepted()
    return root, vault.object_path(digest)


def test_mock_provider_is_deterministic_and_never_previewable():
    provider = MockOnlineProvider()
    first = provider.search("  DK124  controller ")
    second = provider.search("DK124 controller")

    assert first == second
    assert len(first) == 2
    assert all(not row.can_preview and not row.can_save for row in first)
    assert all(row.url and row.url.startswith("https://example.invalid/") for row in first)


def test_local_provider_resolves_pdf_and_matched_page(tmp_path):
    root, object_path = _accepted_vault(tmp_path)
    provider = LocalKnowledgeProvider(root)

    document_hits = provider.search("DK124")
    page_hits = provider.search("electrical characteristics")

    assert any(row.pdf_path == str(object_path.resolve()) for row in document_hits)
    page = next(row for row in page_hits if row.kind == "page")
    assert page.pdf_path == str(object_path.resolve())
    assert page.page == 1
    assert page.can_preview is True


def test_missing_vault_is_a_notice_not_a_crash(tmp_path):
    service = SearchService((LocalKnowledgeProvider(tmp_path / "missing"),))
    response = service.search("DK124")

    assert response.results == ()
    assert response.errors == ()
    assert response.notices and response.notices[0][0] == "local-kb"


def test_one_provider_error_does_not_hide_other_results():
    class BrokenProvider:
        provider_id = "broken"

        def search(self, query: str, *, limit: int = 30):
            raise RuntimeError("provider failed")

    class GoodProvider:
        provider_id = "good"

        def search(self, query: str, *, limit: int = 30):
            return [SearchResult("good", "datasheet", query)]

    response = SearchService((BrokenProvider(), GoodProvider())).search("DK124")

    assert [row.title for row in response.results] == ["DK124"]
    assert response.errors == (("broken", "provider failed"),)
