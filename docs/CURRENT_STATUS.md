# Datasheet Studio — Current Project Status

**Last updated:** 2026-09-15
**Project status:** Desktop PDF/library/AI workspace, Flyback Designer v1, knowledge-base v2 foundation, and Phase-5 local/mock bottom search are implemented
**Current branch:** `feature/datasheet-to-design-v2`
**Primary development environment:** Windows + VS Code + Python virtual environment

> The authoritative newest implementation record is section 19. Earlier
> module-baseline paragraphs are retained as project history and may describe
> the state before the later feature passes recorded in sections 11 and 13–19.

---

## 1. Project Summary

Datasheet Studio is a desktop application for electronics engineers and hardware designers.

Its long-term purpose is to provide a focused workspace for:

- Opening and reading component datasheets in PDF format
- Viewing PDF pages with zoom and scrolling
- Navigating datasheet bookmarks and sections
- Selecting important pages from datasheets
- Writing notes related to datasheets and pages
- Maintaining a local datasheet library organized by type and manufacturer
- Searching component and datasheet sources online
- Using configurable AI providers to analyze, summarize, and search datasheet content
- Supporting future engineering tools such as symbol extraction, package identification, and DipTrace export

The application is designed to be modular, maintainable, visually clear, and efficient with minimal unnecessary clicks.

---

## 2. Current Development Stage

The project has completed:

1. Foundation / Documentation
2. Application Shell (Module 1)

The **PDF Document Service (Module 2)** is in progress: a PyMuPDF-backed reader
opens PDFs, reads metadata/bookmarks, and renders pages. The main window's
**File → Open Datasheet...** action is functional.

AI workflow, local library, online search, and the remaining PDF-viewer
interactions are not implemented yet.

---

## 3. Environment Status

| Item | Current Value |
|---|---|
| Operating system | Windows |
| Development editor | Visual Studio Code |
| Terminal | VS Code integrated terminal |
| Python version | Python 3.13.3 |
| Virtual environment | `.venv` |
| UI framework | PySide6 6.11.1 |
| PDF library | PyMuPDF 1.28.2 |
| Test framework | pytest |
| Source-control system | Git |
| Main Git branch | `main` |
| Project directory | `~/DatasheetStudio` |
| Packaging | `pyproject.toml` (src layout, editable install) |

---

## 4. Completed Work

### 4.1 Environment Setup

- [x] Git repository initialized
- [x] Main branch configured as `main`
- [x] Python virtual environment created as `.venv`
- [x] Python 3.13.3 confirmed
- [x] PySide6 installed
- [x] PyMuPDF installed
- [x] Initial GUI test completed successfully
- [x] `.gitignore` created and extended for packaging/test artifacts

### 4.2 Foundation / Documentation (Module 0)

- [x] `docs/PROJECT_OVERVIEW.md` created and reconciled
- [x] `docs/ARCHITECTURE.md` rewritten (short layer names, four-panel layout, tools layer)
- [x] `docs/ROADMAP.md` rewritten (11 modules, updated status)
- [x] `docs/ENVIRONMENT_SETUP.md` corrected (startup command + editable install)
- [x] `docs/DEVELOPMENT_WORKFLOW.md` created
- [x] `docs/CURRENT_STATUS.md` created
- [x] `docs/DECISIONS.md` rewritten (15 ADRs, clean formatting)
- [x] `docs/modules/APP_SHELL.md` created and updated to Complete
- [x] Architecture and dependency rules defined
- [x] Module roadmap defined
- [x] Development, testing, documentation, and Git workflow defined

### 4.3 Application Shell (Module 1)

- [x] `src/datasheet_studio/app.py` uses shared constants
- [x] `src/datasheet_studio/ui/main_window.py` implements the four-panel layout
- [x] `src/datasheet_studio/core/constants.py` added (shared layer)
- [x] `pyproject.toml` added (packaging + pytest config)
- [x] Editable install performed (`pip install -e .`)
- [x] Menu bar (File, View, Tools, Help), status bar, About dialog
- [x] Left panel with Library/Bookmarks sub-tabs
- [x] AI panel with Chat/Summary/Report sub-tabs
- [x] Automated unit tests passing
- [x] Headless launch and event-loop run verified

### 4.4 PDF Document Service (Module 2, in progress)

- [x] `src/datasheet_studio/models/pdf_document.py` (domain models: `PdfDocumentInfo`, `Bookmark`)
- [x] `src/datasheet_studio/infrastructure/pdf/reader.py` (PyMuPDF adapter isolated)
  - Open PDFs and read metadata, page count, and bookmarks
  - Validate non-PDF files (explicit `is_pdf` check)
  - Render pages as PNG bytes
- [x] Functional **File → Open Datasheet...** (file dialog + bookmarks tree + render page 1 + zoom)
- [x] PDF reader unit tests passing (`tests/unit/test_pdf_reader.py`)

---

## 5. Current Source-Code Status

```text
src/datasheet_studio/
├── __init__.py
├── app.py                  # application entry point
├── core/
│   ├── __init__.py
│   └── constants.py        # shared constants
├── models/
│   ├── __init__.py
│   └── pdf_document.py     # PdfDocumentInfo, Bookmark
├── services/
│   └── __init__.py         # (empty, future application layer)
├── infrastructure/
│   ├── __init__.py
│   └── pdf/
│       ├── __init__.py
│       └── reader.py       # PyMuPDF adapter (open, render)
└── ui/
    ├── __init__.py
    └── main_window.py      # four-panel shell + Open + bookmarks + render
```

Done:

- Application Shell layout
- Main window module structure
- Menu bar (File, View, Tools, Help) + Exit + About
- Open Datasheet... (file dialog, bookmarks, render page 1)
- PDF metadata, page count, bookmark extraction
- Single-page rendering + zoom in/out
- Non-PDF validation

Not yet implemented:

- Multi-page view and page navigation
- Selected-pages workflow (placeholder only)
- Double-click to select / remove pages
- Notes and annotations
- Local datasheet library and database storage
- Online component search
- AI provider setup and secure API-key storage
- AI requests, summaries, or reports
- Tools framework (dynamic Tools menu reserved)
- DipTrace export

---

