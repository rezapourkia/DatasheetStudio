"""Tests for page-by-page text extraction coverage (Phase 7)."""

from pathlib import Path

import pymupdf
import pytest

from datasheet_studio.infrastructure.ocr import NoOcrAdapter
from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.services.text_extraction import (
    ExtractionCancelled,
    ExtractionError,
    TextExtractionService,
)
from datasheet_studio.services.knowledge_hash import sha256_file

LONG_TEXT = (
    "DK124 offline switching controller electrical characteristics "
    "current limit typical value 1.1A fixed frequency 65kHz "
)


def _insert_long_text(page) -> None:
    """Insert wrapped lines so nothing is clipped at the page edge."""

    words = LONG_TEXT.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if sum(len(w) + 1 for w in current) >= 48:
            lines.append(" ".join(current))
            current = []
    if current:
        lines.append(" ".join(current))
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + 14 * index), line)


def make_pdf(
    tmp_path: Path,
    name: str = "mixed.pdf",
    *,
    searchable: int = 1,
    scanned: int = 1,
) -> Path:
    path = tmp_path / name
    doc = pymupdf.open()
    for _ in range(searchable):
        _insert_long_text(doc.new_page())
    for _ in range(scanned):
        doc.new_page()  # empty page -> text-poor/scanned
    doc.save(str(path))
    doc.close()
    return path


class FakeOcr:
    name = "fake"

    def is_available(self) -> bool:
        return True

    def ocr_page(self, pdf_path: str, page: int) -> str:
        return f"OCR recognized text for page {page}: " + LONG_TEXT


class FailingReader:
    """Reader stub that fails on a specific page."""

    def __init__(self, fail_on: int, real: object) -> None:
        self._fail_on = fail_on
        self._real = real

    class _Info:
        page_count = 3

    def open(self, path):
        return self._Info()

    def get_page_text(self, path, page):
        if page == self._fail_on:
            raise RuntimeError("page exploded")
        return LONG_TEXT


# --- ledger ----------------------------------------------------------------


def test_mixed_document_produces_correct_ledger_and_is_not_complete(tmp_path):
    pdf = make_pdf(tmp_path, searchable=2, scanned=1)
    service = TextExtractionService()
    coverage = service.extract(pdf)
    statuses = [p.status for p in coverage.pages]
    assert statuses == ["extracted", "extracted", "scanned"]
    assert coverage.is_complete is False
    assert coverage.count("scanned") == 1
    assert all(p.char_count > 0 for p in coverage.pages if p.status == "extracted")


def test_all_searchable_document_is_complete(tmp_path):
    pdf = make_pdf(tmp_path, "all.pdf", searchable=3, scanned=0)
    coverage = TextExtractionService().extract(pdf)
    assert coverage.is_complete is True


def test_failed_page_is_recorded_not_fatal(tmp_path):
    pdf = make_pdf(tmp_path, "fail.pdf", searchable=3, scanned=0)
    service = TextExtractionService(pdf_reader=FailingReader(2, None))
    coverage = service.extract(pdf)
    statuses = {p.page: p.status for p in coverage.pages}
    assert statuses == {1: "extracted", 2: "failed", 3: "extracted"}
    assert coverage.is_complete is False
    assert "exploded" in coverage.pages[1].reason


def test_missing_file_raises(tmp_path):
    with pytest.raises(ExtractionError):
        TextExtractionService().extract(tmp_path / "nope.pdf")


# --- cache ------------------------------------------------------------------


def test_vault_cache_reuses_previous_run(tmp_path):
    vault_root = tmp_path / "vault"
    KnowledgeVault.create(vault_root, "Cache Vault")
    pdf = make_pdf(tmp_path, "cached.pdf", searchable=2, scanned=0)
    digest = sha256_file(pdf)

    calls = {"n": 0}
    real_get = pymupdf.Document  # marker only; counting via wrapper below

    class CountingReader:
        def __init__(self) -> None:
            from datasheet_studio.infrastructure.pdf.reader import PdfReader

            self._real = PdfReader()

        def open(self, path):
            return self._real.open(path)

        def get_page_text(self, path, page):
            calls["n"] += 1
            return self._real.get_page_text(path, page)

    service = TextExtractionService(
        pdf_reader=CountingReader(), vault_path_getter=lambda: str(vault_root)
    )
    first = service.extract(pdf, source_hash=digest)
    assert first.is_complete
    assert calls["n"] == 2
    cache_files = list((vault_root / "extracted" / digest).glob("*"))
    assert {p.name for p in cache_files} == {"coverage.json", "full-text.md"}

    second = service.extract(pdf, source_hash=digest)
    assert second == first
    assert calls["n"] == 2  # no re-extraction: cache reused


