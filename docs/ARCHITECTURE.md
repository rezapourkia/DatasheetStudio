# Datasheet Studio — Architecture

> Read `docs/PRODUCT_VISION.md` before changing product behavior. The vision,
> engineering knowledge-base contract, and AI workflow are authoritative where
> older “future feature” wording in this document is narrower.

## 1. Architecture Purpose

This document defines the intended technical structure of Datasheet Studio.

The architecture must support gradual development of the application while keeping the code modular, understandable, testable, and easy to extend.

The project begins with a stable PDF-reading application shell and expands later with selected pages, notes, a local datasheet library, AI features, online search, and a plugin-based set of engineering tools.

---

## 2. Architectural Principles

Datasheet Studio must follow these principles:

1. Each module must have a clear and limited responsibility.
2. User-interface code must not contain PDF-processing or business logic.
3. PDF-related operations must be isolated from UI widgets.
4. Application data models must be independent from visual components where practical.
5. External services, such as AI providers or online component websites, must be isolated from core application logic.
6. API keys, local settings, databases, and user files must remain outside Git tracking.
7. New features must be added as separate modules when possible.
8. The application must remain usable even when optional future services, such as AI or online search, are unavailable.
9. Future engineering tools must be added through a plugin registry, not by editing the core application.

---

## 3. High-Level Layers

The application is divided into these layers:

```text
Presentation Layer  ( ui/ )
    PySide6 windows, panels, dialogs, widgets, user interaction

Application Layer  ( services/ )
    Use cases, coordination of actions, application services

Domain Layer  ( models/ )
    Core models and rules:
    datasheets, pages, selected pages, notes, bookmarks, library records

Infrastructure Layer  ( infrastructure/ )
    PDF engine, file system, database, settings, AI APIs, web services

Shared Layer  ( core/ )
    Constants, custom exceptions, logging configuration

Tools Layer  ( tools/ )
    Plugin registry and engineering tools (symbol extraction, package
    identification, DipTrace export, etc.)
```

Dependency direction must be:

```text
Presentation → Application → Domain
Infrastructure → Application / Domain through interfaces
Shared → usable by all layers when genuinely generic
Tools → Application / Domain through the tool registry contract
```

The domain layer must not depend directly on PySide6 widgets, PyMuPDF, a specific AI provider, or a specific web service.

---

## 4. Source-Code Structure

The intended source structure is:

```text
src/datasheet_studio/
├── __init__.py
├── app.py                  # application entry point
│
├── core/                   # Shared layer
│   ├── __init__.py
│   ├── constants.py
│   ├── exceptions.py
│   └── logging.py
│
├── models/                 # Domain layer
│   ├── __init__.py
│   └── ...                 # datasheet, page, selected_page, note, etc.
│
├── services/               # Application layer
│   ├── __init__.py
│   └── ...                 # use cases and services
│
├── ui/                     # Presentation layer
│   ├── __init__.py
│   ├── main_window.py
│   ├── panels/
│   ├── widgets/
│   └── dialogs/
│
├── infrastructure/
│   ├── __init__.py
│   ├── pdf/                # PyMuPDF adapter
│   ├── storage/            # local database / files
│   ├── settings/           # settings and secure key storage
│   ├── ai/                 # AI provider adapters
│   └── web/                # online component source adapters
│
└── tools/
    ├── __init__.py
    ├── registry.py         # ToolRegistry + Tool contract
    └── ...                 # future engineering tools
```

This structure replaces the earlier `presentation/application/domain/infrastructure/shared` naming. The folders above are the canonical names. Folders must be created gradually when their related module is started; empty speculative folders or placeholder code must not be created without a current need.

---

## 5. Module Responsibilities

### 5.1 `ui` (Presentation)

Contains everything the user sees and directly interacts with.

Examples:

- Main application window
- Left bookmark/navigation and library panel
- PDF document viewer
- Selected-pages panel
- AI assistant panel
- Menus, toolbars, buttons, dialogs, and status bar
- Styling and visual resources

This layer must request actions from the application layer. It should not directly perform complex PDF processing, database queries, or AI API calls.

### 5.2 `services` (Application)

Coordinates user actions and application workflows.

Examples:

- Open a datasheet
- Load PDF metadata and bookmarks
- Add or remove selected pages
- Save a note
- Add a datasheet to the local library
- Send a prepared datasheet request to an AI provider
- Trigger a registered tool

This layer bridges the graphical interface, domain models, and infrastructure services.

### 5.3 `models` (Domain)

Contains the core concepts of Datasheet Studio.

Planned domain models include:

- `Datasheet`
- `DatasheetPage`
- `Bookmark`
- `SelectedPage`
- `Annotation`
- `Note`
- `LibraryItem`
- `AiQuery`
- `AiReport`

This layer defines what these concepts are and their core rules. It must not depend on PySide6, PyMuPDF, a database engine, or a specific web/API provider.

### 5.4 `infrastructure`

Implements communication with external technologies and services.

Planned modules:

- PDF reading and rendering through PyMuPDF (`infrastructure/pdf`)
- File-system operations
- Local application settings (`infrastructure/settings`)
- Local datasheet library database (`infrastructure/storage`)
- Secure local storage for AI provider settings and API keys (`infrastructure/settings`)
- AI provider API adapters (`infrastructure/ai`)
- Web-search and component-source adapters (`infrastructure/web`)

For example, the PDF module uses PyMuPDF internally, but the rest of the application does not need to know PyMuPDF implementation details.

### 5.5 `core` (Shared)

Small utilities shared by multiple modules:

- Application constants
- Custom exceptions
- Logging configuration
- Common utility functions

This layer must remain small. Business logic that belongs to a specific module must not be moved here only for convenience.

### 5.6 `tools` (Plugin layer)

