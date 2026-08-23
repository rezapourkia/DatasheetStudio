"""Unit tests for the local datasheet library storage layer."""

import json
import shutil
from pathlib import Path

from datasheet_studio.infrastructure.storage.library_store import (
    LibraryError,
    LibraryStore,
    MANIFEST_FILENAME,
)
from datasheet_studio.models.library_item import LibraryItemKind


def _sample_pdf(path: Path) -> Path:
    pdf = path / "STM32G431zzzz-Datasheet.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 fake datasheet content")
    return pdf


def test_create_library_creates_manifest_and_folders(tmp_path):
    root = tmp_path / "MyLib"
    store = LibraryStore.create(root, name="My Library")

    assert (root / MANIFEST_FILENAME).is_file()
    assert (root / "datasheets").is_dir()
    assert (root / "summaries").is_dir()
    assert store.name == "My Library"
    assert store.item_count == 0

    manifest = json.loads((root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["categories"]["datasheet"] == "datasheets"


def test_is_library_folder_detects_valid_and_rejects_plain(tmp_path):
    root = tmp_path / "Lib"
    LibraryStore.create(root)

    assert LibraryStore.is_library_folder(root) is True
    assert LibraryStore.is_library_folder(tmp_path / "nope") is False

    plain = tmp_path / "plain"
    plain.mkdir()
    assert LibraryStore.is_library_folder(plain) is False


def test_add_item_copies_file_and_registers(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")

    item = store.add_item_from_source(
        src,
        kind=LibraryItemKind.DATASHEET,
        manufacturer_folder="STMicroelectronics",
        manufacturer="STMicroelectronics",
        part_number="STM32G431",
        page_count=240,
    )

    stored = root / "datasheets" / "STMicroelectronics" / src.name
    assert stored.is_file()
    assert item.relative_path == "datasheets/STMicroelectronics/STM32G431zzzz-Datasheet.pdf"
    assert store.item_count == 1
    assert store.item_path(item) == stored


def test_add_item_duplicate_name_gets_unique_file(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")

    first = store.add_item_from_source(
        src, manufacturer_folder="Microchip", manufacturer="Microchip"
    )
    second = store.add_item_from_source(
        src, manufacturer_folder="Microchip", manufacturer="Microchip"
    )

    assert first.relative_path != second.relative_path
    assert (root / "datasheets" / "Microchip" / "STM32G431zzzz-Datasheet (1).pdf").is_file()
    assert store.item_count == 2


def test_add_item_creates_custom_manufacturer_folder(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")

    item = store.add_item_from_source(
        src, manufacturer_folder="My Custom Vendor", manufacturer=""
    )

    assert (root / "datasheets" / "My Custom Vendor" / src.name).is_file()
    assert item.manufacturer_folder == "My Custom Vendor"



def test_manifest_roundtrip_preserves_items(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    item = store.add_item_from_source(
        src,
        manufacturer_folder="STMicroelectronics",
        manufacturer="STMicroelectronics",
        title="STM32G431 Datasheet",
        part_number="STM32G431",
        page_count=240,
        tags=["MCU", "ARM"],
    )
    store.save_summary(item.item_id, "# Summary\n\nFast core.")

    reopened = LibraryStore(root)
    assert reopened.item_count == 1
    loaded = reopened.get_item(item.item_id)
    assert loaded is not None
    assert loaded.title == "STM32G431 Datasheet"
    assert loaded.part_number == "STM32G431"
    assert loaded.tags == ["MCU", "ARM"]
    assert loaded.summary_file is not None
    assert (root / loaded.summary_file).is_file()
    assert "Fast core" in loaded.summary_text


def test_save_summary_writes_markdown_and_replaces(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    item = store.add_item_from_source(
        src, manufacturer_folder="STMicroelectronics", manufacturer="STMicroelectronics"
    )

    first = store.save_summary(item.item_id, "version one")
    assert first.is_file()
    second = store.save_summary(item.item_id, "version two")

    item2 = store.get_item(item.item_id)
    assert item2 is not None
    assert (root / item2.summary_file).is_file()
    assert (root / item2.summary_file).read_text(encoding="utf-8") == "version two"


def test_remove_item_deletes_file_and_summary(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    item = store.add_item_from_source(
        src, manufacturer_folder="Microchip", manufacturer="Microchip"
    )
    store.save_summary(item.item_id, "sum")

    store.remove_item(item.item_id)

    assert store.item_count == 0
    assert not (root / item.relative_path).exists()
    assert not (root / item.summary_file).exists()


def test_move_item_moves_file_and_updates_relative_path(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    item = store.add_item_from_source(
        src, manufacturer_folder="STMicroelectronics", manufacturer="STMicroelectronics"
    )

    moved = store.move_item(item.item_id, "NXP")

    assert moved.manufacturer_folder == "NXP"
    assert (root / "datasheets" / "NXP" / src.name).is_file()
    assert not (root / "datasheets" / "STMicroelectronics" / src.name).exists()



def test_reindex_discovers_untracked_pdfs(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    store.add_item_from_source(
        src, manufacturer_folder="STMicroelectronics", manufacturer="STMicroelectronics"
    )

    # Drop in a new PDF behind the store's back.
    new_dir = root / "datasheets" / "Texas Instruments"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "TPS54331.pdf").write_bytes(b"%PDF fake ti")

    added, new_items = store.reindex()

    assert added == 1
    assert new_items[0].manufacturer_folder == "Texas Instruments"
    assert store.item_count == 2


def test_library_survives_folder_copy(tmp_path):
    """Copying the whole library folder must keep the index working."""
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    item = store.add_item_from_source(
        src,
        manufacturer_folder="STMicroelectronics",
        manufacturer="STMicroelectronics",
        part_number="STM32G431",
    )
    store.save_summary(item.item_id, "summary")

    moved = tmp_path / "MovedElsewhere"
    shutil.copytree(root, moved)

    reopened = LibraryStore(moved)
    assert reopened.item_count == 1
    loaded = reopened.get_item(item.item_id)
    assert loaded is not None
    assert loaded.part_number == "STM32G431"
    assert (moved / loaded.relative_path).is_file()
    assert (moved / loaded.summary_file).is_file()


def test_search_matches_part_number_title_manufacturer(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src1 = _sample_pdf(tmp_path / "a")
    src2 = tmp_path / "TPS54331.pdf"
    src2.write_bytes(b"%PDF fake ti")
    src3 = tmp_path / "ATMEGA328.pdf"
    src3.write_bytes(b"%PDF fake mchp")

    store.add_item_from_source(
        src1,
        manufacturer_folder="STMicroelectronics",
        manufacturer="STMicroelectronics",
        part_number="STM32G431",
        tags=["MCU", "ARM"],
    )
    store.add_item_from_source(
        src2,
        manufacturer_folder="Texas Instruments",
        manufacturer="Texas Instruments",
        part_number="TPS54331",
    )
    store.add_item_from_source(
        src3,
        manufacturer_folder="Microchip",
        manufacturer="Microchip",
        part_number="ATMEGA328",
    )

    assert len(store.search("STM32G431")) == 1
    assert len(store.search("Texas")) == 1
    assert len(store.search("MCU")) == 1
    assert len(store.search("")) == 3
    results = store.search("stm")
    assert len(results) == 1
    assert results[0].part_number == "STM32G431"


def test_search_scored_relevance_orders_exact_first(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    a = tmp_path / "MAX17201.pdf"
    a.write_bytes(b"%PDF")
    b = tmp_path / "MAX17215.pdf"
    b.write_bytes(b"%PDF")

    store.add_item_from_source(
        a, manufacturer_folder="Maxim", manufacturer="Maxim", part_number="MAX17201"
    )
    store.add_item_from_source(
        b, manufacturer_folder="Maxim", manufacturer="Maxim", part_number="MAX17215"
    )

    results = store.search("MAX17201")
    assert results[0].part_number == "MAX17201"


def test_search_matches_summary_text(tmp_path):
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = _sample_pdf(tmp_path / "src")
    item = store.add_item_from_source(
        src, manufacturer_folder="STMicroelectronics", manufacturer="STMicroelectronics"
    )
    store.save_summary(item.item_id, "DMA controller supports many channels")

    assert len(store.search("DMA")) == 1
    assert len(store.search("channels")) == 1


def test_software_kind_record_can_be_added(tmp_path):
    """Proves extensibility: a SOFTWARE record is persisted like a datasheet."""
    root = tmp_path / "Lib"
    store = LibraryStore.create(root)
    src = tmp_path / "my_tool.pdf"
    src.write_bytes(b"%PDF")

    item = store.add_item_from_source(
        src,
        kind=LibraryItemKind.SOFTWARE,
        manufacturer_folder="Tools",
        manufacturer="Tools",
    )

    assert item.kind is LibraryItemKind.SOFTWARE
    assert (root / "software" / "Tools" / "my_tool.pdf").is_file()

    reopened = LibraryStore(root)
    assert reopened.get_item(item.item_id).kind is LibraryItemKind.SOFTWARE


def test_invalid_manifest_raises(tmp_path):
    root = tmp_path / "Lib"
    LibraryStore.create(root)
    (root / MANIFEST_FILENAME).write_text("not json", encoding="utf-8")

    try:
        LibraryStore(root)
    except LibraryError:
        pass
    else:
        raise AssertionError("Expected LibraryError for corrupted manifest")


def test_remove_missing_item_raises(tmp_path):
    store = LibraryStore.create(tmp_path / "Lib")
    try:
        store.remove_item("does-not-exist")
    except LibraryError:
        pass
    else:
        raise AssertionError("Expected LibraryError for missing item")

