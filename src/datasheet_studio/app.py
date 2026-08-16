"""Application entry point for Datasheet Studio."""

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.core.logging import setup_logging
from datasheet_studio.ui.main_window import MainWindow

LOG = logging.getLogger("datasheet_studio")


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    """Log uncaught exceptions so they appear in the Debug Log panel."""
    LOG.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main() -> int:
    """Create and run the Qt application."""
    setup_logging()
    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    # Load modern stylesheet
    style_file = Path(__file__).parent / "ui" / "style.qss"
    if style_file.exists():
        with open(style_file, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
