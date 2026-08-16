"""Unit tests for the Application Shell module."""

import unittest.mock as mock

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QSplitter, QTabWidget

from datasheet_studio.core.constants import APP_NAME
from datasheet_studio.ui.main_window import MainWindow


def _save_dialog_mocks(path):
    """List of mock patches that make the instance-based save dialog accept
    ``path``."""
    return [
        mock.patch.object(
            QFileDialog, "exec", return_value=QDialog.DialogCode.Accepted
        ),
        mock.patch.object(QFileDialog, "selectedFiles", return_value=[path]),
        mock.patch.object(
            QMessageBox, "exec", return_value=QDialog.DialogCode.Accepted
        ),
        mock.patch.object(QMessageBox, "critical", return_value=None),
        mock.patch.object(QMessageBox, "warning", return_value=None),
        mock.patch.object(QMessageBox, "information", return_value=None),
    ]


def _activate_mocks(patches):
    """Context manager that activates a list of mock patches."""
    from contextlib import ExitStack

    stack = ExitStack()
    for patch in patches:
        stack.enter_context(patch)
    return stack


def test_main_window_title(qapp_instance):
    window = MainWindow()
    assert window.windowTitle() == APP_NAME
    window.close()


def test_central_area_has_four_panels(qapp_instance):
    window = MainWindow()
    central = window.centralWidget()
    assert isinstance(central, QSplitter)
    assert central.count() == 4
    window.close()


def test_menu_bar_has_expected_menus(qapp_instance):
    window = MainWindow()
    menu_titles = [action.text() for action in window.menuBar().actions()]
    assert menu_titles == ["&File", "&View", "&Tools", "&Help"]
    window.close()


def test_open_action_is_enabled(qapp_instance):
    window = MainWindow()
    file_action = window.menuBar().actions()[0]
    file_menu = file_action.menu()

    open_action = file_menu.actions()[0]
    assert open_action.text() == "&Open Datasheet..."
    assert open_action.isEnabled() is True

    window.close()


def test_left_panel_has_library_and_bookmarks_tabs(qapp_instance):
    window = MainWindow()
    central = window.centralWidget()
    left_panel = central.widget(0)

    tabs = [
        child
        for child in left_panel.findChildren(QTabWidget)
        if child.tabText(0) == "Bookmarks" and child.tabText(1) == "Library"
    ]
    assert tabs, "Left panel should contain Bookmarks/Library tabs"
    window.close()


def test_ai_panel_has_chat_summary_report_tabs(qapp_instance):
    window = MainWindow()
    central = window.centralWidget()
    ai_panel = central.widget(3)

    tabs = [
        child
        for child in ai_panel.findChildren(QTabWidget)
        if child.count() == 4
        and child.tabText(0) == "Chat"
        and child.tabText(1) == "Summary"
        and child.tabText(2) == "Report"
        and child.tabText(3) == "⚙️ Settings"
    ]
    assert tabs, "AI panel should contain Chat/Summary/Report/Settings tabs"
    window.close()


def test_send_ai_message_does_not_raise(qapp_instance):
    """Sending an AI chat message must not raise (regression for NameError)."""
    import json
    import time
    import unittest.mock as mock

    from datasheet_studio.ui.main_window import MainWindow

    class _FakeResponse:
        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "mock reply"}}]}
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=None):
        return _FakeResponse()

    window = MainWindow()
    try:
        window._ai_api_key_input.setText("sk-test")
        window._update_ai_interface_state()
        assert window._ai_send_button.isEnabled()

        window._ai_chat_input.setPlainText("hello")
        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            window._send_ai_message()

            deadline = time.time() + 3
            while time.time() < deadline:
                qapp_instance.processEvents()
                if any(
                    m["role"] == "assistant" and "mock reply" in m["content"]
                    for m in window._ai_chat_messages
                ):
                    break
                time.sleep(0.05)

        assert any(
            m["role"] == "assistant" and "mock reply" in m["content"]
            for m in window._ai_chat_messages
        )
    finally:
        window.close()

