"""Domain models for the local datasheet library.

The library is a self-contained folder that can be copied or moved
anywhere on disk. Every stored item keeps a *library-relative* path so
the index (``library.json``) stays valid after the folder is moved.

The model is intentionally extensible: ``LibraryItemKind`` already
carries ``software`` and ``application_note`` values so those document
types can be added later without changing the manifest schema.
"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class LibraryItemKind(str, Enum):
    """Document kinds a library entry can hold.

    Only ``DATASHEET`` is active today; the other values exist so the
    storage schema does not have to change when Software or Application
    Note support is added.
    """

    DATASHEET = "datasheet"
    SOFTWARE = "software"
    APPLICATION_NOTE = "application_note"


@dataclass
class LibraryItem:
    """A single document registered in the library index."""

    item_id: str = field(default_factory=lambda: str(uuid4()))
    kind: LibraryItemKind = LibraryItemKind.DATASHEET
    relative_path: str = ""  # library-relative path, e.g. datasheets/STMicro/xyz.pdf
    title: str = ""
    part_number: str = ""
    manufacturer: str = ""  # detected display name (may differ from the folder)
    manufacturer_folder: str = ""  # physical sub-folder under the kind root
    page_count: int = 0
    added_at: str = ""  # ISO-8601 timestamp
    tags: list[str] = field(default_factory=list)
    summary_file: str | None = None  # library-relative path to the summary .md
    summary_text: str = ""  # cached plain text used for fast search
    source_path: str = ""  # where the file was added from (informational)

    def absolute_path(self, library_root: str) -> str:
        """Resolve this item's physical location relative to the library root."""
        import os

        return os.path.join(library_root, self.relative_path)
