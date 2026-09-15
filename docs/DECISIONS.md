# Datasheet Studio — Architecture and Technical Decisions

**Last updated:** 2026-09-15
**Status:** Active
**Purpose:** Record important technical, architectural, and workflow decisions so future development remains consistent.

---

## 1. Decision Record Rules

This document records decisions that have a meaningful effect on the project structure, development workflow, security, maintainability, or future module design.

Each decision should include:

- A unique identifier
- A title
- Its current status
- The decision date
- Context
- The chosen decision
- Consequences
- Alternatives when relevant

Decision statuses:

| Status | Meaning |
|---|---|
| Proposed | Under consideration; not yet approved |
| Accepted | Approved and currently active |
| Superseded | Replaced by a newer decision |
| Deprecated | No longer recommended, but may still exist temporarily |
| Rejected | Considered but intentionally not selected |

New important decisions must be added here rather than being kept only in chat messages, source-code comments, or memory.

---

## 2. Decision Index

| ID | Title | Status | Date |
|---|---|---|---|
| ADR-001 | Use Python as the Primary Programming Language | Accepted | 2026-08-12 |
| ADR-002 | Use PySide6 for the Desktop User Interface | Accepted | 2026-08-12 |
| ADR-003 | Use PyMuPDF for PDF Processing | Accepted | 2026-08-12 |
| ADR-004 | Use a Layered Modular Architecture | Accepted | 2026-08-12 |
| ADR-005 | Use `src/` Layout for the Python Package | Accepted | 2026-08-12 |
| ADR-006 | Keep Feature Modules Isolated by Responsibility | Accepted | 2026-08-12 |
| ADR-007 | Use Git with Focused Commits on the `main` Branch | Accepted | 2026-08-12 |
| ADR-008 | Use Markdown Documentation as the Project Handoff System | Accepted | 2026-08-12 |
| ADR-009 | Keep Secrets and Sensitive User Data Out of Source Control | Accepted | 2026-08-12 |
| ADR-010 | Build the Application Incrementally, Starting with Application Shell | Accepted | 2026-08-12 |
| ADR-011 | Support Multiple AI Providers Through an Abstraction Layer | Accepted | 2026-08-12 |
| ADR-012 | Prefer Official APIs and Permitted Integrations for Online Sources | Accepted | 2026-08-12 |
| ADR-013 | Use Four Simultaneous Resizable Panels (Not Tabs) for the Main Layout | Accepted | 2026-08-13 |
| ADR-014 | Use a Plugin Registry for Future Engineering Tools | Accepted | 2026-08-13 |
| ADR-015 | Use Short Layered Directory Names (`ui`, `services`, `models`, `infrastructure`, `core`, `tools`) | Accepted | 2026-08-13 |
| ADR-016 | Real AI HTTP Integration with Tool/Function Calls | Accepted | 2026-08-14 |
| ADR-017 | Implement Flyback Designer as a Native Documented Tool | Accepted | 2026-09-14 |
| ADR-018 | Treat Datasheet Studio as a Datasheet-to-Design Workspace | Accepted | 2026-09-15 |
| ADR-019 | Use a Portable File Vault with a Rebuildable SQLite Index | Accepted | 2026-09-15 |
| ADR-020 | Keep AI Evidenced and Advisory Around Deterministic Engines | Accepted | 2026-09-15 |
| ADR-021 | Embed a Chromium Browser for Online Datasheet Search | Accepted | 2026-09-15 |

---

## ADR-001 — Use Python as the Primary Programming Language

**Status:** Accepted
**Date:** 2026-08-12

### Context

Datasheet Studio requires a desktop graphical user interface, PDF processing, future AI-provider integration, local data storage, automation, and possible engineering-data processing.

The project needs a language with a strong ecosystem, readable syntax, good support for AI and data-processing libraries, and practical development on Windows.

### Decision

Use **Python 3.13+** as the primary programming language.

