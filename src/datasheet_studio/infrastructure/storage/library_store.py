"""Storage for the local datasheet library.

The library is a self-contained folder that can be copied or moved
anywhere: its identity and index live in a ``library.json`` manifest at
the folder root and every stored path is **library-relative**, so the
index keeps working after the folder moves.

Only this module reads and writes the manifest, keeping the storage
schema in one place.
"""

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from datasheet_studio.models.library_item import LibraryItem, LibraryItemKind

LOG = logging.getLogger("datasheet_studio.infrastructure.storage")

MANIFEST_FILENAME = "library.json"
LIBRARY_SCHEMA_VERSION = 1

# Default mapping from item kind to its sub-folder name. Stored in the
# manifest so old libraries keep working if the mapping ever changes.
DEFAULT_CATEGORIES = {
    LibraryItemKind.DATASHEET.value: "datasheets",
    LibraryItemKind.SOFTWARE.value: "software",
    LibraryItemKind.APPLICATION_NOTE.value: "application_notes",
    "summary": "summaries",
}

UNSORTED_FOLDER = "Unsorted"


class LibraryError(Exception):
    """Base error for all library storage failures."""


class InvalidLibraryError(LibraryError):
    """The folder does not contain a valid library manifest."""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_filename(name: str) -> str:
    """Sanitize a string so it can be used as a file/folder name on Windows."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "untitled"


def _unique_destination(dest: Path) -> Path:
    """Return ``dest`` or a suffixed variant that does not exist yet."""
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    for i in range(1, 1000):
        candidate = dest.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
    raise LibraryError(f"Could not find a unique destination for {dest}")


class LibraryStore:
    """Read/write access to one library folder on disk."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        if not self.is_library_folder(self._root):
            raise InvalidLibraryError(
                f"Not a library folder (missing {MANIFEST_FILENAME}): {self._root}"
            )
        self._manifest_path = self._root / MANIFEST_FILENAME
        self._manifest = self._load_manifest()
        self._items: list[LibraryItem] = [
            self._deserialize_item(item_data)
            for item_data in self._manifest.get("items", [])
        ]

    @classmethod
    def create(cls, root: str | Path, name: str | None = None) -> "LibraryStore":
        """Create a new library folder (with manifest) and return a store."""
        folder = Path(root)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LibraryError(f"Could not create library folder {folder}: {exc}") from exc

        manifest_path = folder / MANIFEST_FILENAME
        if manifest_path.exists():
            raise LibraryError(f"A library already exists at {folder}")

        manifest = {
            "schema_version": LIBRARY_SCHEMA_VERSION,
            "library_id": str(__import__("uuid").uuid4()),
            "name": name or folder.name,
            "created_at": _now_iso(),
            "categories": {k: v for k, v in DEFAULT_CATEGORIES.items()},
            "items": [],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Create kind folders eagerly only for active kinds.
        cls._ensure_folder(folder / DEFAULT_CATEGORIES[LibraryItemKind.DATASHEET.value])
        cls._ensure_folder(folder / DEFAULT_CATEGORIES["summary"])
        return cls(folder)

    @staticmethod
    def is_library_folder(path: str | Path) -> bool:
        """True when ``path`` is a folder containing a valid manifest."""
        folder = Path(path)
        if not folder.is_dir():
            return False
        manifest = folder / MANIFEST_FILENAME
        if not manifest.is_file():
            return False
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return False
        return data.get("schema_version") == LIBRARY_SCHEMA_VERSION

    @staticmethod
    def _ensure_folder(path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - defensive
            raise LibraryError(f"Could not create folder {path}: {exc}") from exc


    @property
    def root(self) -> Path:
        return self._root

    @property
    def name(self) -> str:
        return str(self._manifest.get("name", self._root.name))

    @property
    def items(self) -> list[LibraryItem]:
        return list(self._items)

    @property
    def item_count(self) -> int:
        return len(self._items)

    def category_folder(self, kind: LibraryItemKind) -> str:
        """Sub-folder name for a given item kind (from the manifest)."""
        categories = self._manifest.get("categories") or {}
        return str(categories.get(kind.value, DEFAULT_CATEGORIES[kind.value]))

    def get_item(self, item_id: str) -> LibraryItem | None:
        for item in self._items:
            if item.item_id == item_id:
                return item
        return None

    def item_path(self, item: LibraryItem) -> Path:
        """Absolute path of an item's stored file."""
        return self._root / item.relative_path

    def item_exists(self, item: LibraryItem) -> bool:
        return self.item_path(item).is_file()

    def manufacturer_folders(self, kind: LibraryItemKind) -> list[str]:
        """List existing manufacturer folders under the kind root."""
        base = self._root / self.category_folder(kind)
        if not base.is_dir():
            return []

    def add_item_from_source(
        self,
        source_path: str | Path,
        *,
        kind: LibraryItemKind = LibraryItemKind.DATASHEET,
        manufacturer_folder: str,
        manufacturer: str,
        title: str = "",
        part_number: str = "",
        page_count: int = 0,
        tags: list[str] | None = None,
        summary_text: str = "",
    ) -> LibraryItem:
        """Copy ``source_path`` into the library and register it.

        ``manufacturer_folder`` may be a brand-new name; the folder is
        created automatically. Returns the registered item.
        """
        source = Path(source_path)
        if not source.is_file():
            raise LibraryError(f"Source file not found: {source}")

        folder_name = _safe_filename(manufacturer_folder or UNSORTED_FOLDER)
        kind_root = self._root / self.category_folder(kind)
        target_dir = kind_root / folder_name
        self._ensure_folder(target_dir)

        dest = _unique_destination(target_dir / source.name)
        try:
            shutil.copy2(source, dest)
        except OSError as exc:
            raise LibraryError(f"Could not copy {source} to {dest}: {exc}") from exc

        item = LibraryItem(
            kind=kind,
            relative_path=dest.relative_to(self._root).as_posix(),
            title=title or source.stem,
            part_number=part_number,
            manufacturer=manufacturer or folder_name,
            manufacturer_folder=folder_name,
            page_count=page_count,
            added_at=_now_iso(),
            tags=list(tags or []),
            summary_text=summary_text,
            source_path=str(source),
        )
        self._items.append(item)
        self._save_manifest()
        LOG.info("Added to library: %s -> %s", source, item.relative_path)
        return item

    def remove_item(self, item_id: str, *, delete_file: bool = True) -> None:
        """Remove a record from the index and (by default) its stored file."""
        item = self.get_item(item_id)
        if item is None:
            raise LibraryError(f"Item not found in library: {item_id}")

        self._items = [i for i in self._items if i.item_id != item_id]

        if delete_file:
            try:
                path = self.item_path(item)
                if path.exists():
                    path.unlink()
            except OSError as exc:  # pragma: no cover - defensive
                LOG.warning(
                    "Could not delete library file %s: %s", item.relative_path, exc
                )

        if item.summary_file:
            try:
                summary_path = self._root / item.summary_file
                if summary_path.exists():
                    summary_path.unlink()
            except OSError:  # pragma: no cover - defensive
                pass

        self._save_manifest()
        LOG.info("Removed from library: %s (%s)", item.title, item_id)

    def move_item(self, item_id: str, new_folder: str) -> LibraryItem:
        """Move an item's file into another manufacturer folder (keep record)."""
        item = self.get_item(item_id)
        if item is None:
            raise LibraryError(f"Item not found in library: {item_id}")

        current = self.item_path(item)
        if not current.is_file():
            raise LibraryError(f"Stored file is missing: {current}")

        folder_name = _safe_filename(new_folder or UNSORTED_FOLDER)
        kind_root = self._root / self.category_folder(item.kind)
        target_dir = kind_root / folder_name
        self._ensure_folder(target_dir)

        dest = _unique_destination(target_dir / current.name)
        try:
            shutil.move(str(current), str(dest))
        except OSError as exc:
            raise LibraryError(f"Could not move {current} to {dest}: {exc}") from exc

        item.relative_path = dest.relative_to(self._root).as_posix()
        item.manufacturer_folder = folder_name
        item.manufacturer = item.manufacturer or folder_name
        self._save_manifest()
        LOG.info("Moved library item %s -> %s", item_id, dest)
        return item

    def save_summary(self, item_id: str, text: str) -> Path:
        """Write a Markdown summary for an item and link it in the manifest.

        Returns the absolute path of the written summary file.
        """
        item = self.get_item(item_id)
        if item is None:
            raise LibraryError(f"Item not found in library: {item_id}")

        categories = self._manifest.get("categories") or {}
        summaries_root = self._root / str(categories.get("summary", "summaries"))
        folder = summaries_root / _safe_filename(
            item.manufacturer_folder or UNSORTED_FOLDER
        )
        self._ensure_folder(folder)

        slug = _safe_filename(item.part_number or item.title or item.item_id)
        dest = _unique_destination(folder / f"{slug}.md")
        dest.write_text(text, encoding="utf-8")

        # Remove the previous summary file if it exists and differs.
        if item.summary_file and item.summary_file != dest.relative_to(self._root).as_posix():
            try:
                old = self._root / item.summary_file
                if old.exists():
                    old.unlink()
            except OSError:  # pragma: no cover - defensive
                pass

        item.summary_file = dest.relative_to(self._root).as_posix()
        item.summary_text = text
        self._save_manifest()
        LOG.info("Saved summary for %s -> %s", item_id, item.summary_file)
        return dest

    def reindex(self) -> tuple[int, list[LibraryItem]]:
        """Scan the kind folders and register PDFs that are not yet indexed.

        Returns ``(added_count, new_items)``. Folders are treated as
        manufacturer groups, so a library copied without its manifest (or
        with an outdated one) is re-discovered from the folder layout.
        """
        known = {
            self.item_path(item).resolve()
            for item in self._items
            if item.relative_path
        }
        new_items: list[LibraryItem] = []

        for kind in (
            LibraryItemKind.DATASHEET,
            LibraryItemKind.SOFTWARE,
            LibraryItemKind.APPLICATION_NOTE,
        ):
            kind_root = self._root / self.category_folder(kind)
            if not kind_root.is_dir():
                continue
            for pdf_path in sorted(kind_root.rglob("*.pdf")):
                if pdf_path.resolve() in known:
                    continue
                folder_name = (
                    pdf_path.parent.name
                    if pdf_path.parent != kind_root
                    else UNSORTED_FOLDER
                )
                item = LibraryItem(
                    kind=kind,
                    relative_path=pdf_path.relative_to(self._root).as_posix(),
                    title=pdf_path.stem,
                    manufacturer=folder_name,
                    manufacturer_folder=folder_name,
                    added_at=_now_iso(),
                )
                self._items.append(item)
                new_items.append(item)

        if new_items:
            self._save_manifest()
            LOG.info("Reindexed library: %d new items", len(new_items))
        return len(new_items), new_items

    def search(self, query: str, limit: int = 200) -> list[LibraryItem]:
        """Return items matching ``query`` ordered by a simple token score.

        No external search dependency is required: tokens are matched as
        exact / prefix / substring against the fields users search for.
        """
        query = (query or "").strip().lower()
        if not query:
            return self._items[:limit]

        query_tokens = re.findall(r"[a-z0-9]+", query)
        if not query_tokens:
            return []

        scored: list[tuple[int, LibraryItem]] = []
        for item in self._items:
            haystacks = [
                item.title,
                item.part_number,
                item.manufacturer,
                item.manufacturer_folder,
                item.relative_path,
                item.summary_text,
                " ".join(item.tags),
            ]
            blob = " ".join(haystacks).lower()
            tokens = set(re.findall(r"[a-z0-9]+", blob))

            score = 0
            for token in query_tokens:
                if token in tokens:
                    score += 3
                elif any(t.startswith(token) for t in tokens):
                    score += 2
                elif token in blob:
                    score += 1
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda pair: (-pair[0], pair[1].title.lower()))
        return [item for _, item in scored[:limit]]

    def _save_manifest(self) -> None:
        data = {
            "schema_version": LIBRARY_SCHEMA_VERSION,
            "library_id": self._manifest.get("library_id", ""),
            "name": self._manifest.get("name", self._root.name),
            "created_at": self._manifest.get("created_at", _now_iso()),
            "categories": self._manifest.get("categories")
            or {k: v for k, v in DEFAULT_CATEGORIES.items()},
            "items": [self._serialize_item(item) for item in self._items],
        }
        try:
            self._manifest_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            raise LibraryError(
                f"Could not write manifest {self._manifest_path}: {exc}"
            ) from exc

    def _load_manifest(self) -> dict:
        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise InvalidLibraryError(
                f"Corrupted library manifest: {self._manifest_path}"
            ) from exc
        if data.get("schema_version") != LIBRARY_SCHEMA_VERSION:
            raise InvalidLibraryError(
                f"Unsupported library schema version: {data.get('schema_version')}"
            )
        return data

    @staticmethod
    def _serialize_item(item: LibraryItem) -> dict:
        return {
            "item_id": item.item_id,
            "kind": item.kind.value,
            "relative_path": item.relative_path,
            "title": item.title,
            "part_number": item.part_number,
            "manufacturer": item.manufacturer,
            "manufacturer_folder": item.manufacturer_folder,
            "page_count": item.page_count,
            "added_at": item.added_at,
            "tags": list(item.tags),
            "summary_file": item.summary_file,
            "summary_text": item.summary_text,
            "source_path": item.source_path,
        }

    @staticmethod
    def _deserialize_item(data: dict) -> LibraryItem:
        try:
            kind = LibraryItemKind(
                str(data.get("kind", LibraryItemKind.DATASHEET.value))
            )
        except ValueError:
            kind = LibraryItemKind.DATASHEET
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return LibraryItem(
            item_id=str(data.get("item_id", "")),
            kind=kind,
            relative_path=str(data.get("relative_path", "")),
            title=str(data.get("title", "")),
            part_number=str(data.get("part_number", "")),
            manufacturer=str(data.get("manufacturer", "")),
            manufacturer_folder=str(data.get("manufacturer_folder", "")),
            page_count=int(data.get("page_count", 0) or 0),
            added_at=str(data.get("added_at", "")),
            tags=[str(t) for t in tags],
            summary_file=(
                str(data["summary_file"]) if data.get("summary_file") else None
            ),
            summary_text=str(data.get("summary_text", "")),
            source_path=str(data.get("source_path", "")),
        )

