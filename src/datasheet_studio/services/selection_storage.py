"""Service for saving and loading selected pages with compression."""

import json
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from datasheet_studio.models.selected_page import SelectedPage


class SelectionStorageError(Exception):
    """Raised when selection save/load fails."""


class SelectionStorage:
    """Save and load selected pages to/from compressed ZIP files."""

    @staticmethod
    def save(
        path: str | Path,
        document_path: str,
        selected_pages: dict[int, SelectedPage],
    ) -> None:
        """Save selected pages to a compressed ZIP file.

        The ZIP contains a JSON file with:
        - document_path: original PDF path
        - saved_at: timestamp
        - pages: list of {page_number, note, selected_at}
        """
        file_path = Path(path)

        data = {
            "document_path": document_path,
            "saved_at": datetime.now().isoformat(),
            "pages": [
                {
                    "page_number": sp.page_number,
                    "note": sp.note,
                    "selected_at": sp.selected_at.isoformat(),
                }
                for sp in sorted(selected_pages.values(), key=lambda s: s.page_number)
            ],
        }

        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

        try:
            with zipfile.ZipFile(
                file_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
            ) as zf:
                zf.writestr("selection.json", json_bytes)
        except Exception as exc:
            raise SelectionStorageError(f"Failed to save selection: {exc}") from exc

    @staticmethod
    def load(path: str | Path) -> tuple[str, list[SelectedPage]]:
        """Load selected pages from a compressed ZIP file.

        Returns (document_path, list_of_selected_pages).
        """
        file_path = Path(path)

        if not file_path.is_file():
            raise SelectionStorageError(f"File not found: {file_path}")

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                if "selection.json" not in zf.namelist():
                    raise SelectionStorageError(
                        f"Invalid selection file: {file_path}"
                    )
                json_bytes = zf.read("selection.json")
        except zipfile.BadZipFile as exc:
            raise SelectionStorageError(
                f"Not a valid selection file: {file_path}"
            ) from exc

        try:
            data = json.loads(json_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SelectionStorageError(
                f"Corrupted selection data: {file_path}"
            ) from exc

        document_path = data.get("document_path", "")
        pages_data = data.get("pages", [])

        selected_pages: list[SelectedPage] = []
        for item in pages_data:
            try:
                page_number = int(item["page_number"])
            except (KeyError, TypeError, ValueError):
                continue

            note = str(item.get("note", ""))

            selected_at_str = item.get("selected_at")
            if selected_at_str:
                try:
                    selected_at = datetime.fromisoformat(selected_at_str)
                except (ValueError, TypeError):
                    selected_at = datetime.now()
            else:
                selected_at = datetime.now()

            selected_pages.append(
                SelectedPage(
                    page_number=page_number,
                    document_path=document_path,
                    note=note,
                    selected_at=selected_at,
                )
            )

        return document_path, selected_pages