## 6. Active Module

The next coding module is:

```text
Module 2 — PDF Document Service
```

Its scope: open a PDF safely and expose metadata, page count, bookmarks (with page ranges), and text extraction, isolated in `infrastructure/pdf`. See `docs/ROADMAP.md` §6.

A `docs/modules/PDF_SERVICE.md` specification should be created before coding, following the established module workflow in `docs/DEVELOPMENT_WORKFLOW.md`.

---

## 7. Immediate Next Actions

In order:

1. Commit the Foundation + Application Shell + PDF Document Service work (see §8).
2. Create `docs/modules/PDF_SERVICE.md` to record the completed scope and acceptance criteria.
3. Continue Module 2: add text extraction and bookmark page-range derivation.
4. Then proceed to Module 3 (PDF Viewer): multi-page view, navigation.
5. Update `docs/CURRENT_STATUS.md`, `docs/ROADMAP.md`, and the module doc.

---

## 8. Pending Commit Guidance

The current uncommitted changes cover:

- Rewritten/updated documentation (Foundation + Application Shell)
- New source: `core/constants.py`, refined `app.py` and `ui/main_window.py`
- New `pyproject.toml`
- New tests (`tests/conftest.py`, `tests/unit/test_application_shell.py`)
- Updated `.gitignore`

Suggested focused commits:

1. `docs: reconcile architecture, roadmap, decisions, and application shell`
2. `feat: implement application shell layout`
3. `test: add application shell smoke tests`
4. `chore: add packaging config and ignore artifacts`

Before committing, verify no secrets, `.venv`, `*.egg-info`, `.pytest_cache`, or user data are staged.

---

## 9. Current Risks and Open Questions

### Known Risks

- The application will grow into a multi-feature desktop tool; module boundaries must remain clear to prevent `main_window.py` from becoming too large.
- PDF rendering performance and memory use must be evaluated when real document support is implemented.
- AI provider APIs and key-management methods may differ; provider-specific details must remain isolated in Infrastructure.
- Online component websites may have changing access rules, API limitations, rate limits, or scraping restrictions.
- User data, API keys, notes, downloaded files, and local databases must never be accidentally committed to Git.

### Open Questions (deferred to future modules)

- Which local database technology should be used for the datasheet library?
- What secure local mechanism should store AI provider API keys on Windows?
- Which AI providers should be supported first?
- What retrieval/chunking strategy should be used for AI search (RAG)?
- Which component websites have official APIs suitable for integration?
- What exact data format should be used for annotations and notes?
- What export formats are required for DipTrace integration?
- Which UI style, icon set, and visual theme should be adopted?

These questions do not block the PDF Document Service module.

---

## 10. Verification Status

| Verification Item | Status |
|---|---|
| Python environment created | Verified |
| PySide6 installation | Verified |
| PyMuPDF installation | Verified |
| Basic PySide6 GUI launch | Verified |
| Launch command `python -m datasheet_studio.app` | Verified |
| Editable package install (`pip install -e .`) | Verified |
| Application Shell — four panels + menus | Verified (headless) |
| Application Shell unit tests | 6 passing |
| PDF opening | Working (single file) |
| PDF rendering | Working (page 1 + zoom) |
| Bookmark extraction | Working |
| Non-PDF validation | Working |
| PDF reader unit tests | 5 passing |
| Selected pages | Working (add/remove/range, save as PDF, compress/load `.dssel`) |
| AI provider integration | Working (real API calls; DeepSeek/OpenAI/Custom tool calls; Anthropic/Gemini chat-only) |
| Local data storage | Not started |

---

## 11. Bug-Fix Pass — 2026-08-14

A review/fix pass was performed against the current implementation (which had
grown beyond the Application Shell scope). The following issues were fixed:

- **Selected Pages → Save** now creates a real PDF by copying the selected pages
  with PyMuPDF instead of calling the selection-archive service. A missing
  `.pdf` extension is appended automatically.
- **Compress** now writes the compressed selection archive (`.dssel`) via
  `SelectionStorage`, and **Load Selection** restores it. Duplicate
  `_load_selection` definitions were removed.
- **Fit, Page Range, Add to Selected, and Manage Notes** controls are now
  enabled consistently when a document is opened — including from the
  **Recent Files** menu — via the shared `_activate_document_ui()` helper.
- Opening a new document clears the previous document's notes and selection.
- **Save Notes to PDF** no longer fails. The previous `doc.save(path)`
  raised `ValueError: save to original must be incremental`, and incremental
  saving is not reliable in PyMuPDF 1.28.2; the PDF is now saved to a
  temporary file and atomically replaced. The incorrect
  `annot.set_info(author=...)` call was replaced with `title=` (the correct
  markup-annotation field).
- **Manage Notes** dialog body was stranded inside `_generate_ai_report`
  (which caused a `NameError` and a non-functional dialog). The dialog now
  opens and edit/delete work; an undefined variable in the edit-refresh loop
  was fixed.
- AI settings are now fully restored from `QSettings` (provider, protocol,
  base URL, model, API key, quality).
- The AI Chat, Summary, and Report panels were wired up (history display, send
  button, output panes, generate buttons) so they match the mock AI service.
- **AI Chat crash fixed:** `_send_ai_message` contained a stray fragment of the
  old `_load_ai_settings` code that referenced undefined `base_url`/`quality`
  variables and raised `NameError` on every message. The fragment was removed;
  chat, summary, and report now complete (mock responses).
- **Notes in exported PDF:** `PdfReader.save_selected_pages(...)` was added so
  notes attached to selected pages are copied into the exported PDF as text
  annotations. `_save_selection` now uses this service method (also removing
  direct PyMuPDF usage from the UI), and `add_notes_to_pdf` shares the same
  annotation helper.
- **Temporary debug log panel:** a new `core/logging.py` buffers all events in
  memory (max 2000 entries, never written to disk). Uncaught exceptions are
  logged via a custom `sys.excepthook`. The menu action **Help -> Debug Log...**
  opens a dialog with the full log and a **Copy All** button so issues can be
  pasted back for support.