The currently verified development version is `3.13.3`.

### Consequences

**Positive:**

- Readable and maintainable syntax
- Strong ecosystem for PDF, AI, HTTP, databases, testing, and automation
- Good compatibility with PySide6 and PyMuPDF
- Suitable for rapid iterative development
- Easy integration with future AI-provider SDKs and APIs

**Negative:**

- Native executable packaging may require additional work later.
- Performance-sensitive operations must be profiled and optimized carefully.
- Dependency versions must be managed consistently through `requirements.txt`.

---

## ADR-002 — Use PySide6 for the Desktop User Interface

**Status:** Accepted
**Date:** 2026-08-12

### Context

Datasheet Studio requires a modern, resizable desktop interface with panels, menus, dialogs, custom widgets, PDF-page display, and future complex engineering workflows.

### Decision

Use **PySide6** as the primary GUI framework. Current verified version: `6.11.1`.

The application uses Qt concepts such as `QApplication`, `QMainWindow`, layouts, widgets, dialogs, menus, status bars, `QSplitter`, `QTabWidget`, and signals/slots.

### Consequences

**Positive:**

- Mature and feature-rich desktop UI toolkit
- Suitable for professional multi-panel applications
- Good support for resizable layouts and complex widgets
- Supports Windows well
- Provides a clear path for future UI expansion

**Negative:**

- Qt widget hierarchy and signal/slot patterns require disciplined organization.
- UI code must not contain domain, storage, PDF-processing, or AI-provider logic.
- Application packaging and Qt runtime distribution must be addressed later.

---

## ADR-003 — Use PyMuPDF for PDF Processing

**Status:** Accepted
**Date:** 2026-08-12

### Context

A core future capability is opening and reading datasheet PDF files, rendering pages, extracting text, reading metadata, and navigating PDF bookmarks or outlines.

### Decision

Use **PyMuPDF** as the initial PDF-processing library. Current verified version: `1.28.2`.

PyMuPDF is used only inside dedicated PDF-related Infrastructure components (`infrastructure/pdf`).

### Consequences

**Positive:**

- Suitable for PDF rendering and document inspection
- Supports text extraction and page-level operations
- Supports document metadata and outline access
- Appropriate for future page thumbnails and rendered page views

**Negative:**

- PDF operations must not be called directly from UI widgets.
- Rendering performance and memory usage must be measured with large datasheets.
- The project must handle malformed, encrypted, unavailable, or unsupported PDF files safely.
- Licensing and distribution requirements must be reviewed before release.

---

## ADR-004 — Use a Layered Modular Architecture

**Status:** Accepted
**Date:** 2026-08-12

### Context

Datasheet Studio includes multiple independent concerns: user interface, PDF handling, bookmark navigation, selected pages, notes, datasheet library, AI providers, secure key storage, online search, and export tools. Without defined boundaries, the project could become difficult to test, maintain, and extend.

### Decision

Use a layered modular architecture inspired by Clean Architecture and MVC-style separation.

Primary layers (see ADR-015 for directory naming):

- Presentation (`ui/`)
- Application (`services/`)
- Domain (`models/`)
- Infrastructure (`infrastructure/`)
- Shared (`core/`)
- Tools (`tools/`)

Dependency direction must generally move inward:

- `Presentation → Application → Domain`
- `Infrastructure → Application / Domain` through defined interfaces
- `Shared` usable by all layers when genuinely generic
- `Tools → Application / Domain` through the tool registry contract

### Consequences

**Positive:**

- Clear separation of responsibilities
- Better testability
- Lower coupling between UI and technical services
- Easier replacement of AI providers, storage systems, or PDF implementation details
- Better support for gradual development

**Negative:**

- More files and structure are required than in a small script.
- Developers must avoid placing convenience logic in incorrect layers.
- Some early modules may appear simple, but must still respect architectural boundaries.

---

## ADR-005 — Use `src/` Layout for the Python Package

