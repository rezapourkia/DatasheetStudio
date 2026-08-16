# Datasheet Studio — Development Workflow

## 1. Purpose

This document defines the standard workflow for developing Datasheet Studio.

Its purpose is to keep development organized, predictable, modular, and documented. Every feature must be planned before implementation, developed in small steps, tested appropriately, and recorded in project documentation.

Datasheet Studio is intended to be a long-term, extensible engineering application. Therefore, fast but unstructured changes must be avoided.

---

## 2. Development Principles

All development work must follow these rules:

- Work on one module or clearly defined feature at a time.
- Understand the current documentation before changing code.
- Do not implement a feature until its responsibility and module ownership are clear.
- Keep changes small, focused, and reviewable.
- Separate presentation, application, domain, and infrastructure responsibilities.
- Do not place unrelated logic into existing files only because it is convenient.
- Prefer readable and explicit code over clever but difficult code.
- Do not commit secrets, API keys, user data, local databases, downloaded PDFs, logs, or virtual environments.
- Update documentation whenever a decision, module boundary, workflow, or implementation status changes.
- Test non-UI logic whenever practical.
- Avoid changing multiple unrelated modules in a single commit.

---

## 3. Development Order

The project must generally progress in the following order:

1. Foundation and documentation
2. Application Shell
3. PDF module
4. Document navigation and bookmarks
5. Selected-pages workflow
6. Notes and annotations
7. Local datasheet library
8. Search and organization features
9. AI assistant integration
10. Online component-source integrations
11. Export and CAD-related tools
12. Advanced AI analysis features

This order may be adjusted only when a documented technical reason exists.

Optional future features, including AI providers, web search, and CAD export, must not destabilize the core PDF-reading workflow.

---

## 4. Standard Module Workflow

Every new module must follow the steps below.

### Step 1 — Review Existing Documentation

Before starting implementation, review the relevant documents:

- `docs/PROJECT_OVERVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- The relevant module document in `docs/modules/`

The developer must understand:

- Why the module exists
- Which layer or layers own the module
- What the module is allowed to do
- What the module must not do
- Which future modules may depend on it

---

### Step 2 — Define the Module Scope

Before writing code, create or update a module document in:

```text
docs/modules/
The module document should define:

Module name
Purpose
User-facing behavior
Responsibilities
Non-responsibilities
Related architecture layers
Expected source-code location
Dependencies
Acceptance criteria
Known limitations
Future extension points
A module must have a limited scope. If its scope becomes too broad, divide it into smaller modules or phases.

Step 3 — Record Important Decisions
If implementation requires an important technical or architectural decision, add it to:

text
docs/DECISIONS.md
Examples of decisions that must be recorded:

Choosing a library or storage approach
Changing a module boundary
Defining how settings or secrets are stored
Choosing a PDF-rendering strategy
Defining an AI provider abstraction
Deciding how selected pages are represented internally
Changing the planned source-code structure
Each decision entry should include:

Date
Decision title
Context
Decision
Reason
Consequences or trade-offs
Small implementation details do not need a decision record unless they affect future architecture.

Step 4 — Implement in Small Steps
Implementation must be completed in small, understandable increments.

Recommended order:

Create required package or module files.
Define domain models or interfaces if needed.
Implement application services or use cases.
Implement infrastructure adapters if needed.
Connect the feature to the PySide6 presentation layer.
Add error handling.
Add or update tests.
Run the application manually when UI behavior is involved.
Do not create large amounts of unused placeholder code, empty packages, or speculative abstractions.

Create code only when there is a current documented need.

Step 5 — Test the Change
Testing must be appropriate to the type of change.

Non-UI Logic
For domain, application, and infrastructure logic, add automated tests where practical.

Examples:

Domain model validation
Selected-page add/remove rules
PDF metadata extraction
Bookmark extraction
Storage behavior
AI request preparation
Error handling
Tests should normally be placed in:

text
tests/unit/
tests/integration/
User Interface Changes
For PySide6 interface changes, perform manual verification at minimum.

Verify that:

The application starts successfully.
The relevant window or panel opens correctly.
The feature works as intended.
Errors are handled without crashing the application.
Existing visible functionality has not been unintentionally broken.
Manual test notes may be recorded in:

text
tests/manual/
when the test procedure is important or likely to be repeated.

Step 6 — Update Documentation
After implementation, update the relevant documentation.

At minimum, consider updating:

docs/CURRENT_STATUS.md
The related module document in docs/modules/
docs/DECISIONS.md, if a decision was made
docs/ARCHITECTURE.md, only if architecture changed
docs/ROADMAP.md, if planned order or milestones changed
Documentation must describe the actual state of the project, not only the original plan.

Step 7 — Review Before Commit
Before committing, verify the following:

The application starts if the change affects application startup or UI.
Relevant tests pass.
No API keys, passwords, private files, local settings, or user data are included.
No virtual environment files are included.
No generated caches, temporary render files, or logs are included.
The change is limited to the intended module or task.
Documentation is updated when necessary.
The Git diff is understandable and contains no accidental file changes.
Useful commands:

bash
git status
git diff
Step 8 — Create a Focused Git Commit
Each commit should represent one coherent change.

Good commit messages use a clear prefix:

text
docs: add development workflow
docs: define application shell module scope
feat: add main application window
feat: add PDF metadata service
test: add selected pages unit tests
fix: handle invalid PDF file errors
refactor: separate PDF service from viewer widget
chore: update ignored local files
Avoid vague commit messages such as:

text
update
changes
fix stuff
new files
work
A commit should be small enough that its purpose can be understood from its message and diff.

5. Branch and Commit Policy
The repository currently uses the main branch.

During the early foundation stage, small and carefully reviewed changes may be committed directly to main.

As the project becomes more complex, new work should normally use a dedicated feature branch.

Recommended branch naming:

text
feature/application-shell
feature/pdf-service
feature/selected-pages
feature/annotations
feature/datasheet-library
feature/ai-assistant
fix/pdf-open-error
docs/workflow-update
A feature branch should contain one focused feature or fix.

Before merging a branch into main, verify that:

The feature meets its acceptance criteria.
Relevant tests pass.
Documentation is updated.
No secrets or local files are included.
The application still starts successfully.
6. Documentation Policy
Documentation is part of the project, not optional extra work.

The purpose of documentation is to ensure that future development can continue without losing context.

Required Documentation Areas
Document	Responsibility
PROJECT_OVERVIEW.md	Project purpose, users, goals, scope, and non-goals
ARCHITECTURE.md	Technical structure, layers, boundaries, and dependencies
DEVELOPMENT_WORKFLOW.md	Rules for planning, implementing, testing, documenting, and committing
CURRENT_STATUS.md	Accurate record of completed work and immediate next step
DECISIONS.md	Important architectural and technical decisions
ROADMAP.md	Major planned modules and development sequence
modules/*.md	Detailed scope and acceptance criteria for each module
Documentation Update Rule
When starting a new chat or work session:

Read CURRENT_STATUS.md.
Read the related module document.
Review relevant architectural constraints.
Continue only from the documented next step.
When ending a work session:

Update CURRENT_STATUS.md.
Record decisions if needed.
Update module documentation with completed work and remaining work.
Commit completed changes with a clear message.
7. Security and Secret Handling
The following must never be committed to Git:

AI API keys
Passwords
Tokens
User-specific settings
Local application databases
Downloaded datasheets
User notes or annotations
Private test documents
Application logs containing sensitive information
Temporary PDF-render files
Python virtual environments
.env files containing secrets
API keys must be stored locally through a future secure settings mechanism or entered by the user at runtime.

Source code must never contain real API keys, even temporarily.

If a secret is accidentally added to Git, it must be considered exposed and replaced immediately.

8. Error Handling Policy
The application must fail safely and provide understandable messages to the user.

Examples of expected error cases:

Invalid or corrupted PDF files
Missing files
Permission errors
PDF rendering failures
Unsupported PDF features
Database access errors
Missing AI API configuration
AI provider connection errors
Network timeouts
Invalid user input
Rules:

Do not silently ignore important errors.
Do not expose raw technical tracebacks directly to normal users.
Log useful technical details where appropriate.
Show concise and understandable user-facing messages.
Optional service failures, such as AI or web search failures, must not crash the core application.
9. Definition of Done
A module task is considered complete only when all applicable items below are satisfied:

Its purpose and scope are documented.
Its implementation follows the architecture boundaries.
The required code is implemented.
Relevant tests are added or manual testing is performed.
Basic error conditions are handled.
The application still starts successfully.
Documentation reflects the actual result.
No secrets or generated local files are included.
The change is committed with a meaningful Git message.
CURRENT_STATUS.md identifies the next logical task.
A feature is not complete merely because code has been written.

10. Current Foundation Stage Rule
The Foundation / Documentation baseline and the Application Shell are complete (see docs/CURRENT_STATUS.md). The core documents below are in place and must be kept up to date as work progresses:

docs/PROJECT_OVERVIEW.md
docs/ARCHITECTURE.md
docs/DEVELOPMENT_WORKFLOW.md
docs/CURRENT_STATUS.md
docs/DECISIONS.md
docs/ROADMAP.md
docs/modules/*.md

Since the Application Shell is done, later modules (PDF service/viewer, selected pages, notes, AI) are being implemented incrementally. Each module must still follow the module workflow in this document, keep CURRENT_STATUS.md accurate, and respect the architecture boundaries (including the known AI deviation tracked in docs/ARCHITECTURE.md).