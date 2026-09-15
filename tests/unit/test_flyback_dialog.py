"""Headless UI checks for the native Flyback Designer integration."""

from PySide6.QtCore import Qt

from datasheet_studio.tools.flyback_designer.defaults import default_project
from datasheet_studio.tools.flyback_designer.dialog import FlybackDesignerDialog
from datasheet_studio.tools.flyback_designer.engine import CoreSpec
from datasheet_studio.ui.main_window import MainWindow


def test_flyback_dialog_opens_rtl_and_renders_default_result(qapp_instance):
    dialog = FlybackDesignerDialog()
    try:
        assert dialog.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert dialog._last_result is not None
        assert dialog._last_result.errors == ()
        assert dialog._last_result.primary_turns == 74
        assert dialog._summary_table.rowCount() > 10
        assert dialog._windings_table.rowCount() == 2
        assert "هشدار" in dialog._warnings.toPlainText()
    finally:
        dialog.close()


def test_flyback_dialog_adds_second_output_and_recalculates(qapp_instance):
    dialog = FlybackDesignerDialog()
    try:
        dialog._add_output()
        dialog.recalculate()

        assert dialog._outputs_table.rowCount() == 2
        assert len(dialog._last_result.outputs) == 2
        assert dialog._last_result.output_power_w == 26.5
        assert dialog._windings_table.rowCount() == 3
    finally:
        dialog.close()


def test_loaded_custom_core_can_be_reselected_without_crashing(qapp_instance):
    dialog = FlybackDesignerDialog()
    try:
        custom = CoreSpec("custom-core", "هسته سفارشی", 31, 44, 52, 48, 1600, 0.19)
        dialog._apply_project(default_project(), custom)
        custom_index = dialog._core_combo.findData(custom.core_id)

        dialog._core_combo.setCurrentIndex(0)
        dialog._core_combo.setCurrentIndex(custom_index)

        assert dialog._fields["ae_mm2"].value() == custom.ae_mm2
        assert dialog._fields["bmax_t"].value() == custom.bmax_t
    finally:
        dialog.close()


def test_main_window_builds_tools_menu_from_registry(qapp_instance):
    window = MainWindow()
    try:
        # Registry order = category alphabetical: CAD, Knowledge Base, Power Design
        assert [tool.id for tool in window._tool_registry.list_tools()] == [
            "symbol-creator",
            "document-text-coverage",
            "flyback-designer",
        ]
        tools_action = next(
            action for action in window.menuBar().actions() if action.text() == "&Tools"
        )
        assert tools_action.menu() is not None
        categories = window._tool_category_menus
        assert set(categories) == {"CAD", "Knowledge Base", "Power Design"}
        assert [action.text() for action in categories["CAD"].actions()] == [
            "Symbol Creator…"
        ]
        assert [action.text() for action in categories["Power Design"].actions()] == [
            "طراح فلای‌بک…"
        ]
    finally:
        window.close()
