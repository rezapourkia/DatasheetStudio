"""Note overlay widget for PDF annotations."""

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PySide6.QtWidgets import QWidget, QMenu
from datasheet_studio.models.pdf_document import PdfNote


class NoteOverlayWidget(QWidget):
    """Overlay widget that displays and manages PDF notes.
    
    All note positions and sizes are stored as relative fractions (0.0-1.0)
    of the overlay dimensions, so they scale correctly with zoom.
    """

    note_selected = Signal(str)  # note_id
    note_double_clicked = Signal(str)  # note_id for editing
    note_dragged = Signal(str, float, float)  # note_id, new_x, new_y
    note_resized = Signal(str, float, float)  # note_id, new_width, new_height
    empty_area_double_clicked = Signal()  # Emitted when double-clicking on empty area

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._notes: dict[str, PdfNote] = {}  # note_id -> PdfNote
        self._selected_note_id: str | None = None
        self._dragging = False
        self._resizing = False
        self._drag_start_pos = None
        self._resize_handle_size = 12
        self.setMouseTracking(True)

        # Right-click-drag panning of the scroll area (used when zoomed in).
        self._scroll_area = None
        self._panning = False
        self._pan_moved = False
        self._pan_start_pos = None
        self._pan_start_h_value = 0
        self._pan_start_v_value = 0
        self._pan_move_threshold = 4  # pixels

    def set_scroll_area(self, scroll_area) -> None:
        """Register the QScrollArea whose scrollbars should be panned
        when the user holds the right mouse button and drags."""
        self._scroll_area = scroll_area

    def set_notes(self, notes: list[PdfNote]) -> None:
        """Set the list of notes to display."""
        self._notes = {note.note_id: note for note in notes}
        self.update()

    def add_note(self, note: PdfNote) -> None:
        """Add a new note."""
        self._notes[note.note_id] = note
        self.update()

    def remove_note(self, note_id: str) -> None:
        """Remove a note by ID."""
        if note_id in self._notes:
            del self._notes[note_id]
            if self._selected_note_id == note_id:
                self._selected_note_id = None
            self.update()

    def get_note(self, note_id: str) -> PdfNote | None:
        """Get a note by ID."""
        return self._notes.get(note_id)

    def get_all_notes(self) -> list[PdfNote]:
        """Get all notes."""
        return list(self._notes.values())

    def clear_selection(self) -> None:
        """Clear the selected note."""
        self._selected_note_id = None
        self.update()

    def _get_note_rect(self, note: PdfNote) -> QRectF:
        """Get the absolute pixel rectangle for a note."""
        x = note.x * self.width()
        y = note.y * self.height()
        width = note.width * self.width()
        height = note.height * self.height()
        return QRectF(x, y, width, height)

    def paintEvent(self, event) -> None:
        """Paint all notes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for note in self._notes.values():
            self._paint_note(painter, note)

        painter.end()

    def _paint_note(self, painter: QPainter, note: PdfNote) -> None:
        """Paint a single note."""
        rect = self._get_note_rect(note)

        # Draw shadow
        shadow_rect = rect.adjusted(2, 2, 2, 2)
        shadow_color = QColor(0, 0, 0, 30)
        painter.setBrush(QBrush(shadow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(shadow_rect, 4, 4)

        # Draw background
        bg_color = QColor(note.background_color)
        bg_color.setAlpha(230)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 4, 4)

        # Draw border
        if note.note_id == self._selected_note_id:
            border_pen = QPen(QColor("#2196F3"), 2)
        else:
            border_pen = QPen(QColor(note.border_color), note.border_width)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)

        # Draw text
        painter.setPen(QColor(note.text_color))
        font = QFont(note.font_family, note.font_size)
        painter.setFont(font)
        
        # Draw text with padding
        text_rect = rect.adjusted(6, 6, -6, -6)
        painter.drawText(text_rect, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop, note.text)

        # Draw resize handle if selected
        if note.note_id == self._selected_note_id:
            handle_size = self._resize_handle_size
            handle_rect = QRectF(
                rect.right() - handle_size,
                rect.bottom() - handle_size,
                handle_size,
                handle_size,
            )
            painter.setBrush(QBrush(QColor("#2196F3")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(handle_rect, 2, 2)

    def _get_note_at_pos(self, pos) -> str | None:
        """Get note ID at position, or None."""
        # Check in reverse order (top-most first)
        for note_id, note in reversed(list(self._notes.items())):
            rect = self._get_note_rect(note)
            if rect.contains(pos):
                return note_id
        return None

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for selection, dragging, and resizing."""
        if event.button() == Qt.MouseButton.RightButton and self._scroll_area is not None:
            self._panning = True
            self._pan_moved = False
            self._pan_start_pos = event.globalPosition()
            self._pan_start_h_value = self._scroll_area.horizontalScrollBar().value()
            self._pan_start_v_value = self._scroll_area.verticalScrollBar().value()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            
            # Check if clicking on resize handle of selected note
            if self._selected_note_id:
                note = self._notes.get(self._selected_note_id)
                if note:
                    rect = self._get_note_rect(note)
                    handle_size = self._resize_handle_size
                    handle_rect = QRectF(
                        rect.right() - handle_size,
                        rect.bottom() - handle_size,
                        handle_size,
                        handle_size,
                    )
                    if handle_rect.contains(pos):
                        self._resizing = True
                        self._drag_start_pos = pos
                        event.accept()
                        return

            # Check if clicking on a note
            clicked_note_id = self._get_note_at_pos(pos)

            if clicked_note_id:
                self._selected_note_id = clicked_note_id
                self._dragging = True
                self._drag_start_pos = pos
                self.note_selected.emit(clicked_note_id)
                self.update()
                event.accept()
            else:
                # Clicked outside - clear selection and let event pass through
                if self._selected_note_id:
                    self._selected_note_id = None
                    self.note_selected.emit("")
                    self.update()
                event.ignore()

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for dragging and resizing."""
        if self._panning and self._pan_start_pos is not None and self._scroll_area is not None:
            pos = event.globalPosition()
            dx = pos.x() - self._pan_start_pos.x()
            dy = pos.y() - self._pan_start_pos.y()
            if abs(dx) > self._pan_move_threshold or abs(dy) > self._pan_move_threshold:
                self._pan_moved = True
            h_bar = self._scroll_area.horizontalScrollBar()
            v_bar = self._scroll_area.verticalScrollBar()
            h_bar.setValue(int(self._pan_start_h_value - dx))
            v_bar.setValue(int(self._pan_start_v_value - dy))
            event.accept()
            return

        if self._dragging and self._selected_note_id and self._drag_start_pos:
            note = self._notes.get(self._selected_note_id)
            if note:
                pos = event.position()
                dx = (pos.x() - self._drag_start_pos.x()) / self.width()
                dy = (pos.y() - self._drag_start_pos.y()) / self.height()
                note.x = max(0, min(1, note.x + dx))
                note.y = max(0, min(1, note.y + dy))
                self._drag_start_pos = pos
                self.update()
                event.accept()

        elif self._resizing and self._selected_note_id and self._drag_start_pos:
            note = self._notes.get(self._selected_note_id)
            if note:
                pos = event.position()
                dx = (pos.x() - self._drag_start_pos.x()) / self.width()
                dy = (pos.y() - self._drag_start_pos.y()) / self.height()
                note.width = max(0.05, min(0.5, note.width + dx))
                note.height = max(0.03, min(0.3, note.height + dy))
                self._drag_start_pos = pos
                self.update()
                event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release to finish dragging/resizing."""
        if event.button() == Qt.MouseButton.RightButton and self._panning:
            self._panning = False
            self._pan_start_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            # Keep self._pan_moved set until contextMenuEvent (fired right
            # after release) has had a chance to check it.
            return

        if self._dragging and self._selected_note_id:
            note = self._notes.get(self._selected_note_id)
            if note:
                self.note_dragged.emit(note.note_id, note.x, note.y)
        
        if self._resizing and self._selected_note_id:
            note = self._notes.get(self._selected_note_id)
            if note:
                self.note_resized.emit(note.note_id, note.width, note.height)

        self._dragging = False
        self._resizing = False
        self._drag_start_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to edit note or pass through."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            clicked_note_id = self._get_note_at_pos(pos)
            
            if clicked_note_id:
                self._selected_note_id = clicked_note_id
                self.note_double_clicked.emit(clicked_note_id)
                event.accept()
            else:
                # Pass double-click through to parent for page navigation
                self.empty_area_double_clicked.emit()
                event.ignore()

    def contextMenuEvent(self, event) -> None:
        """Show context menu for selected note (unless the right-click was
        actually a pan drag)."""
        if self._pan_moved:
            # The right-click was used to pan the view, not to open a menu.
            self._pan_moved = False
            event.accept()
            return

        if self._selected_note_id:
            menu = QMenu(self)
            edit_action = menu.addAction("Edit Note")
            delete_action = menu.addAction("Delete Note")
            
            action = menu.exec(event.globalPos())
            if action == edit_action:
                self.note_double_clicked.emit(self._selected_note_id)
            elif action == delete_action:
                self.remove_note(self._selected_note_id)