- **Real AI integration (replaces mock):** `services/ai_service.py` now calls
  real HTTP APIs for DeepSeek, OpenAI, Anthropic, Google Gemini, and custom
  OpenAI-compatible / Anthropic endpoints (stdlib `urllib` only, no new
  dependency). **Test Connection** actually verifies credentials,
  **Fetch Models** lists models from custom endpoints, and Chat / Summary /
  Report send the selected pages' extracted text as context
  (`PdfReader.get_page_text` + `_build_ai_context`). Errors surface as clear
  messages and are written to the debug log.
- **AI tool/function calls:** the AI can now act on the application, not just
  reply with text. `AIService.chat()` supports the OpenAI-compatible
  `tools`/`tool_calls` protocol (DeepSeek, OpenAI, Custom), and the app exposes
  four tools: `get_bookmarks`, `add_pages_to_selection`, `navigate_to_page`,
  and `get_page_text`. Tool calls run on the GUI thread via a
  `_AiToolBridge` (so widgets are never touched from the worker thread) and
  results are fed back to the model in a loop until it answers. The AI context
  now also includes the document outline (bookmarks + page numbers), so the
  model can map sections (e.g. "3.29 USART") to actual pages and add them to
  Selected Pages.
- **Styled chat UI:** the AI chat panel was redesigned like Claude/DeepSeek —
  message bubbles (user right / AI left), full Markdown rendering (headings,
  lists, tables, code blocks, links) via the built-in `ui/markdown_render.py`
  (no new dependency), a **💾 Save .md** button that exports the whole chat to
  Markdown, a **🔁 Retry** button that re-sends the last question, a **🗑 Clear**
  button, and a live status indicator that shows `⏳ Thinking...` with an
  elapsed-seconds counter until the reply arrives (or `⚠ Error`).

Verification:

- `pytest`: 38 tests passing (SelectionStorage, PDF notes/export/text, AI
  request building/error handling/tool loop with mocked network, AI chat
  regression, AI tool execution, Markdown renderer).
- Offscreen smoke tests: PDF export, `.dssel` round trip, debug-log capture,
  AI test-connection and chat with mocked network, end-to-end tool-call flow
  (`get_bookmarks` -> `add_pages_to_selection` -> final reply), chat bubbles,
  `.md` chat export, and retry — all passed.

### 11.1 Bug Fixes: AI Chat Send Button + PDF Right-Click-Drag Panning

- **Send button not working:** `self._ai_send_button.clicked.connect(self._send_ai_message)`
  connected the button directly to a slot whose first parameter is
  `force_message: str | None = None`. Qt's `QPushButton.clicked` signal emits
  a `checked: bool` argument, so PySide6 passed `False` into `force_message`.
  Since `False is not None`, the code proceeded to call `False.strip()`,
  raising an `AttributeError` that Qt swallows silently in the slot — so the
  button visibly did nothing. Fixed by connecting through a lambda:
  `self._ai_send_button.clicked.connect(lambda: self._send_ai_message())`,
  which drops the `checked` argument. A regression test
  (`test_send_button_click_does_not_raise`) calls `.click()` on the real
  button (not the slot directly) with a mocked HTTP response and asserts an
  assistant reply is appended to `_ai_chat_messages`; it was verified to fail
  with the old direct connection and pass with the fix.
- **No right-click-drag panning in the PDF viewer:** `NoteOverlayWidget` sits
  on top of the rendered page and captured all mouse events, but only
  implemented left-click note selection/drag/resize and a right-click
  context menu — there was no way to pan a zoomed-in page by dragging.
  Added `NoteOverlayWidget.set_scroll_area(scroll_area)` plus pan-tracking
  state (`_panning`, `_pan_moved`, `_pan_start_pos`,
  `_pan_start_h_value`/`_pan_start_v_value`, a 4px move threshold).
  `mousePressEvent` now starts a pan on a right-button press (switches to
  `ClosedHandCursor`, snapshots the scrollbar values); `mouseMoveEvent`
  updates the horizontal/vertical scrollbars directly from the drag delta
  and sets `_pan_moved` once the drag exceeds the threshold;
  `mouseReleaseEvent` ends the pan and restores the cursor; and
  `contextMenuEvent` now checks `_pan_moved` first and, if the right-click
  was actually a drag, suppresses the Edit/Delete note menu instead of
  popping it up. `main_window.py` wires this up once with
  `self._note_overlay.set_scroll_area(self._scroll_area)`. Covered by new
  tests in `tests/unit/test_note_overlay_pan.py`
  (`test_right_click_drag_pans_scroll_area`,
  `test_small_right_click_without_drag_does_not_mark_pan_moved`).
- **Selected Pages Save produced no file:** the "💾 Save" button in the
  Selected Pages panel opened the save dialog but no PDF appeared on disk.
  The export chain itself was verified working (real PDF + real button click
  offscreen), which pointed to the UI flow: the dialog opened with an empty
  default filename, so submitting it without typing a name hit the
  `if not path: return` guard and silently returned — no file, no message.
  Fixes: `_save_selection` now passes `self._build_default_selection_name()`
  (document title or file stem + selected page range, sanitized, e.g.
  `STM32G030_1-5.pdf`) as the dialog's default name, adds a guard for a
  missing document, and logs any exception with a full traceback to the
  in-memory debug log (`Help -> Debug Log...`) in addition to the "Save
  Failed" box. `PdfReader.open()` now normalizes the document path to
  absolute (`os.path.abspath`), so exporting never depends on the process's
  current directory. Regression coverage in `tests/unit/test_application_shell.py`:
  `test_save_selection_button_click_creates_pdf` (clicks the real button and
  asserts the output file exists and is non-empty) and
  `test_save_selection_default_name`.

Verification: full `pytest` run — **43 tests passing** (38 previous + 3 earlier
in this session + 2 new).

### 11.2 AI Pinout Extraction Tool (get_pinout)

