# Datasheet Studio — Module Roadmap

## 1. Purpose

This document defines the planned development order for Datasheet Studio.

The roadmap exists to prevent unrelated features from being developed too early, to keep each implementation stage focused, and to ensure that every module has clear responsibilities before coding begins.

Each module must be completed, manually verified, documented, and committed to Git before the next module begins.

---

## 2. Development Rules

The following rules apply to every module:

- Work on one main module at a time.
- Do not implement future features inside the current module without a clear need.
- Keep changes small and reviewable.
- Add or update relevant documentation when module behavior changes.
- Add tests for non-UI logic where practical.
- Verify that the application still launches before committing changes.
- Do not commit API keys, local settings, test datasheets, generated files, databases, logs, or virtual environments.
- Use clear Git commit messages.

---

## 3. Module Development Order

| Order | Module | Status | Main Purpose |
|---:|---|---|---|
| 0 | Foundation / Documentation | Complete | Define project scope, architecture, workflow, and roadmap |
| 1 | Application Shell | Complete | Stable main window, four resizable panels, menus, and status bar |
| 2 | PDF Document Service | Working (partial) | Open PDFs and expose metadata, pages, bookmarks, and text |
| 3 | PDF Viewer | Working (partial) | Render and navigate pages with zoom, scroll, single/multi-page |
| 4 | Bookmark Navigation | Working (partial) | Bookmark tree + right-click to send a section's pages to selection |
| 5 | Selected Pages | Working | Add, remove, clear, and range-transfer pages |
| 6 | Notes and Annotations | Working (partial) | Page-level and datasheet-level notes |
| 7 | Local Datasheet Library | In progress | Local datasheet bank, categories by manufacturer, search, summaries, and download folder |
| 8 | AI Assistant | In progress | Provider config, secure key storage, chat/summary/report with RAG |
| 9 | Online Component Search | Planned | Official-API adapters for SnapEDA, Mouser, DigiKey, etc. |
| 10 | Tools Framework + Export | Future | Plugin registry, symbol/package extraction, DipTrace export |

The order may be adjusted only when a documented architectural reason exists.

---

## 4. Module 0 — Foundation / Documentation

### Purpose

Establish a clear, maintainable starting point before feature development begins.

### Included Work

- Project overview
- Architecture definition
- Module roadmap
- Development workflow
- Git and repository rules
- Initial Python environment verification
- Initial PySide6 application launch verification
- Basic source and test folder structure

### Completion Criteria

This module is complete when:

- Core project documents exist and are reviewed.
- The intended architecture is defined.
- The module development order is defined.
- The Python virtual environment is working.
- PySide6 and PyMuPDF are installed.
- The application can launch successfully.
- The repository contains no secrets or environment-specific files.
- The Foundation work is committed to Git.

### Not Included

- PDF rendering
- PDF bookmark extraction
- Selected pages
- Notes
- Local database
- AI provider communication
- Web search
- CAD export

---

## 5. Module 1 — Application Shell

### Purpose

Create a stable PySide6 main window that provides the permanent visual structure of Datasheet Studio.

### Included Work

- Application entry point
- Main window with the four resizable panels in this left-to-right order:
  1. Bookmarks / Library panel
  2. Document viewer (central)
  3. Selected pages panel
  4. AI assistant panel
- Menu bar: File, View, Tools (dynamic), Help
- Status bar
- Bookmark/Library view switch placeholder
- AI sub-tabs: Chat, Summary, Report (placeholders)
- Clean separation between presentation code and application startup code

### Completion Criteria

This module is complete when:

- The application launches without errors.
- The main window has the intended four functional regions visible at once.
- Panels can be resized appropriately.
- Placeholder panels are clearly labeled.
- The menu bar, status bar, and a dynamic (empty) Tools menu are present.
- No PDF processing is implemented inside UI widgets.
- The application can close cleanly.
- Manual launch verification is documented.
- Changes are committed to Git.

### Not Included

- Opening PDF files
- Rendering PDF pages
- AI API configuration
- Persistent settings
- Database access
- Real selected-page behavior
- Real bookmark behavior

---

## 6. Module 2 — PDF Document Service

### Purpose

Create the infrastructure and application services required to open a PDF safely and expose its basic document information.

