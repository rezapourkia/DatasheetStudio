# Datasheet Studio — Tools Framework

## 1. Purpose

The Tools Framework provides one documented extension point for independent
engineering tools. The main window must discover registered tools and build the
**Tools** menu from their metadata instead of hard-coding one action per tool.

## 2. User-Facing Behaviour

- Available tools appear in the **Tools** menu.
- Tools are grouped by their declared category.
- Selecting a tool runs it with a current, read-only application context.
- A failure in one tool is reported to the user and must not close the main
  application.

## 3. Contract

Each tool provides:

- `id`: stable, unique machine identifier.
- `name`: user-facing menu label.
- `category`: user-facing grouping label.
- `description`: short status-tip text.
- `run(context)`: tool entry point.

`ToolContext` provides only the services and current document state that tools
are permitted to use. A tool may open its own dialog, but it must not reach into
private widgets or mutate the main window directly.

`ToolRegistry` provides deterministic registration, duplicate-ID rejection,
lookup, and category/name ordered listing.

## 4. Source Locations

```text
src/datasheet_studio/tools/
├── __init__.py
├── registry.py
├── symbol_creator_tool.py
└── flyback_designer/
```

The main window owns menu rendering and creates the current `ToolContext` when
an action is triggered. Tool-specific user interfaces stay with the tool or in
a dedicated UI module; business calculations must not be placed in the main
window.

## 5. Dependencies

- Python standard library for the registry.
- PySide6 only for tool-specific presentation and user-visible error dialogs.
- Existing Datasheet Studio services may be passed through `ToolContext`.

The registry itself must not require an open PDF, AI provider, network access,
or local library.

## 6. Acceptance Criteria

- The Tools menu is populated only from `ToolRegistry`.
- Symbol Creator remains available through the registry.
- Flyback Designer is available without opening a PDF.
- Duplicate tool IDs are rejected with a clear exception.
- Registry order and lookup are covered by unit tests.
- Existing application-shell menu tests continue to pass.

## 7. Known Limitations

This is an in-process plugin registry, not a third-party package loader. It does
not execute arbitrary downloaded code, scan external directories, or manage
plugin installation.