Problem observed: asking the AI chat for a pinout table (e.g. "extract a table
of LQFP48 pin names with all their alternate functions") produced only a short
reply after the model fetched 14 pages one by one. Root cause: the only page
tool was `get_page_text`, which returns raw `page.get_text()` output; for
multi-column tables (the ST pin-definition table has pin-number columns for
nine packages interleaved with AF columns) that text is jumbled beyond recovery,
so the model could never reconstruct the table.

Fixes:

- **`PdfReader.get_pinout(package)`** (infrastructure layer): locates the
  "pin definition" section from the TOC, extracts the table with PyMuPDF's
  `page.find_tables()`, remembers the package/pin-name/type/AF column positions
  from the header page and reuses them on continuation pages (so the multi-page
  table is merged), validates each row (numeric pin number + ST pin-name
  pattern) so unrelated tables on nearby pages are never picked up, and joins
  the result with the "alternate functions" table (AF0..AF15 per pin) by pin
  name. Verified on `STM32G431zzzz-Datasheet.pdf`: exactly 48 LQFP48 pins
  numbered 1–48 with no gaps or duplicates, each with `AFn=function` mappings
  (e.g. pin 26 / PB12 → `AF4=I2C2 SMBA, AF5=SPI2 NSS/I2S2 WS, AF6=TIM1 BKIN,
  AF7=USART3 CK, AF8=LPUART1 RTS DE, AF15=EVENT OUT`). Falls back to the plain
  AF column when the alternate-function table is missing.
- **New AI tool `get_pinout`** in `_ai_tools_schema()` / `_execute_ai_tool()`
  (main_window.py): the model asks for one package name and receives the full
  clean pinout in a single tool call. The `get_page_text` tool description now
  points the model at `get_pinout` for pin/package/AF questions.
- **`max_tokens: 4096`** added to the OpenAI-compatible payload
  (ai_service.py) so long table answers are not truncated by the provider's
  default output limit.

Tests added (`tests/unit/test_pdf_reader.py`,
`tests/unit/test_application_shell.py`):
`test_get_pinout_lqfp48_returns_all_pins` (48 rows, pins 1–48, PB12 AFs),
`test_get_pinout_unknown_package_returns_empty`, `test_ai_tool_get_pinout`.

Verification: full `pytest` run — **46 tests passing** (43 previous + 3 new).

### 11.3 Chat Response Invisible + Zoomed-Page Panning

**AI reply not visible in the chat (and chat not "DeepSeek-like"):** the
assistant bubble rendered each reply through a plain `QTextBrowser` with
`SizeAdjustPolicy.AdjustToContents`. Because `setHtml()` runs before the widget
has any width, the document laid out at 0x0 and `AdjustToContents` never
re-computed, so every assistant bubble collapsed to a tiny height and long
replies (e.g. a 48-row pinout table) were clipped out of view.

- Added `_AutoHeightTextBrowser` (a `QTextBrowser` subclass implementing
  `hasHeightForWidth()`/`heightForWidth()`, which lays the document out with
  the real width and returns the true content height). Assistant bubbles now
  expand to fit their full content and the outer chat scroll area scrolls the
  whole message.
- Redesigned `_ChatMessageWidget` to look like DeepSeek/Claude: a small role
  label ("You" / "Assistant") above each bubble, user bubble blue on the
  right, assistant bubble light gray with a subtle border on the left, rounded
  corners, and nicer spacing.
- Improved `markdown_render.py` output: dark rounded code blocks, styled
  inline code, tables with a header background, styled headings, blockquotes,
  and paragraphs.
- Regression test `test_ai_chat_assistant_bubble_expands_to_content` verifies
  a long reply's `QTextBrowser` document/bubble height exceeds 400 px.

**Cannot move (pan) the page when zoomed in the document viewer:** root cause
was in `_render_page` — the viewer `QLabel` was never resized to the rendered
page, and `setWidgetResizable(True)` kept it pinned to the viewport size, so a
zoomed page was clipped and the scrollbars had a 0..0 range (nothing to scroll,
and no scrollbars for the right-click-drag panning to drive).

- `_render_page` now calls `setMinimumSize(pixmap.size())` + `resize(...)` on
  the viewer label, so zoomed pages grow, scrollbars appear, the existing
  right-click-drag panning (in `NoteOverlayWidget`) actually moves the page,
  and plain wheel scrolling works too.
- Regression test `test_viewer_label_resizes_to_page_when_zoomed` verifies the
  label matches the pixmap size and both scrollbar ranges are > 0 at zoom 4.

Verification: full `pytest` run — **48 tests passing** (46 previous + 2 new).

### 11.4 Compress Button Now Saves a Compressed PDF

Previously the Selected Pages **🗜️ Compress** button wrote a `.dssel` archive
(compressed ZIP of the selection) — not a PDF — and the compression-level combo
(Fast / Normal / Best) was unused. The user asked for "when I compress, a PDF
should be saved".

- `PdfReader.save_selected_pages()` gained a `compression` parameter
  (`"none"` / `"fast"` / `"normal"` / `"best"`) mapped to PyMuPDF `save()`
  options: `fast` → `garbage=1` + deflate; `normal` → `garbage=3` +
  deflate images/fonts; `best` → `garbage=4` + `clean=True` + deflate. On the
  STM32G431 datasheet "best" produced a 32% smaller PDF (188 KB vs 276 KB).
- `_compress_selection` now shows the save dialog pre-filled with the same
  default name as Save, filters to `*.pdf`, uses the compression-level combo,
  and logs any failure to the debug log.
- Tests: `test_save_selected_pages_with_compression` (best < plain, valid
  PDF) and `test_compress_selection_button_creates_pdf` (real button click
  produces a PDF). `.dssel` load remains available via **File → Load
  Selection** for previously exported archives.

Verification: full `pytest` run — **50 tests passing** (48 previous + 2 new).

### 11.5 Save Dialog Opens in the Datasheet's Folder

The Selected Pages **💾 Save** (and **🗜️ Compress**) dialogs opened with only a
default filename and no directory, so the native dialog landed in the OS
"last used" folder (e.g. Documents) while users expected the file next to the
datasheet — the PDF was created, but effectively "no file where I looked".

- Added `_get_save_default_path()`: the dialogs now pre-fill the open
  datasheet's folder + a default name, so the output PDF is written where the
  user is already looking. Both `_save_selection` and `_compress_selection`
  use it.
- The "Save Failed" box now points the user to **Help → Debug Log** for the
  full traceback.
- Regression test `test_save_dialog_defaults_to_datasheet_folder` verifies the
  dialog's default path is in the datasheet's folder and ends with `.pdf`.

Verification: full `pytest` run — **51 tests passing** (50 previous + 1 new).

### 11.6 Tools → Symbol Creator

New **Tools → Symbol Creator...** feature: opens a separate window that
identifies the packages (schematic symbol variants) of the open datasheet,
lets the user pick one, previews its full pinout table, and exports it as CSV
(for Excel or KiCad symbol work).

- **Reader layer:** `PdfReader.get_all_pinouts()` extracts every package's
  pinout in a single scan (refactor of the old one-package extraction), and
  `get_available_packages()` returns the package list with pin counts. Pin
  counts prefer the number encoded in the package name (SO8N=8, TSSOP20=20,
  LQFP48=48...) because some datasheet tables (e.g. STM32G030) visually merge
  the SO8N/TSSOP20 columns; the count falls back to distinct extracted pins.
  Ball-grid packages (WLCSP, UFBGA) with alphanumeric ball IDs (A1, B7) are
  now accepted too. The pin-definition section lookup tolerates differing TOC
  titles ("pin definition" / "pin assignment" / "pin description") and the AF
  column header may be truncated ("Alternate\nfunc").
- **UI:** `ui/symbol_creator.py` — `SymbolCreatorDialog` with a package list,
  a pinout table (Pin/Name/Type/AF/Additional), Scan and **Export CSV**
  buttons. The scan runs once (`get_all_pinouts`) and package selection is
  instant. The Tools menu item replaced the reserved "No tools available"
  placeholder.
- **AI chat tool:** new `get_packages` tool so the model can answer "which
  packages does this IC have?" with a structured list (SO8N 8, TSSOP20 20,
  LQFP32 32, LQFP48 48 for STM32G030).

