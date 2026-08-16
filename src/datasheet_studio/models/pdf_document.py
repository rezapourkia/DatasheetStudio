"""Domain models for PDF documents."""

from dataclasses import dataclass, field
import uuid


@dataclass
class Bookmark:
    """A single PDF outline/bookmark entry."""

    title: str
    page: int  # 1-based page number
    level: int  # nesting depth (1 = top level)


@dataclass
class PdfDocumentInfo:
    """Basic information about an opened PDF datasheet."""

    path: str
    page_count: int
    title: str = ""
    author: str = ""
    bookmarks: list[Bookmark] = field(default_factory=list)


@dataclass
class PdfNote:
    """A note annotation on a PDF page.

    All spatial values (x, y, width, height) are stored as relative
    fractions (0.0–1.0) of the page dimensions so that notes remain
    correctly positioned regardless of zoom level.
    """

    page_number: int
    text: str
    x: float  # X position (0-1 relative to page width)
    y: float  # Y position (0-1 relative to page height)
    width: float = 0.15  # Width as fraction of page width
    height: float = 0.08  # Height as fraction of page height
    background_color: str = "#FFF9C4"  # Soft yellow
    text_color: str = "#333333"  # Dark gray
    font_size: int = 11
    font_family: str = "Segoe UI"
    border_width: int = 0
    border_color: str = "#E0E0E0"
    note_id: str = field(default_factory=lambda: str(uuid.uuid4()))