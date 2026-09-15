"""Settings dialog for online search sources (Phase 6: DigiKey).

Credentials live in local ``QSettings`` only (same plain-text limitation as
the current AI keys; see ADR-009 pending secure storage).  The test
connection button runs the token flow through an injectable tester so the
dialog stays testable offline.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.infrastructure.web.digikey import DigiKeyCredentials

_SETTINGS_PREFIX = "onlineSources"


class _TestWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, tester: Callable[[], str], parent=None) -> None:
        super().__init__(parent)
        self._tester = tester

    def run(self) -> None:
        try:
            self.done.emit(self._tester())
        except Exception as exc:  # noqa: BLE001 - surface any failure as text
            self.failed.emit(str(exc))


class OnlineSourcesDialog(QDialog):
    """Enable/configure online sources; nothing is saved until «ذخیره»."""

    def __init__(
        self,
        parent=None,
        *,
        settings=None,
        connection_tester: Callable[[DigiKeyCredentials], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("منابع آنلاین — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(520)

        if settings is None:
            from PySide6.QtCore import QSettings

            settings = QSettings(APP_ORGANIZATION, APP_NAME)
        self._settings = settings
        self._connection_tester = connection_tester
        self._worker: _TestWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        notice = QLabel(
            "کلیدها فقط به‌صورت محلی ذخیره می‌شوند و هرگز به مخزن Git راه پیدا نمی‌کنند. "
            "اتصال واقعی DigiKey تا زمان تست با کلید معتبر، «آزمایش‌نشده» تلقی می‌شود."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "QLabel { background: #fff4ce; color: #5c4400; border: 1px solid #e6ca6a;"
            " border-radius: 6px; padding: 8px; }"
        )
        root.addWidget(notice)

        form = QFormLayout()
        self._digikey_enabled = QCheckBox("فعال‌سازی جست‌وجوی DigiKey")
        self._digikey_client_id = QLineEdit()
        self._digikey_client_id.setPlaceholderText("Client ID از developer.digikey.com")
        self._digikey_client_secret = QLineEdit()
        self._digikey_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._digikey_client_secret.setPlaceholderText("Client Secret")
        form.addRow(self._digikey_enabled)
        form.addRow("Client ID", self._digikey_client_id)
        form.addRow("Client Secret", self._digikey_client_secret)
        root.addLayout(form)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        buttons_row = QHBoxLayout()
        self._test_button = QPushButton("تست اتصال")
        self._test_button.clicked.connect(self._test_connection)
        self._save_button = QPushButton("ذخیره")
        self._save_button.clicked.connect(self._save)
        cancel = QPushButton("انصراف")
        cancel.clicked.connect(self.reject)
        buttons_row.addWidget(self._test_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self._save_button)
        buttons_row.addWidget(cancel)
        root.addLayout(buttons_row)

        self._load()

    # -- settings ------------------------------------------------------------

    def _load(self) -> None:
        self._digikey_enabled.setChecked(
            self._settings.value(f"{_SETTINGS_PREFIX}/digikeyEnabled", False, type=bool)
        )
        self._digikey_client_id.setText(
            str(self._settings.value(f"{_SETTINGS_PREFIX}/digikeyClientId", "") or "")
        )
        self._digikey_client_secret.setText(
            str(self._settings.value(f"{_SETTINGS_PREFIX}/digikeyClientSecret", "") or "")
        )

    def _save(self) -> None:
        self._settings.setValue(
            f"{_SETTINGS_PREFIX}/digikeyEnabled", self._digikey_enabled.isChecked()
        )
        self._settings.setValue(
            f"{_SETTINGS_PREFIX}/digikeyClientId", self._digikey_client_id.text().strip()
        )
        self._settings.setValue(
            f"{_SETTINGS_PREFIX}/digikeyClientSecret",
            self._digikey_client_secret.text().strip(),
        )
        self._settings.sync()
        self.accept()

    def current_credentials(self) -> DigiKeyCredentials:
        return DigiKeyCredentials(
            client_id=self._digikey_client_id.text().strip(),
            client_secret=self._digikey_client_secret.text().strip(),
        )

    # -- connection test --------------------------------------------------------

    def _test_connection(self) -> None:
        credentials = self.current_credentials()
        if not credentials.is_complete:
            self._status_label.setText("ابتدا Client ID و Client Secret را کامل کنید.")
            return
        if self._connection_tester is None:
            from datasheet_studio.infrastructure.web.digikey import DigiKeyProvider

            provider = DigiKeyProvider(lambda: credentials)
            tester = provider.test_connection
        else:
            tester = lambda: self._connection_tester(credentials)  # noqa: E731
        self._test_button.setEnabled(False)
        self._status_label.setText("در حال آزمایش اتصال…")
        self._worker = _TestWorker(tester, self)
        self._worker.done.connect(self._on_test_done)
        self._worker.failed.connect(self._on_test_failed)
        self._worker.start()

    def _on_test_done(self, message: str) -> None:
        self._test_button.setEnabled(True)
        self._status_label.setText(f"✅ {message}")

    def _on_test_failed(self, message: str) -> None:
        self._test_button.setEnabled(True)
        self._status_label.setText(f"❌ {message}")
