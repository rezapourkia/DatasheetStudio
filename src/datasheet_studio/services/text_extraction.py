"""Page-by-page text extraction with a coverage ledger (Phase 7).

Implements ``docs/modules/TEXT_EXTRACTION_COVERAGE.md``: classify every page
(``extracted``/``scanned``/``failed``), keep auditable artifacts cached by
content hash under the vault's ``extracted/<source-hash>/`` folder, feed the
rebuildable index, and never let a document be called complete while a page
is unaccounted for.  Cancellation aborts before any cache write.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Callable

from datasheet_studio.infrastructure.ocr import NoOcrAdapter
from datasheet_studio.infrastructure.pdf.reader import PdfReader
from datasheet_studio.infrastructure.storage.knowledge_index import KnowledgeIndex
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.services.knowledge_hash import sha256_file

EXTRACTOR_VERSION = 1
MIN_SEARCHABLE_CHARS = 32

PAGE_PENDING = "pending"
PAGE_EXTRACTED = "extracted"
PAGE_SCANNED = "scanned"
PAGE_OCR = "ocr"
PAGE_FAILED = "failed"
COMPLETE_STATUSES = (PAGE_EXTRACTED, PAGE_OCR)


class ExtractionCancelled(RuntimeError):
    """The run was cancelled; the previous cache is untouched."""


class ExtractionError(RuntimeError):
    """The source PDF cannot be processed at all."""


@dataclass(frozen=True)
class PageCoverage:
    page: int
    status: str
    char_count: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DocumentCoverage:
    source_hash: str
    page_count: int
    pages: tuple[PageCoverage, ...]

    @property
    def is_complete(self) -> bool:
        return bool(self.pages) and all(
            page.status in COMPLETE_STATUSES for page in self.pages
        )

    def count(self, status: str) -> int:
        return sum(1 for page in self.pages if page.status == status)

    def to_dict(self) -> dict:
        return {
            "extractor_version": EXTRACTOR_VERSION,
            "source_hash": self.source_hash,
            "page_count": self.page_count,
            "pages": [page.to_dict() for page in self.pages],
        }


ProgressCallback = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


def _significant_chars(text: str) -> int:
    return len("".join(text.split()))


class TextExtractionService:
    """Extract, classify, cache, and index the text of one source PDF."""

    def __init__(
        self,
        pdf_reader: PdfReader | None = None,
        ocr_adapter=None,
        vault_path_getter: Callable[[], str] | None = None,
    ) -> None:
        self._reader = pdf_reader or PdfReader()
        self._ocr = ocr_adapter or NoOcrAdapter()
        self._vault_path_getter = vault_path_getter or (lambda: "")

    # -- cache ---------------------------------------------------------------

    def _vault(self) -> KnowledgeVault | None:
        raw = (self._vault_path_getter() or "").strip()
        return KnowledgeVault(raw) if raw else None

    def cached_coverage(self, source_hash: str) -> DocumentCoverage | None:
        vault = self._vault()
        if vault is None:
            return None
        coverage_file = vault.root / "extracted" / source_hash / "coverage.json"
        if not coverage_file.is_file():
            return None
        try:
            data = json.loads(coverage_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if data.get("extractor_version") != EXTRACTOR_VERSION:
            return None
        pages = tuple(
            PageCoverage(
                page=int(p["page"]),
                status=str(p["status"]),
                char_count=int(p.get("char_count", 0)),
                reason=str(p.get("reason", "")),
            )
            for p in data.get("pages", [])
        )
        return DocumentCoverage(
            source_hash=source_hash,
            page_count=int(data.get("page_count", len(pages))),
            pages=pages,
        )

    def _write_cache(
        self, source_hash: str, coverage: DocumentCoverage, page_texts: dict[int, str]
    ) -> None:
        vault = self._vault()
        if vault is None:
            return
        folder = vault.root / "extracted" / source_hash
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "coverage.json").write_text(
            json.dumps(coverage.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        parts = [f"# متن استخراج‌شده — {source_hash[:12]}…", ""]
        for page in sorted(page_texts):
            parts.append(f"<!-- page:{page} -->")
            parts.append(page_texts[page].strip() or "—")
            parts.append("")
        (folder / "full-text.md").write_text("\n".join(parts), encoding="utf-8")

    def _cached_page_texts(self, source_hash: str) -> dict[int, str]:
        vault = self._vault()
        if vault is None:
            return {}
        text_file = vault.root / "extracted" / source_hash / "full-text.md"
        if not text_file.is_file():
            return {}
        texts: dict[int, str] = {}
        current: int | None = None
        chunks: list[str] = []
        for line in text_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("<!-- page:") and line.endswith(" -->"):
                if current is not None:
                    texts[current] = "\n".join(chunks).strip()
                current = int(line[len("<!-- page:") : -len(" -->")])
                chunks = []
            else:
                chunks.append(line)
        if current is not None:
            texts[current] = "\n".join(chunks).strip()
        return texts

    # -- extraction ------------------------------------------------------------

    def extract(
        self,
        pdf_path: str | Path,
        *,
        source_hash: str | None = None,
        use_ocr: bool = False,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> DocumentCoverage:
        """Run (or resume) extraction; returns the coverage ledger."""

        path = Path(pdf_path)
        if not path.is_file():
            raise ExtractionError(f"فایل PDF پیدا نشد: {path}")
        digest = source_hash or sha256_file(path)
        try:
            info = self._reader.open(path)
        except Exception as exc:  # noqa: BLE001 - whole-document failure
            raise ExtractionError(f"باز کردن PDF ممکن نشد: {exc}") from exc
        page_count = info.page_count

        cached = self.cached_coverage(digest)
        page_texts: dict[int, str] = {}
        pages: list[PageCoverage] = []
        if cached is not None and cached.page_count == page_count:
            page_texts = self._cached_page_texts(digest)
            pages = list(cached.pages)

        statuses: list[PageCoverage] = []
        for number in range(1, page_count + 1):
            if should_cancel and should_cancel():
                raise ExtractionCancelled("استخراج متن لغو شد.")
            if progress:
                progress(number, page_count, f"صفحه {number} از {page_count}")
            previous = next((p for p in pages if p.page == number), None)
            if previous is not None and previous.status in COMPLETE_STATUSES:
                statuses.append(previous)
                if number not in page_texts:
                    page_texts[number] = ""
                continue
            try:
                text = self._reader.get_page_text(path, number)
            except Exception as exc:  # noqa: BLE001 - per-page failure
                statuses.append(
                    PageCoverage(number, PAGE_FAILED, 0, str(exc))
                )
                continue
            status = PAGE_EXTRACTED if _significant_chars(text) >= MIN_SEARCHABLE_CHARS else PAGE_SCANNED
            if status == PAGE_SCANNED and use_ocr and self._ocr.is_available():
                try:
                    ocr_text = self._ocr.ocr_page(str(path), number)
                    if _significant_chars(ocr_text) >= MIN_SEARCHABLE_CHARS:
                        text = ocr_text
                        status = PAGE_OCR
                except Exception as exc:  # noqa: BLE001 - OCR failure is not fatal
                    statuses.append(
                        PageCoverage(number, PAGE_SCANNED, _significant_chars(text), f"OCR ناموفق: {exc}")
                    )
                    continue
            statuses.append(PageCoverage(number, status, _significant_chars(text)))
            page_texts[number] = text

        coverage = DocumentCoverage(
            source_hash=digest, page_count=page_count, pages=tuple(statuses)
        )
        self._write_cache(digest, coverage, page_texts)
        self._update_index(digest, coverage, page_texts)
        return coverage

    def _update_index(
        self, digest: str, coverage: DocumentCoverage, page_texts: dict[int, str]
    ) -> None:
        vault = self._vault()
        if vault is None:
            return
        # The index is rebuildable state: opening creates it when missing.
        index = KnowledgeIndex.open(vault.index_path)
        try:
            for page in coverage.pages:
                if page.status in COMPLETE_STATUSES and page_texts.get(page.page, "").strip():
                    index.add_page_text(digest, page.page, page_texts[page.page])
        finally:
            index.close()
