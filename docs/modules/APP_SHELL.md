# Datasheet Studio — Application Shell Module

## 1. Module Identity

- **Module name:** Application Shell
- **Development stage:** Module 1 (first implementation module)
- **Primary layer:** Presentation (`ui/`)
- **Related layers:** Shared (`core/`)
- **Status:** Complete

---

## 2. Purpose

The Application Shell establishes the initial runnable desktop interface for Datasheet Studio.

Its purpose is to create a stable PySide6 application startup path and a main window with the primary visual regions required by the future application.

At this stage, the shell provides structure only. It does not implement PDF processing, datasheet-library storage, AI communication, online search, annotations, or selected-page business rules.

---

## 3. User-Facing Behavior

When the user starts the application:

1. A PySide6 application starts successfully.
2. The main window opens with the title **Datasheet Studio**.
3. The window displays a clean initial layout with four resizable panels visible at once.
4. The panels, from left to right, are:
   - Bookmarks / Library
   - Document viewer
   - Selected pages
   - AI assistant
5. The window can be resized without breaking the layout.
6. The menu bar, a dynamic Tools menu, and a status bar are visible.
7. The application can be closed normally.

Placeholder panels must clearly communicate their intended future purpose; they do not need real feature logic yet.

---

## 4. Scope

### 4.1 In Scope

The Application Shell module includes:

- Application startup entry point (`app.py`)
- PySide6 `QApplication` initialization
- Main window creation and display (`ui/main_window.py`)
- Main window title and initial size
- Main layout with four resizable panels
- Placeholder panels for bookmarks/library, PDF viewer, selected pages, and AI assistant
- A switch between **Library** and **Bookmarks** views in the left panel (placeholder)
- AI panel sub-tabs: **Chat**, **Summary**, **Report** (placeholders)
- Menu bar: File, View, Tools (dynamic), Help
- Status bar
- Clean separation between presentation code and application startup code
- A minimal shared-constants module (`core/constants.py`) for the app name, version, title, and default window size

### 4.2 Out of Scope

The following must **not** be implemented in this module:

- Opening or rendering PDF files
- Calling PyMuPDF
- Extracting PDF text, metadata, page count, or bookmarks
- Actual bookmark navigation or bulk selection
- Zoom controls or page scrolling behavior
- Adding or removing selected pages
- Saving notes or annotations
- Local datasheet library or database access
- AI provider configuration
- API key storage
- AI requests, summaries, or reports
- Online component search
- Downloading datasheets
- DipTrace export
- Complex application settings

These functions belong to future dedicated modules.

---

## 5. Planned Layout

The initial window uses a four-panel horizontal split:

```text
+-------------------------------------------------------------------+
| Menu Bar                                                          |
+------------------+------------------+---------------+--------------+
| Bookmarks /      |                  |               |              |
| Library          |  Document Viewer |  Selected     |  AI          |
| (left panel)     |  (central)       |  Pages        |  Assistant   |
|                  |                  |               |              |
+------------------+------------------+---------------+--------------+
| Status Bar                                                        |
+-------------------------------------------------------------------+
```

Recommended initial approach:

- Use `QMainWindow` as the main application window.
- Use a `QSplitter` for the four horizontally resizable panels.
- The document viewer is the widest panel.
- The left panel contains a `QTabWidget` or a toolbar switch with **Library** and **Bookmarks** placeholders.
- The AI panel contains a `QTabWidget` with **Chat**, **Summary**, and **Report** placeholders.
- Use simple labels or placeholder widgets initially.
- Keep widget construction and layout code organized and readable.

Suggested placeholder texts:

| Area | Suggested Placeholder Text |
|---|---|
| Library | Search and manage your local datasheet library here. |
| Bookmarks | Bookmarks and document navigation will appear here. |
| Document viewer | Open a datasheet to view its pages. |
| Selected pages | Selected datasheet pages will appear here. |
| AI Chat | Ask a question about the selected datasheet pages. |
| AI Summary | AI-generated summaries will appear here. |
| AI Report | AI-generated reports will appear here. |

---

## 6. Planned Source-Code Ownership

The Application Shell should initially use only the source files needed for this module.

Expected files:

```text
src/datasheet_studio/
├── __init__.py
├── app.py                  # application startup (already exists)
├── core/
│   ├── __init__.py
│   └── constants.py        # app name, version, title, default size
└── ui/
    ├── __init__.py         # already exists
    └── main_window.py      # main window + panels (already exists; to be refined)
```

Rules:

- `app.py` is responsible for application startup.
- `main_window.py` is responsible for creating and arranging the main window.
- Future PDF, AI, storage, and domain logic must not be placed in `main_window.py`.
- Placeholder widgets must remain simple and must not become a location for business logic.
- New folders must only be created when they are needed by the current implementation.

---

## 7. Responsibilities by Layer

### Presentation (`ui/`)

Responsible for:

- Displaying the main window
- Creating menus, panels, labels, and status bar
- Handling basic user-interface events
- Showing placeholder content
- Preparing extension points for future widgets

Must not directly access PyMuPDF, databases, external APIs, or secure settings.

### Shared (`core/`)

May provide small shared values:

- Application name
- Application version
- Default window title
- Default initial window dimensions

Must not become a location for unrelated application logic.

---

## 8. Interface Design Requirements

The initial interface should follow these principles:

