# Datasheet Studio

Datasheet Studio is a Windows desktop workspace for electronic-component
datasheets and engineering tools. It is implemented with Python and PySide6;
it is not a browser wrapper.

Current working features include PDF reading and navigation, selected pages,
notes, a local datasheet library, AI-provider integration, Symbol Creator with
DipTrace export, and the native Persian/RTL Flyback Designer.

## Run the Windows Application

When a verified Windows build has been produced, normal use starts by opening:

```text
dist-native/app.dist/DatasheetStudio.exe
```

No terminal or Python command is required after the Windows build has been
created. The build folder is intentionally not committed to Git. The current
repository does not yet claim that its packaged executable has passed the
release verification gate; see `docs/WINDOWS_BUILD.md`.

## Developer Setup

The project requires 64-bit Python 3.13.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,build]"
.venv\Scripts\python -m pytest -q
```

Build the Windows application with:

```powershell
.venv\Scripts\pyside6-deploy -c pysidedeploy.spec -f
```

## Documentation-First Workflow

Before changing behaviour, update or create the relevant Markdown module
contract under `docs/modules/`. The primary references are:

- `docs/PROJECT_OVERVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_STATUS.md`
- `docs/ROADMAP.md`
- `docs/DECISIONS.md`
- `docs/modules/TOOLS_FRAMEWORK.md`
- `docs/modules/FLYBACK_DESIGNER.md`

## Flyback Designer Boundary

The Flyback Designer is a native PySide6 tool with a pure Python numerical
engine. It does not embed or depend on the former HTML/JavaScript prototype.
It is a preliminary DCM design aid, not production approval. Bundled cores and
generic parts are illustrative and deliberately marked unverified.