Tests: `test_get_available_packages_lists_symbol_variants`,
`test_ai_tool_get_packages`, `test_symbol_creator_dialog_scan_and_export_csv`.

Verification: full `pytest` run — **54 tests passing** (51 previous + 3 new).

### 11.7 Save Flow Hardened (No Silent Failures)

The Selected Pages **💾 Save** / **🗜️ Compress** flow was reworked so a "save
dialog opens but no file" situation can no longer happen silently:

- `_ask_save_path()` now uses a **`QFileDialog` instance** (instead of the
  static `getSaveFileName`) with `setDefaultSuffix("pdf")`, and distinguishes
  three outcomes: **ok** (a non-empty path was chosen), **canceled** (user
  closed the dialog — shown in the status bar), and **empty** (dialog accepted
  with no filename — a visible "No Filename" warning box). Previously an empty
  path returned silently with no message and no file.
- On success, `_show_save_success()` shows the full path **and an
  "📂 Open Folder" button** that opens the containing folder in Windows
  Explorer (`_reveal_in_explorer`), so the saved PDF is impossible to lose
  track of.
- Every step is logged to the in-memory debug log (default path, accepted
  path, page count, result/failure) — **Help → Debug Log** always shows what
  happened.
- Tests updated for the instance-based dialog and a new
  `test_save_dialog_accepted_with_empty_path_shows_warning` verifies the
  empty-filename case is never silent.

Verification: full `pytest` run — **55 tests passing** (54 previous + 1 new).

### 11.8 Tools → Symbol Creator: DipTrace Symbol Export

The Symbol Creator can now turn *any* opened datasheet's extracted pinout into
a **DipTrace Component Editor library (`.elixml`)** — a ready-to-open schematic
symbol — in addition to the existing CSV export.

- **New service:** `services/diptrace_export.py` (pure, Qt-free) with
  `build_component_library(pin_rows, component_name=..., package=...)` that
  builds a complete DipTrace 5.x component-library XML per the verified
  conventions in `docs/diptrace/` (root `Library Type="DipTrace-ComponentLibrary"`,
  `Component` → `Part` → `Pins`/`Shapes`).
  - Symbol layout: `Free`-template IC box, pins split left/right
    (first half top→bottom on the left at `Orientation="0"`, second half
    bottom→top on the right at `Orientation="180"`), 100 mil pitch, 100 mil pin
    length, Name/Value text shapes, and a body width calculated from the
    longest labels on both sides.
    *Correction (2026-08-15):* DipTrace draws a pin's stub **in the direction
    of `Orientation` from the pin point**, so left pins point right (`"0"`)
    and right pins point left (`"180"`) — the stub then reaches the body
    instead of floating outside it. `Y` is positive-up in DipTrace symbol
    coordinates ("Schematic Y is commonly negative downward"), so pin 1 is the
    top-left pin.
  - Pin names are shortened to their base name for on-symbol display
    (`short_pin_name`: `PC14- OSC32 IN` -> `PC14`, `PB8-BOOT0` -> `PB8`) so
    long datasheet names cannot overflow the symbol; pin-name font is 4 and
    part Name/Value text is font 5. Pin names are shifted into the rectangle
    and pin numbers out beyond the free connection tip, matching the clean
    layout of a native DipTrace two-sided IC symbol. The body widens on the
    50-mil grid when both label columns need more central clearance.
  - Dense pin `Id`s (0..N-1, position == Id), `PadNumber` = the datasheet pin
    number (numeric or alphanumeric ball IDs such as `A1`/`B7`).
  - ERC `ElectricType` heuristic: power pins (VDD/VSS/AVDD/GND/… variants) →
    `Power`, reset pins → `Input`, everything else `Undefined`.
  - XML-escapes pin names, generates a stable `UID32`, and emits no physical
    footprint (a pattern must be attached inside DipTrace afterwards, because a
    pinout table does not describe land-pattern geometry).
  - `extract_part_number()` names the component from the PDF file name / title
    (STM32G030K8T6, MAX17201, BQ25798…; rejects words like "Maximum").
- **UI:** `ui/symbol_creator.py` gets an **Export DipTrace Symbol (.elixml)...**
  button next to Export CSV. It derives the component name, suggests
  `{Component}_{Package}.elixml` in the datasheet folder, writes the library,
  and reports success/failure via the status label, debug log and error box.
  `main_window.py` passes the document title and the Tools-menu status tip
  mentions the `.elixml` export.
