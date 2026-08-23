"""Application service for the local datasheet library.

Coordinates the storage layer (``LibraryStore``), manufacturer detection
(``ManufacturerDetector``) and the PDF reader so the UI can perform
library use-cases with a single dependency.
"""

import logging
from pathlib import Path

from datasheet_studio.infrastructure.pdf.reader import PdfOpenError, PdfReader
from datasheet_studio.infrastructure.storage.library_store import (
    LibraryStore,
)
from datasheet_studio.models.library_item import LibraryItem, LibraryItemKind
from datasheet_studio.services.manufacturer_detector import (
    ManufacturerDetector,
    extract_part_number_from_text,
)

LOG = logging.getLogger("datasheet_studio.services.library")


class LibraryService:
    """Use-cases over one opened library folder."""

    def __init__(
        self,
        reader: PdfReader | None = None,
        detector: ManufacturerDetector | None = None,
    ) -> None:
        self._reader = reader or PdfReader()
        self._detector = detector or ManufacturerDetector()
        self._store: LibraryStore | None = None

    # ------------------------------------------------------------------
    # Library lifecycle
    # ------------------------------------------------------------------

    @property
    def store(self) -> LibraryStore | None:
        return self._store

    @property
    def is_open(self) -> bool:
        return self._store is not None

    def create_library(self, root: str | Path, name: str | None = None) -> LibraryStore:
        self._store = LibraryStore.create(root, name=name)
        LOG.info("Created library: %s", self._store.root)
        return self._store

    def open_library(self, root: str | Path) -> LibraryStore:
        """Open an existing library folder; raises if it is not a library."""
        self._store = LibraryStore(root)
        self._store.reindex()
        LOG.info("Opened library: %s (%d items)", self._store.root, self._store.item_count)
        return self._store

    def close(self) -> None:
        self._store = None

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def detect_metadata(self, source_path: str | Path) -> dict:
        """Best-effort metadata for a PDF: manufacturer, part number, pages."""
        source = Path(source_path)
        result = {
            "manufacturer": "",
            "part_number": "",
            "page_count": 0,
            "title": "",
        }
        try:
            info = self._reader.open(source)
        except PdfOpenError as exc:
            LOG.warning("Library: could not read %s: %s", source, exc)
            result["manufacturer"] = self._detector.from_filename(source.name)
            return result

        result["page_count"] = info.page_count
        result["title"] = info.title or source.stem

        first_page_text = ""
        try:
            first_page_text = self._reader.get_page_text(source, 1)
        except Exception as exc:  # noqa: BLE001 - best-effort detection
            LOG.debug("Library: page-1 text unavailable: %s", exc)

        result["manufacturer"] = self._detector.detect(
            filename=source.name,
            author=info.author,
            first_page_text=first_page_text,
        )
        result["part_number"] = extract_part_number_from_text(
            f"{source.stem}\n{first_page_text}"
        )
        return result

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def require_store(self) -> LibraryStore:
        if self._store is None:
            raise RuntimeError("No library is open")
        return self._store

    def add_pdf(
        self,
        source_path: str | Path,
        *,
        manufacturer_folder: str,
        kind: LibraryItemKind = LibraryItemKind.DATASHEET,
        tags: list[str] | None = None,
        auto_detect: bool = True,
    ) -> LibraryItem:
        """Copy a PDF into the library (auto-detecting metadata by default)."""
        store = self.require_store()
        meta = self.detect_metadata(source_path) if auto_detect else {}
        manufacturer = (
            str(meta.get("manufacturer") or "")
            or manufacturer_folder
            or "Unsorted"
        )
        return store.add_item_from_source(
            source_path,
            kind=kind,
            manufacturer_folder=manufacturer_folder or manufacturer,
            manufacturer=manufacturer,
            title=str(meta.get("title") or ""),
            part_number=str(meta.get("part_number") or ""),
            page_count=int(meta.get("page_count") or 0),
            tags=tags,
        )

    def remove_item(self, item_id: str, *, delete_file: bool = True) -> None:
        self.require_store().remove_item(item_id, delete_file=delete_file)

    def move_item(self, item_id: str, new_folder: str) -> LibraryItem:
        return self.require_store().move_item(item_id, new_folder)

    def save_summary(self, item_id: str, text: str) -> Path:
        return self.require_store().save_summary(item_id, text)

    def search(self, query: str, limit: int = 200) -> list[LibraryItem]:
        if self._store is None:
            return []
        return self._store.search(query, limit=limit)
