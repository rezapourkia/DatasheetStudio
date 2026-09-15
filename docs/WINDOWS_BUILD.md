# Datasheet Studio — Windows Build

## Purpose

This document records the reproducible maintainer workflow for creating the
desktop build. End users do not need Python, a terminal, or these commands;
they launch `DatasheetStudio.exe` directly.

## Prerequisites

- Windows x64
- Python 3.13 x64
- Project virtual environment at `.venv`
- Editable project installation with the `dev` and `build` extras

## Build

```powershell
.venv\Scripts\python -m pip install -e ".[dev,build]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\pyside6-deploy -c pysidedeploy.spec -f
```

The distributable directory is:

```text
dist-native/app.dist/
```

The executable is:

```text
dist-native/app.dist/DatasheetStudio.exe
```

## Verification

1. Run the full automated test suite before packaging.
2. Launch the packaged executable.
3. Confirm the main four-panel workspace appears.
4. Open **Tools → Power Design → طراح فلای‌بک…**.
5. Confirm the default design calculates and warnings are visible.
6. Open **Tools → CAD → Symbol Creator…** without a PDF and confirm the
   application displays a safe information message.
7. Open a PDF and verify the viewer still renders a page.

## Generated Files

`build/`, `dist/`, `dist-native/`, and Nuitka build caches are local artifacts.
The maintained `pysidedeploy.spec` configuration is committed, while generated
build and distribution folders remain ignored.

The committed specification deliberately leaves `icon` and `python_path`
blank. `pyside6-deploy` resolves those values from the active environment and
may rewrite them as machine-specific absolute paths during a local build; such
generated path changes must not be committed.

The 2026-09-14 packaging attempt reached Nuitka's SCons C backend and failed;
no packaged executable is currently claimed as verified. Source startup and
automated tests are verified separately. Packaging remains a later release
gate rather than a prerequisite for the Phase 1 source baseline.