- **Smoke test:** the generated `example/STM32G030K8T6_LQFP48.elixml` and
  `example/STM32G431_LQFP48.elixml` were launched in the locally installed
  DipTrace 5.3.0.3 CompEdit (process stayed alive — no hard crash on import).
  A visual GUI check in CompEdit is still recommended.

- **Ground-truth capture tooling:** `docs/diptrace/captures/` holds a
  C# capture plug-in (`XmlCapture.cs`, `settings.compedit.capture.xml`) plus a
  small `probe.elixml`. The compiled `XmlCapture.exe` and `settings.xml` are
  installed under `C:\Program Files\DipTrace\Plugins\CompEdit\XmlCapture\`;
  running **Tools → Plugins → Capture Component XML** in CompEdit writes the
  real DipTrace 5.3.0.3 component serialization to
  `docs/diptrace/captures/plugin_capture.xml` (verify the generated XML against
  it before release).

Tests: `tests/unit/test_diptrace_export.py` (pure generator tests:
heuristics, escaping, dense Ids, odd pin counts, real LQFP48 pinout) and
`test_symbol_creator_dialog_exports_diptrace_elixml` (dialog export writes a
parseable 48-pin `.elixml`).

Verification: full `pytest` run — **62 tests passing** (55 previous + 7 new).

### 11.9 Pin Extraction Generalised (non-ST Datasheets)

Until now the pin-table scan was STM32-specific: it required a TOC section
named "pin definition"/"pin assignment", a header containing "pin name", ST
pin-name patterns (`PA0`, `VDD`, `NRST`) and numeric/ball pin numbers. Any
other vendor's datasheet (TI, Maxim, …) returned no packages — e.g. the
**BQ25798** battery charger was unrecognised even though it is a complete
121-page datasheet with a clean `PIN/NAME/NO./TYPE/DESCRIPTION` table.

- **Generic fallback extractor:** `PdfReader._extract_pinout_generic()`
  runs when the STM32-style scan yields nothing. It:
  - works **without a PDF TOC** (scans the first 40 pages, reusing the shared
    per-page table cache);
  - detects pin-table headers by keyword roles, including merged two-row
    headers (`PIN` spanning `NAME`/`NO.`), and single-row styles
    (`Pin | Name | Function`);
  - accepts plain integers, **range numbers** (`2-3`), and alphanumeric ball
    IDs (`A1`, `P3`);
  - merges continuation pages and de-duplicates rows;
  - names the package from page text near the family token (`VQFN (29)` →
    `VQFN29`; section headings like "5 Pin Configuration" are not misread),
    falling back to `{count}P`.
- **Speed:** the STM32-style scan now aborts after 10 pages when the document
  has no matching TOC section, so the generic detector can run immediately.
- **Helpful failure messages:** `PdfReader.extraction_hint()` distinguishes
  "this file is an incomplete excerpt (only N pages)" from "no pin table
  found", and the Symbol Creator shows that hint instead of a bare
  "No packages found". (`MAX17201`/`MAX17320` files in the repo are only
  1–2 page excerpts — they contain no pin tables by design.)
- **Verified on:** `BQ25798…pdf` → package `VQFN29`, 27 pin rows (pins 1–29
  including `VBUS 2-3`), full symbol exported end-to-end.

Tests: `test_get_pinout_generic_ti_style_bq25798`,
`test_extraction_hint_reports_incomplete_file`,
`test_detect_package_prefers_count_near_family`. Existing STM32 pinout tests
still pass unchanged.

Verification: full `pytest` run — **66 tests passing** (63 previous + 3 new).

### 11.10 Symbol Creator: Safe Review Before Export

PDF table detection is inherently vendor- and layout-dependent: a visually
merged table can produce multiple conflicting names for one physical pin, and
one table row can represent multiple tied package pads (for example `2-3`).
Generating a DipTrace library directly from that raw data produced symbols
that could look valid but have the wrong pin count or duplicate pin numbers.

- **Validation gate:** `validate_pin_rows()` in
  `services/diptrace_export.py` now expands numeric ranges/lists into one
  row per physical pin and rejects unsupported numbers, duplicate physical
  pins, empty names, and package-count mismatches.
- **No silent bad exports:** `build_component_library()` applies the same
  validation and raises a clear `Pin table needs review` error instead of
  writing an ambiguous `.elixml`.
- **Review-first UI:** Symbol Creator keeps every discovered package visible.
  Each package is labelled `verified` or `needs review`; its table is now
  editable, with **Add pin** and **Remove selected pin** controls. CSV and
  DipTrace export remain disabled until the reviewed data passes validation.
- **Tied pads:** an entry such as `VBUS | 2-3` is expanded to separate
  physical pins `2` and `3` during DipTrace generation, so a package such as
  VQFN29 is not reduced to a 27-pin symbol merely because two pads share one
  signal name.
- **Regression coverage:** STM32G030 `SO8N` is deliberately detected as
  review-required (the PDF engine returns 20 conflicting rows for its eight
  physical pins) and cannot be exported until corrected. Valid LQFP48
  export remains covered, along with range expansion and duplicate rejection.

The AI chat can still inspect packages and pinouts through `get_packages` and
`get_pinout`; direct AI repair of the editable Symbol Creator table is not
implemented yet. The safety gate ensures an AI result, like any PDF result,
must pass the same validation before it can be exported.

## 12. Handoff Instructions for the Next Development Session

Before beginning work in a future session:

1. Open the project folder in VS Code.
2. Confirm the Python interpreter is the one inside `.venv`.
3. Review Git Source Control and ensure there are no unexpected changes.
4. Read:
   - `docs/CURRENT_STATUS.md`
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_WORKFLOW.md`
   - `docs/ROADMAP.md`
   - The relevant module document in `docs/modules/`
5. Activate the environment and run the application once:
   - `python -m datasheet_studio.app`
6. Inspect the existing source files.
7. Begin only the next module's scope (PDF Document Service).
8. Do not implement viewer, AI, storage, web, or tool functionality during the PDF Document Service module.

---

## 13. Native Tools and Flyback Designer — 2026-09-14

### Environment Recreated After Clone