**Status:** Accepted
**Date:** 2026-08-12

### Context

Python projects can accidentally import source files directly from the repository root during development, hiding packaging or import problems.

### Decision

Use a `src/` package layout. Primary package location: `src/datasheet_studio/`. Tests remain outside the source package in `tests/`.

### Consequences

**Positive:**

- Reduces accidental imports from the project root
- Encourages correct package installation and import behavior
- Provides a clean separation between source code, tests, documentation, and tooling

**Negative:**

- The environment must be configured correctly for module execution.
- Developers must use the documented startup command `python -m datasheet_studio.app`.

---

## ADR-006 — Keep Feature Modules Isolated by Responsibility

**Status:** Accepted
**Date:** 2026-08-12

### Context

The application has many planned features. Combining them in a single large main-window file or a collection of unrelated utility files would make future changes risky.

### Decision

Develop features as focused modules with dedicated documentation and clear ownership.

Planned modules: Application Shell, PDF Document Service, PDF Viewer, Bookmark Navigation, Selected Pages, Notes and Annotations, Local Datasheet Library, AI Assistant, Online Search, Tools Framework + Export.

Each meaningful module has a corresponding specification file under `docs/modules/`.

### Consequences

**Positive:**

- Features can be developed and tested incrementally.
- Future AI assistants or developers can understand module boundaries.
- Changes remain easier to review and commit.
- Failures in one feature are less likely to affect unrelated features.

**Negative:**

- Module boundaries must be reviewed before adding code.
- Some shared interfaces may be needed before a full feature is implemented.
- Avoid creating empty speculative modules or abstractions before they are needed.

---

## ADR-007 — Use Git with Focused Commits on the `main` Branch

**Status:** Accepted
**Date:** 2026-08-12

### Context

The project must remain recoverable, understandable, and safe while development is performed gradually.

### Decision

Use Git for source control. Current primary branch: `main`.

Commits must be focused and represent one coherent completed change, such as:

- `docs: establish project foundation`
- `feat: implement application shell layout`
- `test: add application shell smoke tests`
- `fix: correct shell startup behavior`

### Consequences

**Positive:**

- Provides history and recovery points
- Makes changes easier to inspect
- Supports safe collaboration and public repository use
- Makes AI-assisted development easier to review

**Negative:**

- Unrelated changes must not be mixed in one commit.
- Developers must inspect Git changes before committing.
- Secrets, generated files, local databases, and user files must not be committed.

---

## ADR-008 — Use Markdown Documentation as the Project Handoff System

**Status:** Accepted
**Date:** 2026-08-12

### Context

Development may continue across separate chat sessions, AI assistants, or future contributors. Important decisions and status must not depend only on chat history.

### Decision

Use Markdown files in the `docs/` directory as the canonical human-readable project handoff system.

Key documents:

- `docs/PROJECT_OVERVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/ENVIRONMENT_SETUP.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `docs/modules/`

### Consequences

**Positive:**

- A new development session can quickly understand the project.
- Architecture, status, module scope, and decisions remain visible in the repository.
- Documentation can be reviewed and version-controlled with code.

**Negative:**

- Documentation must be updated when important changes occur.
- Outdated documentation is harmful and must be corrected promptly.
- Documentation should remain concise enough to be maintained.

---

## ADR-009 — Keep Secrets and Sensitive User Data Out of Source Control

**Status:** Accepted
**Date:** 2026-08-12

### Context

Future versions may use AI-provider API keys, user notes, downloaded datasheets, local databases, search history, and application settings. The repository may become accessible to others.

### Decision

Never commit secrets or sensitive local user data to Git. This includes, but is not limited to: API keys, tokens, passwords, private configuration files, downloaded user datasheets, local databases containing user data, personal notes, session files, and logs containing sensitive values.

Sensitive paths and files must be included in `.gitignore` when introduced.

### Consequences

**Positive:**

- Reduces risk of credential exposure
- Protects users and future release users
- Keeps the repository safe

**Negative:**

- Secure local storage must be designed before AI-provider features are implemented.
- Developers must verify Git changes carefully before every commit.
- Example configuration files must contain placeholders only, never real values.

---

## ADR-010 — Build the Application Incrementally, Starting with Application Shell

**Status:** Accepted
**Date:** 2026-08-12

### Context

The project has a broad long-term feature set. Attempting to implement PDF, AI, storage, search, and export functions simultaneously would increase risk and make debugging difficult.

### Decision

Build the application in small, verified modules. The first implementation module is the **Application Shell** (`docs/modules/APP_SHELL.md`). It provides only the initial PySide6 main window, layout regions, placeholder panels, menus, and basic startup behavior.

### Consequences

**Positive:**

- Early visible progress
- Easier debugging
- Smaller and safer Git commits
- Clear verification after each module
- Prevents unfinished future logic from being mixed into the first UI implementation

**Negative:**

- Initial versions will intentionally contain placeholders.
- Some user-facing functionality will not be available until later modules.
- Developers must resist adding unrelated features during a module implementation.

---

## ADR-011 — Support Multiple AI Providers Through an Abstraction Layer

**Status:** Accepted
**Date:** 2026-08-12

### Context

The user may use different AI providers and provider gateways. Provider APIs, models, pricing, authentication, rate limits, and request formats can vary. Directly connecting UI code to one provider creates tight coupling.

### Decision

Future AI functionality must use a provider abstraction. The Presentation layer communicates with Application-layer use cases. Provider-specific implementations remain in `infrastructure/ai`.

AI-assisted search over datasheet content uses retrieval over selected pages/text (RAG-style); provider adapters receive prepared context, not raw UI state.

### Consequences

**Positive:**

- Providers can be added or replaced more safely.
- UI code remains independent of provider details.
- Provider credentials and request handling can be isolated.
- Easier testing through mock provider implementations.

**Negative:**

- The exact provider interface must be designed carefully when AI implementation begins.
- Features common to one provider but not others may require capability checks.
- The retrieval/chunking strategy must be designed before AI search is reliable.
- Secure credential storage remains a separate required decision and module.

---

## ADR-012 — Prefer Official APIs and Permitted Integrations for Online Sources

**Status:** Accepted
**Date:** 2026-08-12

### Context

The application may later search sources such as Mouser, DigiKey, SnapEDA, Component Search Engine, and Ultra Librarian for component data, datasheets, models, pricing, or availability. Third-party websites may have terms of service, API requirements, authentication, rate limits, and restrictions on automated access.

### Decision

Prefer official APIs, documented integrations, licensed data sources, and explicitly permitted access methods. Do not design the project around unrestricted scraping of websites.

Each future online-source integration must document: access method, authentication requirements, rate limits, data ownership and licensing constraints, error handling, caching policy, and user-visible limitations.

### Consequences

**Positive:**

- Lower legal, technical, and maintenance risk
- Better reliability than fragile page scraping
- More predictable behavior for users

**Negative:**

- Some sources may require API keys, accounts, approval, or paid access.
- Some desired data may not be available through official APIs.
- Integrations may need to be implemented source by source.
- Bulk/automatic datasheet downloading may be restricted by some sources.

---

## ADR-013 — Use Four Simultaneous Resizable Panels (Not Tabs) for the Main Layout

**Status:** Accepted
**Date:** 2026-08-13

### Context

The product owner described the main workspace as four side-by-side areas from the left: bookmarks, document viewer, selected pages, and AI assistant. Earlier documentation described the AI area as a bottom panel, which conflicted with this intent.

Using literal Qt tabs would show only one area at a time, increasing the number of clicks and hiding context.

### Decision

Use a single horizontal `QSplitter` with four simultaneously visible, resizable panels, ordered left to right:

1. Bookmarks / Library
2. Document viewer (widest)
3. Selected pages
4. AI assistant

Nested `QTabWidget` sub-tabs are allowed within a panel for closely related sub-views:

- Left panel: **Library** / **Bookmarks**
- AI panel: **Chat** / **Summary** / **Report**

### Consequences

**Positive:**

- All core context is visible at once, minimizing clicks.
- Matches the product owner's mental model directly.
- `QSplitter` provides natural resizing.

**Negative:**

- Four simultaneous panels consume horizontal space on narrow screens.
- The AI panel is narrower than a full-width bottom panel would be.
- Panel content must be designed to work well at various widths.

**Alternatives considered:**

- AI as a bottom dock panel (earlier documented layout) — rejected because the owner wanted AI as the fourth column.
- Literal top-level tabs — rejected because only one area would be visible at a time.

---

## ADR-014 — Use a Plugin Registry for Future Engineering Tools

**Status:** Accepted
**Date:** 2026-08-13

### Context

The owner plans to add many engineering tools over time: symbol extraction, package identification, pin-table extraction, DipTrace export, 3D model discovery, report export, and more. Hardcoding each tool into the main window would make the core grow unsafely.

### Decision

Add a `tools/` plugin layer with:

- A `Tool` contract (`id`, `name`, `category`, `run(context)`)
- A `ToolRegistry` that registers and lists tools
- A dynamic **Tools** menu in the main window built from the registry

Tools access application/domain data through a documented context object and must not reach into UI internals.

### Consequences

**Positive:**

- New tools are added without editing the core UI.
- Tools remain independently testable.
- The core application stays stable as the toolset grows.
- Supports the long-term extensibility goal.

**Negative:**

- The registry and context contract must be defined before the first real tool.
- There is a risk of over-abstracting if only one or two simple tools are needed.
- Tools must be documented separately to keep scope clear.

---

## ADR-015 — Use Short Layered Directory Names

**Status:** Accepted
**Date:** 2026-08-13

### Context

The initial source tree already existed with short names (`ui/`, `models/`, `services/`, `core/`), while the original architecture document used longer names (`presentation/`, `domain/`, `application/`, `infrastructure/`, `shared/`). This mismatch would confuse contributors.

### Decision

Adopt the short directory names as canonical:

- `ui/` = presentation
- `services/` = application
- `models/` = domain
- `infrastructure/` = infrastructure (new)
- `core/` = shared
- `tools/` = plugin layer (new)

### Consequences

**Positive:**

- Matches the already-created source tree, minimizing churn.
- Clear and short import paths.

**Negative:**

- Original docs must be updated (done in `ARCHITECTURE.md`).
- Fixed mapping must be communicated to future contributors.

---

## ADR-016 — Real AI HTTP Integration with Tool/Function Calls

**Status:** Accepted
**Date:** 2026-08-14

### Context

The AI panel originally returned mock responses and could not act on the
application (e.g., adding pages to the selection). Users asked for real
answers and for the AI to perform actions such as "find the UART section and
add it".

### Decision

- Replace the mock `AIService` with real HTTP calls to the providers'
  chat-completion endpoints (DeepSeek, OpenAI, Anthropic, Google Gemini, and
  custom OpenAI-compatible / Anthropic endpoints) using only the Python
  standard library (`urllib`).
- Implement OpenAI-compatible **function calling** (`tools` / `tool_calls`)
  for DeepSeek, OpenAI, and Custom providers, with the application exposing
  four tools: `get_bookmarks`, `add_pages_to_selection`, `navigate_to_page`,
  and `get_page_text`. Tool calls execute on the GUI thread via a bridge and
  results are fed back to the model in a loop.
- Include the document outline (bookmarks with page numbers) in the AI
  context so the model can map sections to pages.
- Style the chat panel with Markdown rendering, `.md` export, retry, and a
  live status indicator.

### Consequences

**Positive:**

- The AI answers real questions and can perform real actions in the app.
- No new runtime dependency was added (`urllib` only).
- Test Connection and Fetch Models now work against real endpoints.

**Negative / Trade-offs:**

- Anthropic and Gemini tool calls are not yet implemented (chat-only).
- The AI HTTP transport currently lives in `services/ai_service.py` instead
  of `infrastructure/ai`; this deviation is tracked in
  `docs/ARCHITECTURE.md` for a future refactor.
- Function calling depends on provider support and can behave differently
  across providers.

### Alternatives Considered

- Parser-based action markers (`[ADD_PAGES: 35,36]`) in the model reply —
  simpler but fragile.
- Using a third-party HTTP client or SDK — rejected to avoid new dependencies
  at this stage.

---

## ADR-017 — Implement Flyback Designer as a Native Documented Tool

**Status:** Accepted
**Date:** 2026-09-14

### Context

The earlier flyback calculator was a direct-open browser application. The
owner requested that flyback design become part of Datasheet Studio as real
desktop software and explicitly rejected importing or wrapping the HTML user
interface. The project also requires Markdown-first feature development and
already has an accepted registry architecture for engineering tools.

### Decision

Implement Flyback Designer as a registered, native PySide6 tool. Keep all
engineering equations in a pure Python engine inside the tool package, keep the
tool UI Persian and right-to-left, and store designs in versioned JSON.

The former browser project is a reference only for reviewed equations,
numerical fixtures, provenance, and limitations. Datasheet Studio must not load
its HTML, CSS, JavaScript, local storage, or a WebView.

All bundled core and generic component profiles remain illustrative and
unverified. Automated tests establish equation consistency and regression
coverage, not production or laboratory validation.

### Consequences

- Flyback Designer follows normal desktop interaction and packaging.
- The calculation engine is testable without Qt or a display server.
- Existing numerical reference values can be compared across implementations.
- Future CCM/QR solvers can be added behind a mode-specific engine boundary.
- The native UI must be maintained separately from the former browser project.
- Production use still requires manufacturer data, simulation, prototyping,
  thermal/EMI work, and safety verification.

### Alternatives Considered

- Embedding the existing HTML in Qt WebEngine: rejected by the owner and would
  preserve the unwanted browser interface.
- Continuing two independent products: rejected because Datasheet Studio is
  now the intended engineering workspace.

---

## ADR-018 — Treat Datasheet Studio as a Datasheet-to-Design Workspace

**Status:** Accepted

**Date:** 2026-09-15

### Context

The earlier documents framed the application mainly as a PDF workspace and the
native Flyback Designer as an isolated preliminary calculator. The owner needs
a continuous workflow from an open controller datasheet through AI-assisted
extraction, reviewed reusable data, real magnetic selection, engineering
analysis, and a saved reproducible design.

### Decision

Adopt `docs/PRODUCT_VISION.md` as the authoritative product workflow. Tools
receive a documented current-datasheet context and use shared library records;
they do not create private, disconnected copies of component knowledge.

### Consequences

- Current PDF, library, AI, and tool modules need explicit integration contracts.
- Flyback Designer v1 remains useful but is not the target product.
- Product acceptance is measured by end-to-end workflows, not feature presence.

## ADR-019 — Use a Portable File Vault with a Rebuildable SQLite Index

**Status:** Accepted

**Date:** 2026-09-15

### Context

A single `library.json` manifest and manufacturer folders work for a small PDF
collection but do not provide robust full-text search, revision/evidence links,
deduplication, or engineering catalogue queries at daily-use scale.

### Decision

Evolve the library into the portable layout in
`docs/modules/ENGINEERING_KNOWLEDGE_BASE.md`: immutable content-addressed source
files, human-readable Markdown records, typed JSON profiles, and a rebuildable
SQLite/FTS index. Normal users receive an in-app, recoverable upgrade flow.

### Consequences

- SQLite improves query and transaction behavior without becoming the only copy
  of user knowledge.
- Source hashes provide duplicate detection and stable evidence references.
- More schema/versioning and migration tests are required.

## ADR-020 — Keep AI Evidenced and Advisory Around Deterministic Engines

**Status:** Accepted

**Date:** 2026-09-15

### Context

AI is valuable for reading long controller/core documents and interacting with
the user, but undocumented prompts and model-generated arithmetic would be
difficult to reproduce, audit, or maintain across providers and developers.

### Decision

Use versioned Markdown prompts and strict response schemas. AI extracts facts
with page evidence, explains results, and proposes design changes. Pure,
tested engines own calculations and constraints. User acceptance is required
before AI proposals change design inputs or review states.

### Consequences

- Designs remain calculable offline and independent of chat history.
- AI runs become auditable project artifacts.
- Complete extraction requires explicit page coverage and failure reporting.

## ADR-021 — Embed a Chromium Browser for Online Datasheet Search

**Status:** Accepted

**Date:** 2026-09-15

### Context

The owner's daily workflow requires searching the open web (Google-style) for
datasheets, opening PDFs from result links, and saving them into the local
library — all without leaving Datasheet Studio. Opening the OS browser and
manually copying files back breaks the workflow. ADR-017 rejected a WebView
only for the Flyback Designer tool UI; it did not decide the online-search
surface.

### Decision

Use QtWebEngine (`QWebEngineView`) to embed a Chromium tab inside the
application as the user-driven online search/download surface. Web searches
(default Google, optional DuckDuckGo/Bing) run inside the embedded browser;
downloads are validated (%PDF signature, SHA-256, size) and can be saved
directly into the accepted v2 knowledge vault (falling back to the v1 library
flow when no vault is active). Browsing remains strictly user-driven
(ADR-012); no scraping or automated crawling is introduced.

### Consequences

**Positive:**

- The full web remains usable for sources without permitted APIs while
  downloads still enter the validated knowledge-base pipeline.
- PDFs can be read inside the embedded viewer or opened in the Datasheet
  Studio viewer with one click.

**Negative:**

- QtWebEngine adds runtime weight (render processes) and must be handled
  gracefully when unavailable (existing fallback to the system browser).
- Websites may show consent/anti-bot pages; engine choice is configurable.

### Alternatives Considered

- System-browser-only flow — explicitly rejected by the owner (broken
  workflow).
- API-only search (Phase 6 adapters) — kept in parallel, but not a
  replacement for arbitrary web hunting.

## 3. Pending Decisions

The following decisions are intentionally postponed until their related modules begin.

| Planned Decision | Related Future Module |
|---|---|
| Local database technology and schema | Datasheet Library |
| Secure API-key storage strategy on Windows | AI Assistant / Settings |
| Exact AI-provider interface and first supported provider | AI Assistant |
| Retrieval/chunking strategy for AI search | AI Assistant |
| PDF render cache strategy and memory limits | PDF Viewer |
| Annotation data format and persistence model | Notes and Annotations |
| Datasheet download folder and file-naming policy | Datasheet Library / Online Search |
| Visual design system, theme, icons, and accessibility rules | UI refinement |
| DipTrace export formats and integration mechanism | Tools / Export |
| Application packaging and installer strategy | Release / Distribution |
| Automated test framework configuration and CI workflow | Testing Infrastructure |

These pending decisions must be made before or during their related module implementation, not prematurely.

---

## 4. How to Add a New Decision

Copy the template below and add it before the Pending Decisions section.

```markdown
## ADR-XXX — Short Decision Title

**Status:** Proposed
**Date:** YYYY-MM-DD

### Context

Explain the problem, requirement, or constraint.

### Decision

State the selected approach clearly.

### Consequences

**Positive:**

- Positive result

**Negative:**

- Trade-off or limitation

### Alternatives Considered

- Alternative 1
- Alternative 2
```

If a previously accepted decision changes, do not delete it. Change its status to `Superseded` and create a new ADR that references the old one.