### Included Work

- PDF file validation
- Open and close PDF documents
- Read document metadata
- Read page count
- Extract document bookmarks or outline when available
- Extract text from pages where needed (basis for search and RAG)
- Safe handling of invalid, encrypted, missing, or damaged files
- Domain models for PDF document information and bookmarks
- Unit tests for non-UI PDF behavior

### Completion Criteria

This module is complete when:

- A valid PDF can be opened through the application layer.
- Page count and metadata are available to the UI.
- Bookmark data can be retrieved when present, including page ranges for each bookmark section.
- Text extraction works for searchable PDFs.
- Errors are represented clearly and do not crash the application.
- PyMuPDF usage remains isolated inside `infrastructure/pdf`.
- Relevant automated tests pass.

### Not Included

- Page rendering in the UI
- Zoom controls
- Selected pages
- Notes
- Library storage

---

## 7. Module 3 — PDF Viewer

### Purpose

Display PDF pages in the application and provide practical page navigation.

### Included Work

- Render PDF pages for display
- Single-page viewing
- Multi-page (grid/thumbnail) viewing
- Page navigation
- Zoom in and zoom out
- Scroll behavior
- Switch between single-page and multi-page modes
- Display current page number and total page count
- Loading and rendering feedback
- Safe handling of rendering errors
- Double-click a page to add it to selected pages (emits a signal; real selection logic arrives in Module 5)

### Completion Criteria

This module is complete when:

- An opened PDF page is visible in the viewer.
- The user can navigate between pages.
- The user can zoom and scroll.
- The user can switch between single-page and multi-page views.
- Double-click on a page emits a page-selection signal.
- Rendering remains responsive for normal datasheets.
- Viewer code does not directly manage library, AI, or storage logic.

### Not Included

- Selected-page persistence (Module 5)
- Notes and annotations (Module 6)
- AI analysis (Module 8)

---

## 8. Module 4 — Bookmark Navigation

### Purpose

Show PDF bookmarks in the left panel and allow navigation and bulk page selection.

### Included Work

- Bookmark tree display
- Nested bookmark hierarchy
- Navigation to a bookmark target page
- Graceful behavior for PDFs without bookmarks
- Right-click on a bookmark → send that section's page range (start..end) to selected pages
- Basic context-menu foundation

### Completion Criteria

This module is complete when:

- PDF bookmarks appear in the left panel when available.
- Clicking a bookmark moves the viewer to the correct page.
- Right-click on a bookmark offers "Select pages in this section".
- The bookmark-to-section page range is computed correctly (including the last bookmark's range).
- PDFs without bookmarks remain usable.
- Bookmark data comes through the application layer, not direct UI-level PyMuPDF calls.

### Not Included

- User-created bookmarks
- Persistent bookmark storage

---

## 9. Module 5 — Selected Pages

### Purpose

Allow users to collect important datasheet pages in a dedicated workspace area.

### Included Work

- Add a page to selected pages (via viewer double-click)
- Add a page range (e.g., 4–18) via a toolbar/input control
- Display selected pages
- Remove one selected page (double-click)
- Remove multiple selected pages (multi-select + delete)
- Clear all selected pages
- Prevent accidental duplicate behavior according to documented rules
- Domain model for selected pages
- Tests for selected-page rules

### Completion Criteria

This module is complete when:

- A user can add and remove pages reliably.
- A user can add a page range.
- The selected-pages panel accurately reflects current selections.
- Clear-all and remove-selected operations work.
- Double-click on a selected page removes it.
- Selected-page business rules are testable without PySide6 widgets.
- The PDF viewer remains functional after selection changes.

### Not Included

- Saving selected pages permanently
- Exporting selected pages
- AI analysis of selected pages

---

## 10. Module 6 — Notes and Annotations

### Purpose

Enable users to create notes and annotations associated with a datasheet or page.

### Included Work

- Page-level notes
- Datasheet-level notes
- Basic annotation model
- Local persistence design
- Create, edit, and delete notes
- Clear ownership rules between document, page, and note
- Tests for note-related domain logic

### Completion Criteria

This module is complete when:

- Notes can be created, edited, saved, reopened, and deleted.
- Notes remain associated with the correct datasheet and page.
- Storage failures are handled safely.
- Note data is separated from the visual editor.

---

## 11. Module 7 — Local Datasheet Library

### Purpose

Provide an internal library (the "datasheet bank") for organizing and reopening datasheets.

### Included Work

- Local library database or storage implementation
- Add datasheet records
- Categories and tags (by type and manufacturer)
- Search and filtering
- Reopen a stored datasheet
- A managed download folder for datasheets
- Basic metadata management
- Safe handling of missing source PDF files

### Completion Criteria

This module is complete when:

- Datasheets can be added to the local library.
- Users can search, filter, categorize, and reopen library entries.
- Users can manage a local datasheet download folder.
- Local databases and downloaded datasheets are excluded from Git.
- The core PDF viewer works even if the library is unavailable.

---

## 12. Module 8 — AI Assistant

### Purpose

Create a safe, provider-independent AI assistant for search, summaries, and reports over datasheet content.

### Included Work

- Provider configuration model
- API key input and secure local storage strategy
- Provider adapter interface
- AI request preparation
- Retrieval over selected pages/text (RAG-style) as context
- Chat (question answering)
- Summaries
- Report generation
- Clear error handling for unavailable providers, invalid keys, or network failures

### Completion Criteria

This module is complete when:

- API keys are never written to Git-tracked files.
- AI provider code is isolated in `infrastructure/ai`.
- The AI panel supports Chat, Summary, and Report sub-tabs.
- The application remains usable without AI configuration.
- Provider-specific behavior does not leak into domain models or general UI code.

### Not Included

- Fully autonomous design analysis
- Automatic symbol generation
- Automatic package extraction
- Online vendor searching unless separately implemented

---

## 13. Module 9 — Online Component Search

### Purpose

Search approved external component sources for datasheets, pricing, availability, symbols, footprints, and 3D models.

### Potential Sources

- SnapEDA
- Component Search Engine
- Ultra Librarian
- Mouser
- DigiKey

### Important Constraints

- Each external provider must use a separate adapter in `infrastructure/web`.
- Prefer official APIs and permitted integrations; no unrestricted scraping.
- Website/API terms of service must be respected.
- API keys and credentials must remain local and untracked.
- Failure of an online source must not affect local PDF reading.

---

## 14. Module 10 — Tools Framework + Export

### Purpose

Provide a plugin registry for future engineering tools and export workflows.

### Included Work

- `tools/registry.py` with a `Tool` contract and `ToolRegistry`
- Dynamic Tools menu populated from the registry
- Tool context contract for accessing application/domain data

### Potential Future Tools

- Export selected pages and notes as a report
- DipTrace-compatible export workflows
- Symbol extraction assistance
- Package identification assistance
- Pin-table extraction
- AI-assisted component analysis
- 3D model discovery

Each future tool requires its own brief design document before implementation.

### Completion Criteria

This module is complete when:

- The Tools menu is built dynamically from the registry.
- A new tool can be added without editing the core UI.
- Tool registry behavior is covered by tests.
- Tools follow layered boundaries and do not reach into UI internals.

---

## 15. Definition of Done for Every Module

A module is considered complete only when all applicable items below are satisfied:

- The module purpose and boundaries are understood.
- The implementation follows the architecture document.
- The application launches successfully.
- Relevant tests pass.
- Manual behavior has been checked.
- Errors are handled safely.
- Documentation has been updated.
- No secrets or local-only files are staged for Git.
- Changes are committed with a clear message.

---

## 16. Current Next Step

The Foundation / Documentation module and Module 1 (Application Shell) are
complete. The PDF Document Service, PDF Viewer, Bookmark Navigation, Selected
Pages, Notes, and a large part of the AI Assistant are implemented and working
(see `docs/CURRENT_STATUS.md` for exact verification).

The active module is:

**Module 8 — AI Assistant**

Remaining AI work:

- Tool/function calls for Anthropic and Google Gemini (OpenAI-compatible
  providers already support them).
- Secure local API-key storage (see ADR-009; the key is currently stored in
  plain `QSettings`).
- Retrieval / RAG over selected pages as richer context.
- Moving the AI HTTP transport into `infrastructure/ai` (see the known
  deviation documented in `docs/ARCHITECTURE.md`).
