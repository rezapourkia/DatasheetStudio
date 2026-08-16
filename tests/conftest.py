"""Pytest configuration for Datasheet Studio."""

import os
import sys

# Force a headless Qt platform so tests run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make the src/ package importable during test collection.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp_instance():
    """Provide a shared QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app