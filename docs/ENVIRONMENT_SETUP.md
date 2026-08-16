# Datasheet Studio — Environment Setup

## Project Information

- Project name: Datasheet Studio
- Project path: `~/DatasheetStudio`
- Operating system: Windows
- Terminal: Git Bash (or VS Code integrated terminal)
- Git branch: `main`

## Python Environment

- Python version: `3.13.3`
- Virtual environment: `.venv`
- PySide6 version: `6.11.1`
- PyMuPDF version: `1.28.2`

## Activate the Virtual Environment

From the project root, run:

```bash
source .venv/Scripts/activate
```

After activation, the terminal prompt should begin with:

```text
(.venv)
```

## Install Dependencies

Install the project in editable mode (this also installs the runtime dependencies declared in `pyproject.toml`):

```bash
python -m pip install -e .
```

Or install the core packages directly:

```bash
python -m pip install PySide6 PyMuPDF
```

## Verify the Installation

```bash
python --version
python -c "import PySide6; print(PySide6.__version__)"
python -c "import fitz; print(fitz.VersionBind)"
```

## Run the Application

From the project root:

```bash
python -m datasheet_studio.app
```

> The startup command is `python -m datasheet_studio.app`. Do not use `python main.py`; the project uses the `src/` layout and imports the `datasheet_studio` package.