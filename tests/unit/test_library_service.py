"""Unit tests for the library application service."""

from pathlib import Path

from datasheet_studio.infrastructure.pdf.reader import PdfReader
from datasheet_studio.infrastructure.storage.library_store import LibraryStore
from datasheet_studio.models.library_item import LibraryItemKind
from datasheet_studio.services.library_service import LibraryService


def _fake_pdf(path: Path, author: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if author:
        # Enough content for PyMuPDF to parse as a real PDF.
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), f"Copyright {author} 2026")
        doc.set_metadata({"author": author})
        doc.save(path)
        doc.close()
    else:
        path.write_bytes(b"%PDF-1.4 fake")
    return path


def test_detect_metadata_from_real_pdf(tmp_path):
    src = _fake_pdf(tmp_path / "STM32G431zzzz-Datasheet.pdf", author="STMicroelectronics")
    service = LibraryService()

    meta = service.detect_metadata(src)

    assert meta["manufacturer"] == "STMicroelectronics"
    assert meta["page_count"] == 1
    assert "STM32G431" in meta["part_number"]


def test_detect_metadata_from_filename_only(tmp_path):
    src = tmp_path / "TPS54331-Datasheet.pdf"
    src.write_bytes(b"%PDF not real")
    service = LibraryService()

    meta = service.detect_metadata(src)

    assert meta["manufacturer"] == "Texas Instruments"


def test_add_pdf_uses_detected_manufacturer_folder(tmp_path):
    root = tmp_path / "Lib"
    service = LibraryService()
    service.create_library(root)
    src = _fake_pdf(tmp_path / "STM32G030-Datasheet.pdf", author="STMicroelectronics")

    item = service.add_pdf(src, manufacturer_folder="")

    assert item.manufacturer == "STMicroelectronics"
    assert item.manufacturer_folder == "STMicroelectronics"
    assert (root / "datasheets" / "STMicroelectronics" / src.name).is_file()


def test_add_pdf_with_custom_folder_keeps_custom_name(tmp_path):
    root = tmp_path / "Lib"
    service = LibraryService()
    service.create_library(root)
    src = _fake_pdf(tmp_path / "STM32G030-Datasheet.pdf", author="STMicroelectronics")

    item = service.add_pdf(src, manufacturer_folder="My Parts")

    assert item.manufacturer_folder == "My Parts"
    assert item.manufacturer == "STMicroelectronics"  # detected, but folder is custom


def test_create_and_open_roundtrip(tmp_path):
    root = tmp_path / "Lib"
    service = LibraryService()
    service.create_library(root)
    _fake_pdf(tmp_path / "MAX17201.pdf", author="Maxim Integrated")
    service.add_pdf(tmp_path / "MAX17201.pdf", manufacturer_folder="")

    assert service.store is not None
    assert service.store.item_count == 1

    # A fresh service opens the same library from disk.
    other = LibraryService()
    store = other.open_library(root)
    assert store.item_count == 1
    assert store.get_item(service.store.items[0].item_id) is not None


def test_save_summary_via_service(tmp_path):
    root = tmp_path / "Lib"
    service = LibraryService()
    service.create_library(root)
    src = _fake_pdf(tmp_path / "ATMEGA328.pdf", author="Microchip Technology")
    item = service.add_pdf(src, manufacturer_folder="")

    summary_path = service.save_summary(item.item_id, "# Summary")

    assert summary_path.is_file()
    assert "Microchip" in str(summary_path)


def test_remove_and_move_via_service(tmp_path):
    root = tmp_path / "Lib"
    service = LibraryService()
    service.create_library(root)
    src = _fake_pdf(tmp_path / "MAX17201.pdf", author="Maxim Integrated")
    item = service.add_pdf(src, manufacturer_folder="")

    moved = service.move_item(item.item_id, "Renesas")
    assert moved.manufacturer_folder == "Renesas"

    service.remove_item(item.item_id)
    assert service.store.item_count == 0
