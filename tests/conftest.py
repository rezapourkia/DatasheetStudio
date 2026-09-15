"""Pytest configuration for Datasheet Studio."""

import os
import sys

# Force a headless Qt platform so tests run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make the src/ package importable during test collection.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def isolated_qsettings(tmp_path_factory, qapp_instance):
    """Route every test QSettings to a temp INI file.

    Review finding (round 2): tests previously wrote to the user's real
    QSettings store (registry on Windows). QSettings() honors the default
    format and the organization/application names set on QApplication, so
    the whole suite (and the app code under test) resolves to an INI file
    under the pytest temp directory — the real user's settings stay
    untouched.
    """

    from PySide6.QtCore import QSettings

    from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION

    qapp_instance.setOrganizationName(APP_ORGANIZATION)
    qapp_instance.setApplicationName(APP_NAME)
    directory = tmp_path_factory.mktemp("qsettings")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(directory)
    )
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(directory)
    )
    yield directory


@pytest.fixture(scope="session")
def qapp_instance():
    """Provide a shared QApplication for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app