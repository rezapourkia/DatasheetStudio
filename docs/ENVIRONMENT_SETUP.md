# Datasheet Studio — Environment Setup

## Project Information

- Project name: Datasheet Studio
- Project path: `~/DatasheetStudio`
- Operating system: Windows
- Terminal: Git Bash
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
python main.py
```