"""Unit tests for the Library panel UI."""

from pathlib import Path

from PySide6.QtWidgets import QTabWidget, QTreeWidget

from datasheet_studio.ui.main_window import MainWindow


def _make_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path


def _fresh_window(qapp_instance) -> MainWindow:
    """A MainWindow with a clean QSettings library path."""
    from PySide6.QtCore import QSettings

    from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION

    settings = QSettings(APP_ORGANIZATION, APP_NAME)
    settings.remove("libraryPath")
    window = MainWindow()
    return window


def test_library_panel_is_real_widget(qapp_instance):
    window = _fresh_window(qapp_instance)
    assert hasattr(window, "_library_panel")
    window.close()


def test_library_panel_has_search_and_tree(qapp_instance):
    window = _fresh_window(qapp_instance)
    panel = window._library_panel
    assert panel.findChild(QTreeWidget) is not None
    assert hasattr(panel, "_search_edit")
    window.close()


def test_library_tab_still_inside_left_panel(qapp_instance):
    window = _fresh_window(qapp_instance)
    central = window.centralWidget()
    left_panel = central.widget(0)

    tabs = [
        child
        for child in left_panel.findChildren(QTabWidget)
        if child.tabText(0) == "Bookmarks" and child.tabText(1) == "Library"
    ]
    assert tabs, "Left panel should contain Bookmarks/Library tabs"
    window.close()


def test_open_library_populates_tree(qapp_instance, tmp_path):
    window = _fresh_window(qapp_instance)
    service = window._library_service
    root = tmp_path / "Lib"
    service.create_library(root)
    src = _make_pdf(tmp_path / "STM32G431-Datasheet.pdf")
    service.add_pdf(src, manufacturer_folder="STMicroelectronics")

    window._library_panel.refresh()

    tree = window._library_panel.findChild(QTreeWidget)
    assert tree is not None
    assert tree.topLevelItemCount() == 1  # one kind node: Datasheets
    kind_node = tree.topLevelItem(0)
    assert kind_node.text(0) == "Datasheets"
    assert kind_node.childCount() == 1  # one manufacturer folder
    folder_node = kind_node.child(0)
    assert folder_node.text(0) == "STMicroelectronics"
    assert folder_node.childCount() == 1
    window.close()


def test_search_filters_tree(qapp_instance, tmp_path):
    window = _fresh_window(qapp_instance)
    service = window._library_service
    root = tmp_path / "Lib"
    service.create_library(root)

    service.add_pdf(
        _make_pdf(tmp_path / "STM32G431-Datasheet.pdf"),
        manufacturer_folder="STMicroelectronics",
    )
    service.add_pdf(
        _make_pdf(tmp_path / "TPS54331-Datasheet.pdf"),
        manufacturer_folder="Texas Instruments",
    )

    panel = window._library_panel
    panel.refresh()
    tree = panel.findChild(QTreeWidget)

    # Empty query shows everything.
    panel._search_edit.setText("")
    panel._apply_search()
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).childCount() == 2

    # A matching query narrows the results.
    panel._search_edit.setText("STM32")
    panel._apply_search()
    kind_node = tree.topLevelItem(0)
    assert kind_node.childCount() == 1
    assert kind_node.child(0).text(0) == "STMicroelectronics"

    # No match → a "no matches" hint item.
    panel._search_edit.setText("zzz-no-match-zzz")
    panel._apply_search()
    assert tree.topLevelItemCount() == 1
    assert "No matches" in tree.topLevelItem(0).text(0)
    window.close()


def test_add_current_pdf_action_enabled_after_open(qapp_instance, tmp_path):
    window = _fresh_window(qapp_instance)
    pdf = _make_pdf(tmp_path / "sample.pdf")
    info = window._reader.open(pdf)
    window._pdf_info = info
    window._activate_document_ui()

    assert window._add_to_library_action.isEnabled() is True
    assert window._library_panel._add_button.isEnabled() is True
    window.close()