- Keep the layout simple and uncluttered.
- Use understandable labels for placeholder areas.
- Allow the central document-viewer area to receive the most visual space.
- Make side panels resizable.
- Avoid excessive buttons and controls before their functionality exists.
- Do not present non-functional controls as though they are fully implemented.
- Prefer disabled future actions or clearly marked placeholder content.
- Use text that makes the current development state understandable.

---

## 9. Initial Menu Structure

The Application Shell includes a menu bar.

```text
File
  - Open Datasheet...       (disabled or shows "Not implemented yet")
  - Exit                    (works)

View
  - Reset Layout            (optional future placeholder)

Tools                      (dynamic; initially empty, no hardcoded tools)

Help
  - About Datasheet Studio
```

Rules:

- Exit must work.
- About Datasheet Studio displays a small dialog with the application name and development-stage message.
- Open Datasheet... is now functional: it opens a real PDF, populates the bookmarks tree, and renders the first page. Full PDF interaction (multi-page view, navigation, double-click selection) remains in later modules.
- The Tools menu is built from the tool registry. In this module the registry is not yet built, so the Tools menu is reserved and shows a single disabled "No tools available" item.
- Unfinished actions must clearly indicate that they are not yet implemented.

---

## 10. Error Handling Requirements

The shell must handle basic startup problems safely.

At minimum:

- If an unexpected error occurs during startup, the application should not fail silently.
- During development, technical error details may be printed to the console or logged.
- User-facing error messages must be understandable.
- No API keys, user files, local databases, or external services are required by this module.

---

## 11. Acceptance Criteria

The Application Shell module is complete when all of the following are true:

- [x] The application starts through `python -m datasheet_studio.app`.
- [x] A main window titled **Datasheet Studio** is displayed.
- [x] The main window has a sensible initial size.
- [x] The window is resizable.
- [x] A menu bar (File, View, Tools, Help) is visible.
- [x] A status bar is visible.
- [x] The four panels are visible at once, left to right: bookmarks/library, document viewer, selected pages, AI.
- [x] The left panel includes Library and Bookmarks placeholder views.
- [x] The AI panel includes Chat, Summary, and Report placeholder sub-tabs.
- [x] The Tools menu is present (and shows "No tools available").
- [x] The application closes normally.
- [x] The Exit menu action works.
- [x] No PDF processing is implemented.
- [x] No AI, database, web-search, or secret-storage code is implemented.
- [x] The architecture boundaries in `docs/ARCHITECTURE.md` are respected.
- [x] Manual startup and layout verification has been performed.
- [x] `docs/CURRENT_STATUS.md` has been updated after completion.
- [ ] The completed work is committed with a focused Git commit.

---

## 12. Manual Test Checklist

After implementing the Application Shell, verify manually:

- [ ] Activate the virtual environment.
- [ ] Run `python -m datasheet_studio.app`.
- [ ] Confirm that no startup error occurs.
- [ ] Confirm that the main window title is correct.
- [ ] Resize the window smaller and larger.
- [ ] Confirm that the layout remains usable.
- [ ] Confirm that all four panels are visible at once.
- [ ] Confirm the left panel shows Library and Bookmarks placeholders.
- [ ] Confirm the AI panel shows Chat, Summary, and Report sub-tabs.
- [ ] Confirm the menu bar contains File, View, Tools, and Help.
- [ ] Open the File menu and test Exit.
- [ ] Re-run the application after closing it.
- [ ] Confirm that no API key, PDF file, database, or external service is required for startup.

---

## 13. Future Extension Points

The Application Shell will later host these modules:

| Future Module | Planned Shell Integration |
|---|---|
| PDF Document Service | Central document viewer receives PDF data through services |
| PDF Viewer | Central viewer receives rendered pages, zoom, scroll, modes |
| Bookmark Navigation | Left panel Bookmarks view receives real outline data |
| Selected Pages | Right panel receives selected-page widgets and actions |
| Notes and Annotations | Document viewer receives annotation tools |
| Datasheet Library | Left panel Library view receives library actions |
| AI Assistant | Right panel sub-tabs receive provider config and chat/report UI |
| Online Component Search | Dedicated panel or dialog |
| Tools Framework | Tools menu is populated from the registry |

Future modules must replace or extend placeholders without requiring a complete rewrite of the main window.

---

## 14. Completion Notes

- **Source files:**
  - `src/datasheet_studio/app.py` (updated: uses shared constants)
  - `src/datasheet_studio/ui/main_window.py` (four panels, menus, status bar, About dialog)
  - `src/datasheet_studio/core/constants.py` (new)
  - `pyproject.toml` (new: packaging + pytest config)
  - `tests/conftest.py` (new)
  - `tests/unit/test_application_shell.py` (new: 6+ passing tests)
- **Manual test result:** headless (`offscreen`) launch and event-loop run verified; window constructs with correct title, four menus, four resizable panels, and the Library/Bookmarks and Chat/Summary/Report/Settings sub-tabs.
- **Known limitations (as of 2026-08-14):** storage and web functionality remain placeholders; engineering tools remain placeholders. PDF support has grown beyond the shell: opening a file, bookmarks, single-page rendering with zoom/fit, page navigation, selected pages, notes, and partial AI are now implemented in later work (see `docs/CURRENT_STATUS.md`).
- **Commit:** pending.
- **Next planned module:** Module 2 — PDF Document Service (partially started with `infrastructure/pdf/reader.py`).
</content>
</replace_in_file>
