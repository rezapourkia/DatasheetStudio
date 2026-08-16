"""Unit tests for selection (de)compression service."""

from datetime import datetime

from datasheet_studio.models.selected_page import SelectedPage
from datasheet_studio.services.selection_storage import (
    SelectionStorage,
    SelectionStorageError,
)


def _make_pages():
    return {
        1: SelectedPage(page_number=1, document_path=r"C:\docs\sample.pdf", note="first"),
        3: SelectedPage(
            page_number=3,
            document_path=r"C:\docs\sample.pdf",
            note="third",
            selected_at=datetime(2026, 8, 1, 12, 30),
        ),
    }


def test_roundtrip_save_load(tmp_path):
    target = tmp_path / "selection.dssel"
    SelectionStorage.save(target, r"C:\docs\sample.pdf", _make_pages())

    document_path, pages = SelectionStorage.load(target)

    assert document_path == r"C:\docs\sample.pdf"
    assert [p.page_number for p in pages] == [1, 3]
    by_number = {p.page_number: p for p in pages}
    assert by_number[1].note == "first"
    assert by_number[3].note == "third"
    assert by_number[3].selected_at == datetime(2026, 8, 1, 12, 30)


def test_load_missing_file_raises(tmp_path):
    missing = tmp_path / "missing.dssel"
    try:
        SelectionStorage.load(missing)
    except SelectionStorageError:
        pass
    else:
        raise AssertionError("Expected SelectionStorageError for missing file")


def test_load_invalid_archive_raises(tmp_path):
    bad = tmp_path / "bad.dssel"
    bad.write_bytes(b"this is not a zip archive")
    try:
        SelectionStorage.load(bad)
    except SelectionStorageError:
        pass
    else:
        raise AssertionError("Expected SelectionStorageError for invalid archive")