def test_send_button_click_does_not_raise(qapp_instance):
    """Regression: clicking the Send button (not calling the slot directly)
    must actually send the message. QPushButton.clicked emits a `checked:
    bool` argument; if the button were connected straight to
    `_send_ai_message`, that `False` would land in the `force_message`
    parameter and crash on `False.strip()`, silently doing nothing."""
    import json
    import time
    import unittest.mock as mock

    from datasheet_studio.ui.main_window import MainWindow

    class _FakeResponse:
        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "clicked reply"}}]}
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=None):
        return _FakeResponse()

    window = MainWindow()
    try:
        window._ai_api_key_input.setText("sk-test")
        window._update_ai_interface_state()
        window._ai_chat_input.setPlainText("hello via click")

        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            window._ai_send_button.click()

            deadline = time.time() + 3
            while time.time() < deadline:
                qapp_instance.processEvents()
                if any(
                    m["role"] == "assistant" and "clicked reply" in m["content"]
                    for m in window._ai_chat_messages
                ):
                    break
                time.sleep(0.05)

        assert any(
            m["role"] == "assistant" and "clicked reply" in m["content"]
            for m in window._ai_chat_messages
        ), "Send button click should have produced an assistant reply"
    finally:
        window.close()


def test_save_selection_button_click_creates_pdf(qapp_instance, tmp_path):
    """Regression: clicking the real Save button in the Selected Pages panel
    must produce a PDF file."""
    import os

    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    out_path = str(tmp_path / "selection_out.pdf")

    window = MainWindow()
    try:
        info = PdfReader().open(os.path.join("example", "a1.pdf"))
        window._pdf_info = info
        window._activate_document_ui()
        window._add_page_to_selected(1)
        window._add_page_to_selected(3)

        # The service normalizes the document path to absolute on open.
        assert os.path.isabs(window._pdf_info.path)

        with _activate_mocks(_save_dialog_mocks(out_path)):
            window._save_selection_button.click()

        assert os.path.isfile(out_path), "Save button click should produce a PDF file"
        assert os.path.getsize(out_path) > 0
    finally:
        window.close()
        if os.path.exists(out_path):
            os.remove(out_path)


def test_save_selection_default_name(qapp_instance):
    """The save dialog should be pre-filled with a sensible filename so it can
    never be submitted empty (which previously produced no file)."""
    from datasheet_studio.models.pdf_document import PdfDocumentInfo

    window = MainWindow()
    try:
        window._pdf_info = PdfDocumentInfo(
            path=r"C:\docs\STM32G030.pdf", page_count=10, title="STM32G030"
        )
        window._add_page_to_selected(1)
        window._add_page_to_selected(5)
        name = window._build_default_selection_name()
        assert name == "STM32G030_1-5.pdf"
        assert not any(ch in name for ch in '\\/:*?"<>|')

        # Fall back to the file stem when the PDF has no title.
        window._clear_selected_pages()
        window._pdf_info = PdfDocumentInfo(
            path=r"C:\docs\some dir\raw sheet.pdf", page_count=10, title=""
        )
        window._add_page_to_selected(2)
        name = window._build_default_selection_name()
        assert name == "raw sheet_2-2.pdf"
    finally:
        window.close()


def test_ai_tool_get_pinout(qapp_instance):
    """The get_pinout AI tool returns a complete LQFP48 pinout."""
    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    window = MainWindow()
    try:
        window._pdf_info = PdfReader().open(
            "example/STM32G431zzzz-Datasheet.pdf"
        )
        result = window._execute_ai_tool("get_pinout", {"package": "LQFP48"})

        assert result["package"] == "LQFP48"
        assert result["count"] == 48
        assert result["rows"][25]["name"] == "PB12"  # pin 26
        assert "AF4=" in result["rows"][25]["alternate_functions"]
    finally:
        window.close()


def test_ai_chat_assistant_bubble_expands_to_content(qapp_instance):
    """A long assistant reply (e.g. a pinout table) must render fully visible
    instead of collapsing to a tiny height (QTextBrowser auto-height fix)."""
    import time

    from datasheet_studio.ui.main_window import _AutoHeightTextBrowser

    window = MainWindow()
    try:
        window.resize(1200, 800)
        window.show()
        long_md = "| Pin | Name |\n|---|---|\n" + "\n".join(
            f"| {i} | PA{i} |" for i in range(1, 50)
        )
        window._append_ai_message("assistant", long_md)
        for _ in range(10):
            qapp_instance.processEvents()
            time.sleep(0.02)

        browsers = window._ai_chat_content.findChildren(_AutoHeightTextBrowser)
        assert len(browsers) == 1, "one assistant bubble should be rendered"
        browser = browsers[0]
        # The document must be laid out and the browser must expand to it.
        assert browser.document().size().height() > 400
        assert browser.height() > 400
    finally:
        window.close()


