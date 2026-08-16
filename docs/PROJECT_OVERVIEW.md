# Datasheet Studio — Project Overview

## 1. Project Identity

**Project name:** Datasheet Studio  
**Type:** Desktop application  
**Primary platform:** Windows  
**Primary language:** Python  
**UI framework:** PySide6  
**PDF engine:** PyMuPDF  

Datasheet Studio is a specialized desktop application for reading, organizing, annotating, searching, and analyzing electronic-component datasheets in PDF format.

The project is intended for electronics engineers and hardware designers who need a fast, focused, and well-organized environment for working with component datasheets.

---

## 2. Problem Statement

Electronic datasheets are often long, complex PDFs. Important information such as pin assignments, absolute maximum ratings, electrical characteristics, package dimensions, application circuits, and ordering codes can be difficult and time-consuming to locate.

Existing PDF readers are general-purpose applications and do not provide a workflow designed specifically for electronic-component datasheets.

Datasheet Studio will provide a purpose-built workflow to make datasheet review, extraction of important pages, note-taking, bookmarking, and future AI-assisted analysis faster and easier.

---

## 3. Primary Goals

The application must:

1. Open and render PDF datasheets reliably.
2. Display document bookmarks and document structure.
3. Allow users to browse pages with zoom and scrolling.
4. Allow users to select important pages and collect them in a dedicated area.
5. Support annotations and notes on datasheets.
6. Provide a clean, modern, simple interface with minimal unnecessary clicks.
7. Maintain a local datasheet library for storing, categorizing, searching, and reopening datasheets.
8. Be modular, maintainable, and documented for long-term development.
9. Prepare a safe extension point for AI-assisted datasheet search, summaries, and reports.

---

## 4. Target Users

Primary users are:

- Electronics engineers
- Hardware designers
- PCB designers
- Embedded systems developers
- Students and researchers working with electronic components

The primary user is expected to work with IC, module, sensor, passive-component, and connector datasheets frequently.

---

## 5. Core User Workflow

A typical workflow is:

1. The user opens a PDF datasheet.
2. The application reads PDF metadata, page count, and bookmarks.
3. The user navigates pages in the document viewer.
4. Important pages are transferred to the selected-pages area.
5. The user adds notes, bookmarks, or annotations.
6. The user searches the datasheet or, in future versions, asks an AI assistant questions about it.
7. The datasheet can be saved to the internal library with categories and metadata.

---

## 6. Planned Main Interface Areas

The initial application interface is expected to contain these main areas:

The main window uses four resizable panels visible side by side (left to right):

1. **Bookmarks / Library panel (left):**
   - PDF bookmarks / document outline
   - Navigation tree
   - Local datasheet library with search, categories, and tags
   - A switch between "Library" and "Bookmarks" views

2. **Document viewer (central, widest):**
   - PDF page rendering
   - Zoom controls and scroll controls
   - Single-page and multi-page viewing modes
   - Double-clicking a page adds it to selected pages

3. **Selected pages panel:**
   - Contains pages chosen by the user
   - Double-clicking a selected page removes it
   - Supports adding a page range, clearing all, or clearing selected pages

4. **AI assistant panel (right):**
   - API provider and API key configuration
   - Datasheet question answering (chat)
   - Search, summaries, and structured reports
   - Sub-tabs for Chat, Summary, and Report
   - Must be designed so API keys are never committed to Git

---

## 7. Future Capabilities

Future versions may include:

- AI extraction of component symbols and pin information
- AI-assisted package identification
- Export workflows for DipTrace
- Search integration with sources such as:
  - SnapEDA
  - Component Search Engine
  - Ultra Librarian
  - Mouser
  - DigiKey
- Price and availability lookup
- Downloading and organizing datasheets
- 3D model discovery
- Local searchable datasheet database
- Exporting selected datasheet pages and notes as a report

---

## 8. Non-Goals for the First Development Stage

The first development stage should not attempt to implement every future feature.

Initial work must focus on:

- A stable application foundation
- Clear module boundaries
- Reliable PDF opening and rendering
- A basic but correct UI shell
- Documentation and development workflow
- Testable architecture

AI integration, online search, database synchronization, and external CAD exports are planned extensions and must not destabilize the core PDF-reading application.

---

## 9. Engineering Principles

The project must follow these principles:

- Keep modules small and focused.
- Separate user interface, business logic, data models, and infrastructure code.
- Avoid placing all application logic in one file.
- Prefer explicit, readable code over clever but unclear code.
- Document architectural decisions.
- Add tests for non-UI logic where practical.
- Never commit secrets, API keys, local databases, temporary files, or virtual environments to Git.
- Make changes in small, reviewable commits.

---

## 10. Current Development Stage

The project has moved past Foundation and now has a working application:

- **Application Shell** (four resizable panels, menus, status bar).
- **PDF Document Service & Viewer** — open PDFs, metadata, bookmarks, page
  navigation, zoom-to-fit, page text extraction, PNG rendering.
- **Selected Pages** — add/remove/range/clear, export to PDF, compress/load
  `.dssel`.
- **Notes** — overlay annotations, editor, manage dialog, save to PDF.
- **AI Assistant (partial)** — real API calls for DeepSeek/OpenAI/Anthropic/
  Google Gemini/Custom, function calling (tools) so the model can add pages
  and read bookmarks, a styled Markdown chat with `.md` export, retry, and a
  live status indicator.
- **Debug Log** — in-memory event log viewable from Help -> Debug Log.

See `docs/CURRENT_STATUS.md` for the exact verification status and
`docs/ARCHITECTURE.md` for the implemented architecture (including a known
deviation: AI HTTP code currently lives in `services/` instead of
`infrastructure/ai`).