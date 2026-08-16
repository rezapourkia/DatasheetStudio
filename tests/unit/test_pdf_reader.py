"""Unit tests for the PyMuPDF-backed PDF reader."""

import pymupdf
import pytest

from datasheet_studio.infrastructure.pdf.reader import PdfOpenError, PdfReader
from datasheet_studio.models.pdf_document import PdfDocumentInfo


def _make_sample_pdf(tmp_path, name="sample.pdf"):
    """Create a small 3-page PDF with bookmarks and metadata."""
    path = tmp_path / name
    doc = pymupdf.open()

    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")

    doc.set_metadata({"title": "Test Datasheet", "author": "Tester"})
    doc.set_toc(
        [
            [1, "Introduction", 1],
            [1, "Specifications", 2],
            [2, "Electrical", 2],
            [1, "Packages", 3],
        ]
    )
    doc.save(str(path))
    doc.close()
    return path


def test_open_returns_document_info(tmp_path):
    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()

    info = reader.open(pdf_path)

    assert isinstance(info, PdfDocumentInfo)
    assert info.page_count == 3
    assert info.title == "Test Datasheet"
    assert info.author == "Tester"
    assert len(info.bookmarks) == 4
    assert info.bookmarks[0].title == "Introduction"
    assert info.bookmarks[0].page == 1
    assert info.bookmarks[0].level == 1
    assert info.bookmarks[2].level == 2


def test_open_missing_file_raises(tmp_path):
    reader = PdfReader()
    missing = tmp_path / "does_not_exist.pdf"
    with pytest.raises(PdfOpenError):
        reader.open(missing)


def test_open_non_pdf_raises(tmp_path):
    reader = PdfReader()
    bad_file = tmp_path / "not_a_pdf.txt"
    bad_file.write_text("this is not a pdf", encoding="utf-8")
    with pytest.raises(PdfOpenError):
        reader.open(bad_file)


def test_render_page_returns_png_bytes(tmp_path):
    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()

    png = reader.render_page_png(pdf_path, page_number=1, zoom=1.0)

    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_page_out_of_range_raises(tmp_path):
    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()
    with pytest.raises(PdfOpenError):
        reader.render_page_png(pdf_path, page_number=99)


def test_get_page_text_returns_text(tmp_path):
    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()

    text = reader.get_page_text(pdf_path, 1)

    assert "Page 1" in text
    assert reader.get_page_text(pdf_path, 3) == "Page 3"


def test_get_page_text_out_of_range_raises(tmp_path):
    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()
    with pytest.raises(PdfOpenError):
        reader.get_page_text(pdf_path, 99)


def test_add_notes_to_pdf_saves_incrementally(tmp_path):
    """Notes must be saved to the same file without raising (incremental save)."""
    from datasheet_studio.models.pdf_document import PdfNote

    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()
    note = PdfNote(page_number=1, text="Important note", x=0.5, y=0.5)

    reader.add_notes_to_pdf(pdf_path, [note])

    doc = pymupdf.open(str(pdf_path))
    try:
        assert doc.page_count == 3
        annotations = list(doc[0].annots() or [])
        assert len(annotations) >= 1
        assert annotations[0].info.get("content", "") == "Important note"
    finally:
        doc.close()


def test_copy_selected_pages_into_new_pdf(tmp_path):
    """Selected pages from a source PDF can be copied into a new PDF file."""
    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()

    source_doc = pymupdf.open(str(pdf_path))
    new_doc = pymupdf.open()
    try:
        for page_num in (1, 3):
            page_index = page_num - 1
            new_doc.insert_pdf(source_doc, from_page=page_index, to_page=page_index)
        output = tmp_path / "selected.pdf"
        new_doc.save(str(output))
    finally:
        new_doc.close()
        source_doc.close()

    saved = pymupdf.open(str(output))
    try:
        assert saved.page_count == 2
        assert saved[0].get_text().strip() == "Page 1"
        assert saved[1].get_text().strip() == "Page 3"
    finally:
        saved.close()


def test_get_pinout_lqfp48_returns_all_pins():
    """The LQFP48 pinout table must yield exactly pins 1-48 with AFs."""
    reader = PdfReader()
    rows = reader.get_pinout("example/STM32G431zzzz-Datasheet.pdf", "LQFP48")

    assert len(rows) == 48
    assert [int(r["pin"]) for r in rows] == list(range(1, 49))

    pb12 = next(r for r in rows if r["name"] == "PB12")
    assert pb12["pin"] == "26"
    assert pb12["type"] == "I/O"
    # AF numbers from the alternate-function table are joined in.
    assert "AF4=I2C2 SMBA" in pb12["alternate_functions"]
    assert "AF15=EVENT OUT" in pb12["alternate_functions"]


def test_get_pinout_unknown_package_returns_empty():
    reader = PdfReader()
    rows = reader.get_pinout("example/STM32G431zzzz-Datasheet.pdf", "BGA999")
    assert rows == []


def test_get_pinout_generic_ti_style_bq25798():
    """A TOC-less TI datasheet (PIN/NAME/NO./TYPE/DESCRIPTION, range pin
    numbers like ``2-3``) must still be recognized by the generic extractor."""
    reader = PdfReader()
    all_pinouts = reader.get_all_pinouts(
        "BQ25798 I2 C Controlled, 1 to 4-Cell, 5A Buck-Boost Battery_1-128.pdf"
    )
    assert "VQFN29" in all_pinouts
    rows = all_pinouts["VQFN29"]
    assert len(rows) >= 20

    by_name = {r["name"]: r for r in rows}
    assert by_name["STAT"]["pin"] == "1"
    assert by_name["STAT"]["type"] == "DO"
    # Multi-pad pins use range numbers.
    assert by_name["VBUS"]["pin"] == "2-3"
    assert by_name["PMID"]["pin"] == "29"

    available = reader.get_available_packages(
        "BQ25798 I2 C Controlled, 1 to 4-Cell, 5A Buck-Boost Battery_1-128.pdf"
    )
    assert available[0]["package"] == "VQFN29"
    assert available[0]["pin_count"] == 29