def test_viewer_label_resizes_to_page_when_zoomed(qapp_instance):
    """Zooming a page must enlarge the viewer label so scrollbars appear and
    right-click-drag panning can move the page."""
    import time

    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    window = MainWindow()
    try:
        window.resize(1000, 700)
        window.show()
        window._pdf_info = PdfReader().open(
            "example/STM32G431zzzz-Datasheet.pdf"
        )
        window._activate_document_ui()
        window._zoom = 4.0
        window._render_page(1)
        for _ in range(10):
            qapp_instance.processEvents()
            time.sleep(0.02)

        label = window._viewer_label
        assert label.width() == label.pixmap().width()
        assert label.height() == label.pixmap().height()
        assert window._scroll_area.verticalScrollBar().maximum() > 0
        assert window._scroll_area.horizontalScrollBar().maximum() > 0
    finally:
        window.close()


def test_compress_selection_button_creates_pdf(qapp_instance, tmp_path):
    """Clicking the real Compress button must produce a compressed PDF file."""
    import os

    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    out_path = str(tmp_path / "compressed_out.pdf")

    window = MainWindow()
    try:
        window._pdf_info = PdfReader().open(
            "example/STM32G431zzzz-Datasheet.pdf"
        )
        window._activate_document_ui()
        window._add_page_to_selected(1)
        window._add_page_to_selected(3)

        with _activate_mocks(_save_dialog_mocks(out_path)):
            window._compress_selection_button.click()

        assert os.path.isfile(out_path), "Compress button should produce a PDF file"
        assert os.path.getsize(out_path) > 0
    finally:
        window.close()
        if os.path.exists(out_path):
            os.remove(out_path)


def test_save_dialog_defaults_to_datasheet_folder(qapp_instance):
    """The save dialog must open in the open datasheet's folder (so the saved
    file is easy to find) with a pre-filled default name."""
    import os

    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    window = MainWindow()
    try:
        info = PdfReader().open(os.path.join("example", "a1.pdf"))
        window._pdf_info = info
        window._activate_document_ui()
        window._add_page_to_selected(1)

        default_path = window._get_save_default_path()
        assert os.path.dirname(default_path) == os.path.dirname(info.path)
        assert default_path.endswith(".pdf")
    finally:
        window.close()


def test_save_dialog_accepted_with_empty_path_shows_warning(qapp_instance, tmp_path):
    """An accepted save dialog with no filename must show a visible warning —
    the save flow must never fail silently."""
    import os

    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    out_path = str(tmp_path / "nothing.pdf")
    window = MainWindow()
    try:
        info = PdfReader().open(os.path.join("example", "a1.pdf"))
        window._pdf_info = info
        window._activate_document_ui()
        window._add_page_to_selected(1)

        with (
            mock.patch.object(
                QFileDialog, "exec", return_value=QDialog.DialogCode.Accepted
            ),
            mock.patch.object(QFileDialog, "selectedFiles", return_value=[]),
            mock.patch.object(QMessageBox, "warning", return_value=None) as warn,
            mock.patch.object(QMessageBox, "critical", return_value=None),
        ):
            window._save_selection_button.click()

        warn.assert_called_once()
        assert not os.path.exists(out_path)
    finally:
        window.close()


def test_ai_tool_get_packages(qapp_instance):
    """The get_packages AI tool lists the datasheet's symbol variants."""
    from datasheet_studio.infrastructure.pdf.reader import PdfReader

    window = MainWindow()
    try:
        window._pdf_info = PdfReader().open(
            "example/STM32G030K8T6-STMicroelectronics.pdf"
        )
        result = window._execute_ai_tool("get_packages", {})

        assert result["count"] == 4
        assert [p["package"] for p in result["packages"]] == [
            "SO8N",
            "TSSOP20",
            "LQFP32",
            "LQFP48",
        ]
        assert result["packages"][-1]["pin_count"] == 48
    finally:
        window.close()


