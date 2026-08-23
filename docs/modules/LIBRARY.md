# Datasheet Studio — Local Datasheet Library Module

## 1. Module Identity

- **Module name:** Local Datasheet Library
- **Development stage:** Module 7 (ROADMAP)
- **Primary layers:** `services/`, `infrastructure/storage`, `ui/`, `models/`
- **Status:** Working (initial implementation)

---

## 2. Purpose

Provide an internal library (the "datasheet bank") for organizing,
searching and reopening datasheets.

The library is a **self-contained folder** that can be copied or moved
anywhere on disk. Its identity and index live in a `library.json`
manifest at the folder root, and every stored path is library-relative,
so the index keeps working after the folder is copied to another machine
or location.

---

## 3. User-Facing Behavior

1. The user opens a library folder (or creates a new one) from the
   **Library** menu or the **Library** tab of the left panel.
2. PDFs are stored under `datasheets/<manufacturer>/...` — the
   manufacturer is detected automatically (metadata → filename →
   first-page text) or chosen/typed by the user in the *Add to Library*
   dialog, which also offers the existing manufacturer folders.
3. Items are grouped in the Library tree by document kind
   (Datasheet today) and then by manufacturer folder.
4. A fast search box filters items instantly by title, part number,
   manufacturer, tags and summary text.
5. Double-click opens a stored PDF; a right-click menu offers Open,
   Open Summary, Move to Folder, Reveal in Explorer and Remove.
6. AI summaries can be saved into `summaries/<manufacturer>/...` and are
   linked to the item.
7. The **Search Datasheets Online…** menu opens a small embedded browser
   for finding and temporarily downloading datasheets; downloaded PDFs
   can be added to the library from the dialog.

---

## 4. Folder Layout

```text
MyLibrary/
├── library.json                 # manifest: identity, categories, items
├── datasheets/                  # kind root (from manifest categories)
│   ├── STMicroelectronics/
│   │   └── STM32G431zzzz-Datasheet.pdf
│   ├── Texas Instruments/
│   └── Unsorted/
├── software/                    # future kind (created on demand)
├── application_notes/           # future kind (created on demand)
├── summaries/                   # Markdown summaries
│   └── STMicroelectronics/
│       └── STM32G431.md
└── _downloads/                  # temporary browser downloads (not indexed)
```

The manifest `categories` maps each item kind to its folder name, so new
document types can be added later without breaking old libraries.

---

## 5. Key Components

| Component | File | Responsibility |
|---|---|---|
| `LibraryItem`, `LibraryItemKind` | `models/library_item.py` | Domain records with library-relative paths; extensible kinds (datasheet / software / application_note) |
| `LibraryStore` | `infrastructure/storage/library_store.py` | The only module that reads/writes the manifest; create/open, add, remove, move, save_summary, reindex, search |
| `ManufacturerDetector` | `services/manufacturer_detector.py` | Pure-string vendor detection (metadata → filename → first-page text) and part-number extraction |
| `LibraryService` | `services/library_service.py` | Use-cases coordinating the store, detector and PDF reader |
| `LibraryPanel` | `ui/library_panel.py` | Left-panel tree, search box, toolbar, context menu |
| `AddToLibraryDialog` | `ui/dialogs/add_to_library_dialog.py` | Editable manufacturer/folder combo + kind + tags |
| `DatasheetBrowserDialog` | `ui/dialogs/datasheet_browser.py` | Embedded browser, temp downloads, graceful fallback to the system browser |

---

## 6. Manifest Schema (v1)

```json
{
  "schema_version": 1,
  "library_id": "<uuid>",
  "name": "MyLibrary",
  "created_at": "ISO-8601",
  "categories": {
    "datasheet": "datasheets",
    "software": "software",
    "application_note": "application_notes",
    "summary": "summaries"
  },
  "items": [
    {
      "item_id": "<uuid>",
      "kind": "datasheet",
      "relative_path": "datasheets/STMicroelectronics/STM32G431zzzz-Datasheet.pdf",
      "title": "STM32G431 Datasheet",
      "part_number": "STM32G431",
      "manufacturer": "STMicroelectronics",
      "manufacturer_folder": "STMicroelectronics",
      "page_count": 240,
      "added_at": "ISO-8601",
      "tags": ["MCU", "ARM"],
      "summary_file": "summaries/STMicroelectronics/STM32G431.md",
      "summary_text": "...",
      "source_path": "C:\\original\\location.pdf"
    }
  ]
}
```

---

## 7. Search

Search is dependency-free and instant for typical library sizes. Tokens
are matched as exact / prefix / substring against the title, part
number, manufacturer, manufacturer folder, relative path, tags and
summary text. Results are ranked by score.

---

## 8. Extensibility

- `LibraryItemKind` already contains `software` and `application_note`
  values. Enabling a new kind only requires: a value in the enum (done),
  an entry in `DEFAULT_CATEGORIES` (already present) and UI grouping
  (the tree already groups by kind).
- The manifest stores the `categories` mapping, so old libraries remain
  readable if folder names ever change.
- `reindex()` rebuilds the index from the folder layout on disk, so a
  library whose manifest was lost/copied partially is re-discovered from
  its manufacturer folders.

---

## 9. Safety Rules

- The library folder and `library.json` are user data and must never be
  committed to Git (see `.gitignore`).
- If a stored file is missing, the item is shown grayed out and opening
  it shows a clear warning; the library never crashes.
- If the embedded browser is unavailable, the dialog falls back to the
  system browser. Browsing is user-driven only; no scraping (ADR-012).
- The core PDF viewer works even when no library is open.