- Installed Python 3.13.3 x64 for the current Windows user.
- Recreated the ignored `.venv` in the repository.
- Installed the exact runtime dependencies from `pyproject.toml`:
  PySide6 6.11.1 and PyMuPDF 1.28.2.
- Installed pytest 9.1.1 through the `dev` extra.
- Added a `build` extra for the Qt-recommended Nuitka deploy path and a
  maintained `pysidedeploy.spec` file.

### Documentation-First Contracts

- Added `docs/modules/TOOLS_FRAMEWORK.md` before implementing the registry.
- Added `docs/modules/FLYBACK_DESIGNER.md` before implementing the tool.
- Added ADR-017 documenting the explicit native/no-HTML decision.
- Added a root `README.md` and `docs/WINDOWS_BUILD.md`.

### Tools Framework

- Added `Tool`, `ToolContext`, and `ToolRegistry` under
  `src/datasheet_studio/tools/registry.py`.
- The main window now renders categorized tool actions from the registry.
- Duplicate IDs and incomplete metadata are rejected.
- Symbol Creator is now a registered CAD tool rather than a hard-coded action.
- Tool failures are isolated and reported without terminating Datasheet Studio.

### Native Flyback Designer v1

- Added a pure Python DCM engine with explicit-unit dataclasses.
- Added a native PySide6 dialog; no HTML, JavaScript, Qt WebEngine, or runtime
  dependency on the former FLYBACK repository exists.
- The dialog is Persian and right-to-left with editable source/switch, core,
  winding, clamp, feedback, and up-to-eight-output inputs.
- Results cover turns, inductance, currents, wire suggestion, fill, gap, AL,
  reflected voltage, switch stress, RCD estimate, losses, ripple, and TL431 DC
  values.
- Engineering errors and warnings remain visible. All bundled seed data is
  explicitly illustrative and unverified.
- Versioned UTF-8 JSON save/open is implemented with validation before form
  replacement.

### Verification

- Python compile check: passed.
- Flyback engine/registry tests: 25 passed.
- Native Flyback dialog/menu integration checks: passed.
- Full project regression suite: **138 passed in 62.43 seconds**.
  Re-verified in the current checkout on 2026-09-15 (ZCode) during the Phase 1
  baseline pass: compile check passed and full suite **143 passed in 61.99 s**
  (the count grew with test files present in the working tree), plus an
  offscreen startup smoke test with two registered tools.
- Timed Qt event-loop startup smoke test: passed with exit code 0 and two
  registered tools.
- Automated Windows screenshot inspection was attempted but the Computer Use
  approval/window session failed; visual desktop interaction is therefore not
  claimed as verified in this record.

### Next Work

1. Build and launch the official `pyside6-deploy`/Nuitka distribution.
2. Perform manual visual verification on the packaged executable.
3. Add manufacturer-backed editable core/component libraries with per-field
   provenance; do not promote samples to verified data.
4. Add physical winding-layer planning and report export in a later documented
   phase.

---

## 14. Update Rule

This document must be updated whenever:

- A module begins
- A module is completed
- The next planned task changes
- A new significant risk or open question appears
- The development environment changes
- A major technical decision affects project direction
- A significant verification result is obtained

The purpose of this file is to provide an accurate handoff point so work can continue safely in a new chat session or with an AI assistant inside VS Code.

---

## 15. Owner Workflow Realignment — 2026-09-15

The owner clarified the intended daily workflow. The authoritative requirements
are now in `docs/PRODUCT_VISION.md`, with supporting contracts in:

- `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md`
- `docs/modules/AI_ENGINEERING_WORKFLOW.md`
- `docs/modules/ONLINE_DATASHEET_SEARCH.md`
- `docs/modules/FLYBACK_DESIGNER.md`

### Implemented Today

- PDF viewer, selected pages, notes, initial local library, AI chat, tool
  registry, and native Persian RTL Flyback Designer v1.
- A separate online-search browser dialog with manual download-to-library flow.
- A portable v1 library based on `library.json` and manufacturer folders.

### Not Yet Implemented

- Bottom main-window search strip and normalized official-source adapters.
- Content-addressed source vault, SQLite/FTS index, revision/evidence graph, and
  safe v1-to-v2 in-app upgrade.
- Complete-datasheet controller-profile extraction with OCR coverage, strict
  schema, page evidence, and review/lock workflow.
- Automatic handoff of the current datasheet/profile into Flyback Designer.
- Manufacturer-backed core/material/bobbin packs and update UI.
- Arbitrary output count in the domain model, isolation groups, scenario matrix,
  complete per-rail capacitor/rectifier calculations, cross-regulation, and
  explicit optocoupler feedback topology analysis.
- Calculation-aware Flyback chat with archived Markdown prompt/response artifacts.

No current illustrative core/component record has been promoted to verified.
The next implementation phase is Knowledge Base v2, as ordered in
`docs/ROADMAP.md` section 17.

---

## 16. Phase 2 — Knowledge-Base Domain Schema — 2026-09-15

Implemented the Phase 2 slice of the staged plan (see
`docs/DEVELOPMENT_PLAN.md` and the module contract
`docs/modules/KNOWLEDGE_BASE_SCHEMA.md`):

- `src/datasheet_studio/models/knowledge_base.py`: validated, frozen domain
  types — `SourceObject` (content-addressed, duplicate merge rules),
  `DocumentRevision`, `ComponentProfile`, `MagneticsRecord`, `LibraryIdentity`,
  plus `EvidenceField`/`Provenance` carrying source hash, page/table evidence,
  extractor version, import time, confidence, and review state for every
  engineering fact. Review states are enforced: AI/import can assign at most
  `extracted`; `verified` requires reviewer and timestamp. Strict validation
  rejects unknown keys, malformed hashes/dates/paths, bad numeric order, and
  unsafe relative paths. Versioned envelope serialization
  (`dump_record`/`load_record`) rejects unsupported schema versions instead of
  silently converting.
- `src/datasheet_studio/services/knowledge_hash.py`: streaming SHA-256 for
  large PDFs (constant memory), and canonical record hashing for reproducible
  equality across key order and platforms.
- No UI change, no user file moves, no Qt/network dependency in the domain
  module (verified by import scan and test imports).