def test_symbol_creator_dialog_scan_and_export_csv(qapp_instance, tmp_path):
    """Symbol Creator: scanning lists the packages, selecting one fills the
    pin table, and Export CSV writes the expected file."""
    import csv
    import os
    import unittest.mock as mock

    from PySide6.QtWidgets import QFileDialog

    from datasheet_studio.infrastructure.pdf.reader import PdfReader
    from datasheet_studio.ui.symbol_creator import SymbolCreatorDialog

    reader = PdfReader()
    info = reader.open("example/STM32G030K8T6-STMicroelectronics.pdf")
    window = MainWindow()
    out_path = ""
    try:
        dialog = SymbolCreatorDialog(window, reader, info.path)

        assert dialog._package_list.count() == 4

        # Select LQFP48 (index 3: SO8N, TSSOP20, LQFP32, LQFP48).
        dialog._package_list.setCurrentRow(3)
        assert dialog._pin_table.rowCount() == 48
        assert dialog._pin_table.item(0, 1).text() != ""

        out_path = str(tmp_path / "LQFP48.csv")
        with mock.patch.object(
            QFileDialog,
            "getSaveFileName",
            return_value=(out_path, "CSV Files (*.csv)"),
        ):
            dialog._export_csv()

        assert os.path.isfile(out_path)
        with open(out_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == [
            "Pin Number",
            "Pin Name",
            "Pin Type",
            "Alternate Functions",
            "Additional Functions",
        ]
        assert len(rows) == 49  # header + 48 pins
        dialog.close()
    finally:
        window.close()
        if os.path.exists(out_path):
            os.remove(out_path)


def test_symbol_creator_requires_review_for_ambiguous_package(qapp_instance):
    """A merged PDF table must not be silently exported as a bad symbol."""
    from datasheet_studio.infrastructure.pdf.reader import PdfReader
    from datasheet_studio.ui.symbol_creator import SymbolCreatorDialog

    reader = PdfReader()
    info = reader.open("example/STM32G030K8T6-STMicroelectronics.pdf")
    window = MainWindow()
    try:
        dialog = SymbolCreatorDialog(window, reader, info.path)

        # SO8N's PDF table is merged by the PDF engine, producing duplicate
        # physical pin numbers. It remains visible for correction, but export
        # is deliberately blocked instead of making an invalid 20-pin symbol.
        dialog._package_list.setCurrentRow(0)
        assert dialog._pin_table.rowCount() == 20
        assert dialog._export_button.isEnabled() is False
        assert dialog._export_diptrace_button.isEnabled() is False
        assert "review required" in dialog._status_label.text().lower()
        dialog.close()
    finally:
        window.close()


def test_symbol_creator_dialog_exports_diptrace_elixml(qapp_instance, tmp_path):
    """Symbol Creator: Export DipTrace Symbol writes an .elixml component
    library that parses and contains all the selected package's pins."""
    import os
    import unittest.mock as mock
    import xml.etree.ElementTree as ET

    from PySide6.QtWidgets import QFileDialog

    from datasheet_studio.infrastructure.pdf.reader import PdfReader
    from datasheet_studio.ui.symbol_creator import SymbolCreatorDialog

    reader = PdfReader()
    info = reader.open("example/STM32G030K8T6-STMicroelectronics.pdf")
    window = MainWindow()
    out_path = ""
    try:
        dialog = SymbolCreatorDialog(window, reader, info.path, info.title)
        assert dialog._export_diptrace_button.isEnabled() is False

        # Select LQFP48 (index 3: SO8N, TSSOP20, LQFP32, LQFP48).
        dialog._package_list.setCurrentRow(3)
        assert dialog._pin_table.rowCount() == 48
        assert dialog._export_diptrace_button.isEnabled() is True

        out_path = str(tmp_path / "STM32G030_LQFP48.elixml")
        with mock.patch.object(
            QFileDialog,
            "getSaveFileName",
            return_value=(out_path, "DipTrace Component Library (*.elixml)"),
        ):
            dialog._export_diptrace()

        assert os.path.isfile(out_path)
        with open(out_path, encoding="utf-8") as fh:
            xml_text = fh.read()
        assert xml_text.startswith('<?xml version="1.0" encoding="UTF-8"?>')

        root = ET.fromstring(xml_text)
        assert root.attrib["Type"] == "DipTrace-ComponentLibrary"
        assert root.attrib["Name"] == "STM32G030K8T6 LQFP48"
        pins = root.findall(".//Pins/Pin")
        assert len(pins) == 48
        assert [p.get("Id") for p in pins] == [str(i) for i in range(48)]
        assert [p.findtext("PadNumber") for p in pins] == [
            str(i) for i in range(1, 49)
        ]
        dialog.close()
    finally:
        window.close()
        if os.path.exists(out_path):
            os.remove(out_path)


def test_execute_ai_tool_adds_pages_to_selection(qapp_instance):
    from datasheet_studio.models.pdf_document import PdfDocumentInfo

    window = MainWindow()
    try:
        window._pdf_info = PdfDocumentInfo(path="sample.pdf", page_count=10)

        result = window._execute_ai_tool(
            "add_pages_to_selection", {"page_numbers": [2, 5, 5, 99]}
        )
        assert result["added"] == [2, 5]
        assert sorted(window._selected_pages) == [2, 5]

        # duplicate call adds nothing new
        result = window._execute_ai_tool(
            "add_pages_to_selection", {"page_numbers": [2]}
        )
        assert result["added"] == []

        # bookmarks of a fake document with no bookmarks
        assert window._execute_ai_tool("get_bookmarks", {}) == {"bookmarks": []}
    finally:
        window.close()
