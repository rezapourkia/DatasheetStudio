"""Unit tests for right-click-drag panning in NoteOverlayWidget."""

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QScrollArea, QWidget

from datasheet_studio.ui.widgets.note_overlay import NoteOverlayWidget


def _make_mouse_event(event_type, pos, button):
    return QMouseEvent(
        event_type,
        QPointF(pos),
        QPointF(pos),  # scenePos
        QPointF(pos),  # globalPos
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )


def _build_scroll_area_with_content() -> QScrollArea:
    scroll_area = QScrollArea()
    content = QWidget()
    content.setFixedSize(2000, 2000)
    scroll_area.setWidget(content)
    scroll_area.resize(400, 400)
    scroll_area.horizontalScrollBar().setRange(0, 1600)
    scroll_area.verticalScrollBar().setRange(0, 1600)
    scroll_area.horizontalScrollBar().setValue(800)
    scroll_area.verticalScrollBar().setValue(800)
    return scroll_area


def test_right_click_drag_pans_scroll_area(qapp_instance):
    scroll_area = _build_scroll_area_with_content()
    overlay = NoteOverlayWidget()
    overlay.set_scroll_area(scroll_area)

    start_h = scroll_area.horizontalScrollBar().value()
    start_v = scroll_area.verticalScrollBar().value()

    press = _make_mouse_event(
        QEvent.Type.MouseButtonPress, QPoint(100, 100), Qt.MouseButton.RightButton
    )
    overlay.mousePressEvent(press)
    assert overlay._panning is True

    move = _make_mouse_event(
        QEvent.Type.MouseMove, QPoint(60, 70), Qt.MouseButton.RightButton
    )
    overlay.mouseMoveEvent(move)

    # Dragging left/up should scroll the view right/down (content follows the hand).
    assert scroll_area.horizontalScrollBar().value() == start_h + 40
    assert scroll_area.verticalScrollBar().value() == start_v + 30
    assert overlay._pan_moved is True

    release = _make_mouse_event(
        QEvent.Type.MouseButtonRelease, QPoint(60, 70), Qt.MouseButton.RightButton
    )
    overlay.mouseReleaseEvent(release)
    assert overlay._panning is False


def test_small_right_click_without_drag_does_not_mark_pan_moved(qapp_instance):
    scroll_area = _build_scroll_area_with_content()
    overlay = NoteOverlayWidget()
    overlay.set_scroll_area(scroll_area)

    press = _make_mouse_event(
        QEvent.Type.MouseButtonPress, QPoint(100, 100), Qt.MouseButton.RightButton
    )
    overlay.mousePressEvent(press)

    # Tiny move below the threshold: should not count as a pan drag.
    move = _make_mouse_event(
        QEvent.Type.MouseMove, QPoint(101, 101), Qt.MouseButton.RightButton
    )
    overlay.mouseMoveEvent(move)
    assert overlay._pan_moved is False

    release = _make_mouse_event(
        QEvent.Type.MouseButtonRelease, QPoint(101, 101), Qt.MouseButton.RightButton
    )
    overlay.mouseReleaseEvent(release)
    assert overlay._panning is False
