"""Symbol Creator dialog.

Scans the open datasheet for its packages (schematic symbol variants), lets the
user pick one, previews the full pinout table, and exports it as a CSV table
or as a ready-to-use DipTrace schematic-symbol library (``.elixml``).
"""

import csv
import os

from datasheet_studio.services.diptrace_export import (
    build_component_library,
    extract_part_number,
    sanitize_name,
    validate_pin_rows,
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SymbolCreatorDialog(QDialog):
    """Window for extracting package pinout tables from the open datasheet."""

    _HEADERS = [
        "Pin Number",
        "Pin Name",
        "Pin Type",
        "Alternate Functions",
        "Additional Functions",
    ]

    def __init__(
        self, parent, reader, document_path: str, document_title: str = ""
    ) -> None:
        super().__init__(parent)
        self._reader = reader
        self._document_path = document_path
        self._document_title = document_title
        self._packages: list[dict] = []
        self._all_pinouts: dict[str, list[dict]] = {}
        self._current_rows: list[dict] = []
        self._current_expected_pin_count: int | None = None
        self._loading_pin_table = False

        self.setWindowTitle("Symbol Creator — Datasheet Studio")
        self.resize(900, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel("Symbol Creator")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        root.addWidget(title)

        hint = QLabel(
            "Choose a package (symbol variant), review or correct its pin table, "
            "then export it as CSV or as a DipTrace schematic symbol (.elixml). "
            "DipTrace export is enabled only after the physical pins are valid."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        root.addWidget(hint)

        toolbar = QHBoxLayout()
        self._scan_button = QPushButton("🔍 Scan")
        self._scan_button.setToolTip("Scan the datasheet for packages")
        self._scan_button.clicked.connect(self._scan)
        toolbar.addWidget(self._scan_button)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888;")
        toolbar.addWidget(self._status_label)
        toolbar.addStretch()
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QVBoxLayout()
        left_label = QLabel("Packages (symbol variants):")
        left_label.setStyleSheet("font-weight: 600;")
        left.addWidget(left_label)
        self._package_list = QListWidget()
        self._package_list.itemSelectionChanged.connect(self._on_package_selected)
        left.addWidget(self._package_list, 1)
        left_container = QWidget()
        left_container.setLayout(left)
        splitter.addWidget(left_container)

        right = QVBoxLayout()
        right_label = QLabel("Pinout (editable review):")
        right_label.setStyleSheet("font-weight: 600;")
        right.addWidget(right_label)
        self._pin_table = QTableWidget(0, len(self._HEADERS))
        self._pin_table.setHorizontalHeaderLabels(self._HEADERS)
        self._pin_table.horizontalHeader().setStretchLastSection(True)
        self._pin_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self._pin_table.setAlternatingRowColors(True)
        self._pin_table.itemChanged.connect(self._on_pin_table_changed)
        right.addWidget(self._pin_table, 1)
        table_actions = QHBoxLayout()
        self._add_pin_button = QPushButton("Add pin")
        self._add_pin_button.setToolTip("Add a missing physical pin row")
        self._add_pin_button.clicked.connect(self._add_pin_row)
        self._add_pin_button.setEnabled(False)
        table_actions.addWidget(self._add_pin_button)
        self._remove_pin_button = QPushButton("Remove selected pin")
        self._remove_pin_button.setToolTip(
            "Remove an incorrect or duplicate table row after review"
        )
        self._remove_pin_button.clicked.connect(self._remove_selected_pin_rows)
        self._remove_pin_button.setEnabled(False)
        table_actions.addWidget(self._remove_pin_button)
        table_actions.addStretch()
        right.addLayout(table_actions)
        right_container = QWidget()
        right_container.setLayout(right)
        splitter.addWidget(right_container)

        splitter.setSizes([260, 640])
        root.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self._export_button = QPushButton("💾 Export CSV...")
        self._export_button.setToolTip(
            "Export the selected pin table as a CSV file"
        )
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._export_csv)
        bottom.addWidget(self._export_button)

        self._export_diptrace_button = QPushButton("🟦 Export DipTrace Symbol (.elixml)...")
        self._export_diptrace_button.setToolTip(
            "Generate a DipTrace Component Editor schematic symbol "
            "(.elixml) for the selected package"
        )
        self._export_diptrace_button.setEnabled(False)
        self._export_diptrace_button.clicked.connect(self._export_diptrace)
        bottom.addWidget(self._export_diptrace_button)

        bottom.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        bottom.addWidget(close_button)
        root.addLayout(bottom)

        self._scan()

    # ------------------------------------------------------------------
    # Scanning and display
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Scan the datasheet once and populate the package list."""
        self._status_label.setText("Scanning...")
        self._package_list.clear()
        self._pin_table.setRowCount(0)
        self._export_button.setEnabled(False)
        self._export_diptrace_button.setEnabled(False)
        self._add_pin_button.setEnabled(False)
        self._remove_pin_button.setEnabled(False)
        self._current_rows = []
        self._current_expected_pin_count = None
        self._all_pinouts = {}
        try:
            self._all_pinouts = self._reader.get_all_pinouts(self._document_path)
            self._packages = sorted(
                [
                    {
                        "package": package,
                        "pin_count": self._reader.package_pin_count(package, rows),
                    }
                    for package, rows in self._all_pinouts.items()
                    if rows
                ],
                key=lambda item: (item["pin_count"], item["package"]),
            )
        except Exception as exc:  # noqa: BLE001 - surface scan errors
            QMessageBox.critical(
                self, "Scan Failed", f"Could not scan the datasheet:\n{exc}"
            )
            self._status_label.setText("Scan failed")
            return

        for item in self._packages:
            _rows, errors = validate_pin_rows(
                self._all_pinouts[item["package"]], item["pin_count"]
            )
            state = "verified" if not errors else "needs review"
            entry = QListWidgetItem(
                f"{item['package']} — {item['pin_count']} pins ({state})"
            )
            entry.setData(Qt.ItemDataRole.UserRole, item["package"])
            entry.setData(Qt.ItemDataRole.UserRole + 1, item["pin_count"])
            self._package_list.addItem(entry)

        if not self._packages:
            hint = self._reader.extraction_hint(self._document_path)
            self._status_label.setText(hint or "No packages found in this datasheet.")
        else:
            self._status_label.setText(f"{len(self._packages)} package(s) found")

    def _on_package_selected(self) -> None:
        """Load and display the pinout of the selected package."""
        items = self._package_list.selectedItems()
        if not items:
            return
        package = items[0].data(Qt.ItemDataRole.UserRole)
        norm = package.replace(" ", "").replace("_", "").replace("-", "").upper()
        self._current_rows = [dict(row) for row in self._all_pinouts.get(norm, [])]
        self._current_expected_pin_count = int(
            items[0].data(Qt.ItemDataRole.UserRole + 1) or 0
        )
        self._populate_pin_table()
        self._add_pin_button.setEnabled(True)
        self._remove_pin_button.setEnabled(bool(self._current_rows))
        self._update_validation_status(package)

    def _populate_pin_table(self) -> None:
        """Refresh the editable table without treating it as user input."""
        self._loading_pin_table = True
        self._pin_table.setRowCount(len(self._current_rows))
        for r, row in enumerate(self._current_rows):
            values = [
                row.get("pin", ""),
                row.get("name", ""),
                row.get("type", ""),
                row.get("alternate_functions", ""),
                row.get("additional_functions", ""),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self._pin_table.setItem(r, c, cell)
        self._loading_pin_table = False

    def _rows_from_table(self) -> list[dict]:
        """Read the user-reviewed values back from the table."""
        rows: list[dict] = []
        keys = (
            "pin",
            "name",
            "type",
            "alternate_functions",
            "additional_functions",
        )
        for row_no in range(self._pin_table.rowCount()):
            row = {}
            for column, key in enumerate(keys):
                cell = self._pin_table.item(row_no, column)
                row[key] = cell.text().strip() if cell else ""
            rows.append(row)
        return rows

    def _on_pin_table_changed(self, _item: QTableWidgetItem) -> None:
        """Require a valid table before any export can be enabled."""
        if self._loading_pin_table:
            return
        self._current_rows = self._rows_from_table()
        items = self._package_list.selectedItems()
        package = items[0].data(Qt.ItemDataRole.UserRole) if items else "Package"
        self._remove_pin_button.setEnabled(bool(self._current_rows))
        self._update_validation_status(package)

    def _update_validation_status(self, package: str) -> None:
        """Display validation feedback and guard the two export actions."""
        _rows, errors = validate_pin_rows(
            self._current_rows, self._current_expected_pin_count
        )
        valid = bool(self._current_rows) and not errors
        self._export_button.setEnabled(valid)
        self._export_diptrace_button.setEnabled(valid)
        if valid:
            self._status_label.setText(
                f"{package}: {len(_rows)} physical pins verified"
            )
        else:
            summary = errors[0] if errors else "No pins found"
            self._status_label.setText(f"{package}: review required — {summary}")

    def _add_pin_row(self) -> None:
        """Append an editable row for a pin missing from the PDF extraction."""
        self._current_rows = self._rows_from_table()
        self._current_rows.append(
            {
                "pin": "",
                "name": "",
                "type": "",
                "alternate_functions": "",
                "additional_functions": "",
            }
        )
        self._populate_pin_table()
        row = self._pin_table.rowCount() - 1
        self._pin_table.setCurrentCell(row, 0)
        self._pin_table.editItem(self._pin_table.item(row, 0))
        self._update_validation_status(
            self._package_list.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
        )

    def _remove_selected_pin_rows(self) -> None:
        """Remove selected raw rows so a reviewed table can be de-duplicated."""
        selected_rows = sorted(
            {item.row() for item in self._pin_table.selectedItems()}, reverse=True
        )
        if not selected_rows:
            return
        self._current_rows = self._rows_from_table()
        for row in selected_rows:
            del self._current_rows[row]
        self._populate_pin_table()
        items = self._package_list.selectedItems()
        package = items[0].data(Qt.ItemDataRole.UserRole) if items else "Package"
        self._remove_pin_button.setEnabled(bool(self._current_rows))
        self._update_validation_status(package)

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def _export_csv(self) -> None:
        """Export the selected package's pin table as a CSV file."""
        if not self._current_rows:
            return
        self._current_rows = self._rows_from_table()
        items = self._package_list.selectedItems()
        package = (
            items[0].data(Qt.ItemDataRole.UserRole) if items else "symbol"
        )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Symbol CSV",
            os.path.join(os.path.dirname(self._document_path), f"{package}.csv"),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(self._HEADERS)
                for row in self._current_rows:
                    writer.writerow(
                        [
                            row.get("pin", ""),
                            row.get("name", ""),
                            row.get("type", ""),
                            row.get("alternate_functions", ""),
                            row.get("additional_functions", ""),
                        ]
                    )
            self._status_label.setText(f"Saved {package} CSV to {path}")
            self._log_debug(
                f"Symbol CSV exported: {path} ({len(self._current_rows)} pins)"
            )
        except OSError as exc:
            QMessageBox.critical(
                self, "Export Failed", f"Could not write the CSV file:\n{exc}"
            )

    # ------------------------------------------------------------------
    # DipTrace symbol export
    # ------------------------------------------------------------------

    def _component_name(self) -> str:
        """Best-effort component/part name for the symbol library.

        Prefers a part number found in the PDF file name, then the datasheet
        title; falls back to the sanitized file name.
        """
        stem = os.path.splitext(os.path.basename(self._document_path))[0]
        for raw in (stem, self._document_title):
            token = extract_part_number(raw)
            if token:
                return token
        return sanitize_name(stem, fallback="IC")

    def _export_diptrace(self) -> None:
        """Export the selected package as a DipTrace symbol library (.elixml)."""
        if not self._current_rows:
            return
        self._current_rows = self._rows_from_table()
        items = self._package_list.selectedItems()
        package = (
            items[0].data(Qt.ItemDataRole.UserRole) if items else "symbol"
        )
        component = self._component_name()

        default_name = (
            f"{component}_{sanitize_name(package, fallback='package')}.elixml"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export DipTrace Symbol",
            os.path.join(os.path.dirname(self._document_path), default_name),
            "DipTrace Component Library (*.elixml);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".elixml"):
            path += ".elixml"

        try:
            xml_text = build_component_library(
                self._current_rows,
                component_name=component,
                package=package,
                expected_pin_count=self._current_expected_pin_count,
            )
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(xml_text)
            self._status_label.setText(
                f"Saved DipTrace symbol for {package} "
                f"({len(self._current_rows)} pins)"
            )
            self._log_debug(
                f"DipTrace symbol exported: {path} "
                f"({len(self._current_rows)} pins)"
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not write the DipTrace symbol:\n{exc}",
            )

    def _log_debug(self, message: str) -> None:
        """Best-effort debug log entry (the parent window may not expose one)."""
        try:
            from datasheet_studio.core.logging import LOG

            LOG.info(message)
        except Exception:  # noqa: BLE001
            pass