def test_cached_full_text_has_page_markers(tmp_path):
    vault_root = tmp_path / "vault"
    KnowledgeVault.create(vault_root, "Markers Vault")
    pdf = make_pdf(tmp_path, "markers.pdf", searchable=2, scanned=0)
    digest = sha256_file(pdf)
    TextExtractionService(vault_path_getter=lambda: str(vault_root)).extract(
        pdf, source_hash=digest
    )
    text = (vault_root / "extracted" / digest / "full-text.md").read_text(
        encoding="utf-8"
    )
    assert "<!-- page:1 -->" in text and "<!-- page:2 -->" in text


def test_cancellation_keeps_previous_cache(tmp_path):
    vault_root = tmp_path / "vault"
    KnowledgeVault.create(vault_root, "Cancel Vault")
    pdf = make_pdf(tmp_path, "cancel.pdf", searchable=2, scanned=0)
    digest = sha256_file(pdf)
    service = TextExtractionService(vault_path_getter=lambda: str(vault_root))
    first = service.extract(pdf, source_hash=digest)

    # corrupt the cache page_count to force re-extraction, then cancel
    coverage_file = vault_root / "extracted" / digest / "coverage.json"
    coverage_file.write_text(
        coverage_file.read_text(encoding="utf-8").replace(
            '"page_count": 2', '"page_count": 99'
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExtractionCancelled):
        service.extract(pdf, source_hash=digest, should_cancel=lambda: True)

    # cache restore check: the cancelled run must not have overwritten ledger
    # (page_count 99 stays until a successful run replaces it)
    assert '"page_count": 99' in coverage_file.read_text(encoding="utf-8")
    # and a clean re-run restores a complete ledger
    again = service.extract(pdf, source_hash=digest)
    assert again.is_complete and again.page_count == 2


# --- OCR ---------------------------------------------------------------------


def test_fake_ocr_completes_scanned_document(tmp_path):
    pdf = make_pdf(tmp_path, "scan.pdf", searchable=0, scanned=2)
    service = TextExtractionService(ocr_adapter=FakeOcr())
    coverage = service.extract(pdf, use_ocr=True)
    assert [p.status for p in coverage.pages] == ["ocr", "ocr"]
    assert coverage.is_complete is True


def test_ocr_requested_but_unavailable_keeps_scanned(tmp_path):
    pdf = make_pdf(tmp_path, "scan2.pdf", searchable=0, scanned=1)
    service = TextExtractionService(ocr_adapter=NoOcrAdapter())
    coverage = service.extract(pdf, use_ocr=True)
    assert coverage.pages[0].status == "scanned"
    assert coverage.is_complete is False


def test_ocr_not_requested_leaves_scanned(tmp_path):
    pdf = make_pdf(tmp_path, "scan3.pdf", searchable=0, scanned=1)
    service = TextExtractionService(ocr_adapter=FakeOcr())
    coverage = service.extract(pdf, use_ocr=False)
    assert coverage.pages[0].status == "scanned"


# --- index integration ---------------------------------------------------------


def test_extracted_pages_become_searchable_in_index(tmp_path):
    vault_root = tmp_path / "vault"
    KnowledgeVault.create(vault_root, "Index Vault")
    pdf = make_pdf(tmp_path, "idx.pdf", searchable=1, scanned=0)
    digest = sha256_file(pdf)
    service = TextExtractionService(vault_path_getter=lambda: str(vault_root))
    service.extract(pdf, source_hash=digest)

    with KnowledgeIndex.open(vault_root / "library.sqlite") as index:
        hits = index.search("65kHz", kinds=("page",))
        assert hits
        assert hits[0].ref["page"] == 1
        assert hits[0].ref["source_hash"] == digest