A registry-based plugin system for engineering tools.

The `Tool` contract defines:

- `id`
- `name`
- `category`
- `run(context)`

The `ToolRegistry` registers tools and exposes them to the application. The main window builds its **Tools** menu dynamically from the registry, so adding a future tool (symbol extraction, package identification, DipTrace export, etc.) does not require editing the core UI. Tools access the application and domain through a documented context object, never through direct UI manipulation.

---

## 6. Initial Application Shell

The first implementation module is the application shell.

Its responsibility is limited to:

- Start the PySide6 application
- Create and display the main window
- Define the main interface regions
- Provide placeholder panels for bookmarks/library, PDF viewing, selected pages, and AI assistant
- Provide a menu bar, a dynamic Tools menu (currently empty), and a status bar
- Establish a clean base for future modules

The shell must not implement complex PDF rendering, AI communication, databases, bookmarks, notes, selected-page rules, or online searches.

---

## 7. Layout Direction

The main window uses a four-panel horizontal split so all primary areas are visible at once and can be resized independently:

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

Order from left to right:

1. Bookmarks / Library panel
2. Document viewer (central, largest)
3. Selected pages panel
4. AI assistant panel

The AI panel itself contains sub-tabs for **Chat**, **Summary**, and **Report**. The Bookmarks/Library panel contains a switch between **Library** and **Bookmarks** views.

---

## 8. PDF Module Boundary

PDF handling is implemented as a dedicated infrastructure module (`infrastructure/pdf`).

Its future responsibilities include:

- Open a PDF file
- Read document metadata
- Read page count
- Extract bookmarks / document outline
- Render requested pages to images
- Extract text from pages where needed
- Report PDF-related errors safely

The user interface must receive PDF data through application services rather than directly calling PyMuPDF throughout the codebase.

---

## 9. Search Boundaries

Three distinct search features are kept separate:

| Search type | Location | Implementation |
|---|---|---|
| Local library search | Bookmarks/Library panel | `infrastructure/storage` |
| AI search inside a datasheet (RAG) | AI panel | `infrastructure/ai` over selected pages |
| Online component sources | dedicated panel/dialog | `infrastructure/web` adapters |

Online sources must always use official APIs or explicit permitted integrations; unrestricted scraping is prohibited.

---

## 10. Future Extension Boundaries

Future major features must remain isolated from the basic PDF reader:

| Feature | Planned Module Area |
|---|---|
| Selected pages | `models`, `services`, `ui` |
| Notes and annotations | `models`, `services`, `ui`, `infrastructure/storage` |
| Local datasheet library | `models`, `services`, `infrastructure/storage`, `ui` |
| AI assistant | `services`, `infrastructure/ai`, `ui` |
| Online component search | `services`, `infrastructure/web`, `ui` |
| DipTrace export | `tools` |
| Symbol/package extraction | `tools` |

Optional modules must not prevent the core PDF viewer from launching.

---

## 11. Data and Secret Storage Rules

The following items must never be committed to Git:

- API keys
- User-specific settings
- Local databases
- Downloaded datasheets
- Temporary PDF render files
- Application logs containing private information
- Virtual environment files

These items are stored in suitable local application-data directories or ignored project directories.

---

## 12. Testing Direction

Tests are organized separately from source code:

```text
tests/
├── unit/
├── integration/
└── manual/
```

Priority is given to testing non-UI logic, including:

- Domain models and rules
- PDF service behavior
- Selected-page workflows
- Storage behavior
- AI request preparation and provider adapters
- Tool registry behavior

Complex visual behavior may initially be tested manually, with automated UI tests added later when practical.

---

## 13. Current Status

This architecture is the approved direction for the project.

### 13.1 Implemented So Far

- Application Shell (four resizable panels, menus, status bar).
- PDF Document Service (`infrastructure/pdf/reader.py`): open, metadata,
  page count, bookmarks, page text, PNG rendering, selected-page export,
  notes-to-PDF.
- Selected Pages (add/remove/range/clear, save as PDF, compress/load `.dssel`).
- Notes and annotations (overlay, editor, manage dialog, save to PDF).
- AI Assistant (partial): real HTTP provider calls for DeepSeek / OpenAI /
  Anthropic / Google Gemini / Custom, plus OpenAI-compatible **tool/function
  calls** (`get_bookmarks`, `add_pages_to_selection`, `navigate_to_page`,
  `get_page_text`) so the model can act on the application. Chat panel is
  styled with Markdown rendering, `.md` export, retry, and a live status
  indicator.
- Debug Log (`core/logging.py` + Help -> Debug Log...).
- Tools Framework (`tools/registry.py`): deterministic registry and dynamic
  categorized Tools menu. Symbol Creator is registered instead of hard-coded.
- Native Flyback Designer (`tools/flyback_designer/`): Persian RTL PySide6 UI,
  pure Python DCM calculation engine, versioned JSON projects, and no HTML or
  WebView dependency. Bundled core/component values remain illustrative and
  unverified.

### 13.2 Known Architecture Deviation (AI HTTP)

The real HTTP provider logic currently lives in `services/ai_service.py`
(Application layer) instead of an `infrastructure/ai` adapter. This keeps the
feature working while the project is small, but the intended home for
provider-specific HTTP code is `infrastructure/ai` (per the layer rules in
this document and ADR-011). A future refactor should move the HTTP transport
into `infrastructure/ai` and keep only use-case logic in `services/ai_service.py`.

### 13.3 Next Steps

Follow `docs/PRODUCT_VISION.md`, `docs/ROADMAP.md`, and
`docs/CURRENT_STATUS.md`. The active next phase is the Knowledge Base v2
foundation defined in `docs/ROADMAP.md` section 17. Remaining generic AI work
continues only where it supports that end-to-end workflow.