def test_get_available_packages_multi_package_pinout_table_attiny1614():
    """ATtiny1614 has one table with four package variants in separate columns."""
    reader = PdfReader()
    all_pinouts = reader.get_all_pinouts(
        "example/ATtiny1614-16-17-DataSheet-DS40002204A.pdf"
    )

    available = reader.get_available_packages(
        "example/ATtiny1614-16-17-DataSheet-DS40002204A.pdf"
    )
    assert [(p["package"], p["pin_count"]) for p in available] == [
        ("SOIC14", 14),
        ("SOIC20", 20),
        ("VQFN20", 20),
        ("VQFN24", 24),
    ]

    rows = all_pinouts["SOIC14"]
    assert len(rows) == 14
    assert [r["pin"] for r in rows[:5]] == ["1", "2", "3", "4", "5"]
    assert rows[-1]["pin"] == "14"

    rows_20 = all_pinouts["VQFN20"]
    assert len(rows_20) == 20
    assert rows_20[0]["pin"] == "1"
    assert rows_20[-1]["pin"] == "20"


def test_get_available_packages_multi_package_pinout_table_max17201():
    """MAX17201 has package labels in the first data row after header."""
    reader = PdfReader()
    all_pinouts = reader.get_all_pinouts("example/MAX17201-MAX17215.pdf")

    available = reader.get_available_packages("example/MAX17201-MAX17215.pdf")
    assert [item["package"] for item in available] == ["TDFN", "WLP"]
    assert [item["pin_count"] for item in available] == [14, 15]

    assert len(all_pinouts["TDFN"]) == 14
    assert all_pinouts["TDFN"][0]["pin"] == "1"

    assert len(all_pinouts["WLP"]) == 15
    assert all_pinouts["WLP"][0]["pin"] == "A1"


def test_extraction_hint_reports_incomplete_file():
    """Two-page excerpts have no pin table; the hint must say so instead of
    silently returning nothing."""
    reader = PdfReader()
    hint = reader.extraction_hint("1324_MAX17201-MAX17215_1-2.pdf")
    assert "incomplete" in hint.lower()


def test_detect_package_prefers_count_near_family():
    """Package counts are only trusted next to the family token, so section
    headings like ``5 Pin Configuration`` are not misread."""
    assert PdfReader._detect_package("5 Pin Configuration and Functions\nVQFN (29)", 27) == "VQFN29"
    assert PdfReader._detect_package("28-Pin TSSOP\nLQFP details", 20) == "TSSOP28"
    assert PdfReader._detect_package("no package mentioned here", 12) == "12P"
    assert PdfReader._detect_package("", 8) == "8P"


def test_save_selected_pages_with_compression(tmp_path):
    """Compressed PDF output must be valid and 'best' smaller than plain."""
    import os

    reader = PdfReader()
    plain = tmp_path / "plain.pdf"
    best = tmp_path / "best.pdf"
    reader.save_selected_pages("example/STM32G431zzzz-Datasheet.pdf", [1, 2], plain)
    reader.save_selected_pages(
        "example/STM32G431zzzz-Datasheet.pdf", [1, 2], best, compression="best"
    )

    assert os.path.getsize(plain) > 0
    assert os.path.getsize(best) > 0
    assert os.path.getsize(best) < os.path.getsize(plain)

    saved = pymupdf.open(str(best))
    try:
        assert saved.page_count == 2
        assert saved[0].get_text().strip() != ""
    finally:
        saved.close()


def test_get_available_packages_lists_symbol_variants():
    """The datasheet's packages (symbol variants) must be listed with their
    pin counts — e.g. STM32G030 has SO8N/TSSOP20/LQFP32/LQFP48."""
    reader = PdfReader()

    g030 = reader.get_available_packages(
        "example/STM32G030K8T6-STMicroelectronics.pdf"
    )
    assert [(p["package"], p["pin_count"]) for p in g030] == [
        ("SO8N", 8),
        ("TSSOP20", 20),
        ("LQFP32", 32),
        ("LQFP48", 48),
    ]

    g431 = reader.get_available_packages(
        "example/STM32G431zzzz-Datasheet.pdf"
    )
    assert len(g431) == 9
    by_name = {p["package"]: p["pin_count"] for p in g431}
    assert by_name["LQFP48"] == 48
    assert by_name["WLCSP49"] == 49
    assert by_name["UFBGA64"] == 64
    assert by_name["LQFP100"] == 100


def test_save_selected_pages_includes_notes(tmp_path):
    """Notes attached to selected pages must appear in the exported PDF."""
    from datasheet_studio.models.pdf_document import PdfNote

    pdf_path = _make_sample_pdf(tmp_path)
    reader = PdfReader()
    notes_by_page = {
        1: [PdfNote(page_number=1, text="Note on page 1", x=0.5, y=0.5)],
    }
    output = tmp_path / "selected_with_notes.pdf"

    reader.save_selected_pages(pdf_path, [1, 3], output, notes_by_page)

    saved = pymupdf.open(str(output))
    try:
        assert saved.page_count == 2
        annots = list(saved[0].annots() or [])
        assert len(annots) == 1
        assert annots[0].info.get("content") == "Note on page 1"
        assert len(list(saved[1].annots() or [])) == 0
    finally:
        saved.close()