Example records for the owner review gate (explicitly unverified, placeholder
source hashes): `docs/examples/knowledge_base/DK124_profile_example.md` and
`docs/examples/knowledge_base/EE19_17_core_example.md`; machine fixtures live
in `tests/fixtures/knowledge_base/` and are validated by the test suite.

Verification: `compileall` passed; full regression **187 passed in 63.51 s**
(143 previous + 44 new schema/hash tests).

---

## 17. Phase 3 — Rebuildable SQLite/FTS Index — 2026-09-15

Implemented the Phase 3 slice per `docs/modules/KNOWLEDGE_INDEX.md`
(contract written before code):

- `src/datasheet_studio/infrastructure/storage/knowledge_index.py`: a
  stdlib-only SQLite/FTS5 adapter (`KnowledgeIndex`) over the Phase 2 domain
  records. Separate rowid-aligned FTS tables per record kind (documents,
  components, magnetics, fields, page texts); incremental upsert/remove;
  explicit transactions with rollback; **atomic rebuild** (temp file +
  `os.replace`) that never leaves a half-written index; corruption recovery
  (`KnowledgeIndex.recover`) that deletes a broken file and rebuilds.
- Search grammar: free terms are prefix-AND FTS matches (Persian text works
  via the unicode61 tokenizer), with `maker:`, `type:`, `core:`,
  `material:`, and `verified:` filters. Hits are grouped by kind and carry
  page/field context plus highlighted snippets. Verified tokenizer behavior
  documented: `DK124` is one token, so `dk1` matches but a bare `124` does
  not.
- SQLite remains an index only (ADR-019); durable truth stays in record
  files, proven by the delete-and-rebuild equivalence test.
- Threading rule documented: the adapter is synchronous; the future UI
  (Phase 5 strip, Phase 4 migration) must call it from a worker thread.
  Phase 3 ships no UI.

Verification: full regression **206 passed in 66.20 s** (19 new tests:
lifecycle, unique-key conflicts, transaction rollback, atomic-rebuild
equivalence incl. page/field snippets, corruption recovery from a garbage
file, query grammar incl. Persian free text, and a synthetic 1,500-document /
6,000-field / 3,000-page performance fixture — build ≈ 0.2 s, queries ≤ 4 ms
on the development machine).

---

## 18. Phase 4 — Safe Library v1 → v2 Desktop Upgrade — 2026-09-15

Implemented per `docs/modules/LIBRARY_UPGRADE.md` (contract written first).
This is the first phase with a visible desktop change:

- **Menu:** **Library → Upgrade Library to v2 (Knowledge Base)...** opens the
  Persian RTL `LibraryUpgradeDialog` for the active v1 library.
- **Dialog flow:** preview (item/file/missing counts + bytes to copy),
  cancellable run on a worker `QThread` with a progress bar, itemized report
  (imported / duplicate / ambiguous / skipped / failed with reasons), and
  explicit **final acceptance** (marks the vault accepted in `library.toml`
  and stores `knowledgeBasePath` in QSettings) or **rollback** (deletes the
  v2 vault and clears the setting).
- **Vault writer** (`infrastructure/storage/knowledge_vault.py`): creates the
  v2 layout (`library.toml` via a stdlib TOML writer validated against the
  Phase 2 `LibraryIdentity`, `objects/sha256/<hh>/<hash>.pdf`,
  `records/.../record.md` + `record.json` envelope, `migration/` backup and
  reports) and rebuilds the Phase 3 index.
- **Migration service** (`services/library_migration.py`): per-item import
  with SHA-256 duplicate resolution (one object, per-item records), skipped
  entries for missing/invalid PDFs (PyMuPDF check isolated in
  `infrastructure/pdf`), failure entries on copy errors (migration
  continues), ambiguous entries when part number/manufacturer were absent,
  and abort-with-cleanup semantics for cancellation or unexpected errors.
  The v1 library is never modified — verified byte-for-byte in tests.
- Browsing still happens in the v1 panel during the transition; the v2
  surface arrives with the Phase 5 search strip.

Verification: full regression **227 passed in 64.98 s** (21 new tests: vault
layout/dedup/envelope/TOML/accept/rollback; migration success with v1
byte-identical + searchable index, duplicates, invalid/missing files,
simulated `PermissionError`, cancellation and unexpected-error cleanup,
rollback-after-success, preview counts; dialog preview/report/accept/rollback
offscreen with QSettings cleanup). Compile check and offscreen startup smoke
passed. Not verified: real-worker-thread cancellation inside a visible
desktop session and a migration of the owner's real library (that is the
Phase 4 review gate).

---

## 19. Phase 5 — Bottom Search Strip UX Shell — 2026-09-15

Implemented per `docs/modules/BOTTOM_SEARCH_STRIP.md`, continuing the initial
module contract authored by ZCode:

- A thin Persian RTL search bar now sits below the unchanged four-panel
  splitter and above the status bar. `Ctrl+K` expands it and targets the query
  workflow; collapsing restores the workspace height.
- Source filters cover all, accepted local v2 knowledge vault, and deterministic
  mock-online data. Phase 5 contains no real network request.
- The local provider searches documents, component profiles, magnetics,
  evidence fields, and page text through the Phase-3 SQLite/FTS index. Results
  with a source object resolve the content-addressed PDF and matched page for
  opening in the existing viewer.
- Hint, searching, results, no-results, no-vault, and provider-error states are
  explicit. Searches run in QThreads; generation IDs discard stale responses;
  provider failures remain isolated.
- Copy Link/Path works. Online preview and Save to Library are visible but
  disabled with Phase-6 explanations.
- The deploy manifest includes the new service and widget modules.

Verification: focused Phase-5/index/main-window suite **48 passed**; additional
thread/stale-result focus **28 passed**; full regression **236 passed in
65.12 s**; compile check passed. A visible Windows run confirmed collapsed and
expanded layout, Ctrl+K, RTL order, and that the four-panel workspace remains
usable. Not verified: the owner's real migrated vault, packaged executable,
DPI variants, or any real provider/download/save flow. Phase 5 is at the owner
review gate; Phase 6 must not start without acceptance.
