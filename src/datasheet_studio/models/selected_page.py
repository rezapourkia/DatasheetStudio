"""Domain model for selected PDF pages with notes."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SelectedPage:
    """Represents a page selected by the user from a PDF document."""

    page_number: int
    document_path: str
    note: str = ""
    selected_at: datetime = field(default_factory=datetime.now)

    @property
    def display_title(self) -> str:
        """Return a display-friendly title for this selected page."""
        return f"Page {self.page_number}"

    def has_note(self) -> bool:
        """Check if this page has a note attached."""
        return bool(self.note.strip())