"""Symbol Creator dialog.

Scans the open datasheet for its packages (schematic symbol variants), lets the
user pick one, previews the full pinout table, and exports it as a CSV table
or as a ready-to-use DipTrace schematic-symbol library (``.elixml``).
"""

import csv
import json
import os
import re

from datasheet_studio.services.diptrace_export import (
    build_component_library,
    extract_part_number,
    sanitize_name,
    validate_pin_rows,
)
from datasheet_studio.services.ai_service import AIServiceError

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QCheckBox,
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
    _AI_SCAN_CHAR_LIMIT = 120_000
    _AI_SCAN_CHUNK_CHAR_LIMIT = 40_000

    def __init__(
        self,
        parent,
        reader,
        document_path: str,
        document_title: str = "",
        ai_service=None,
        symbol_pages: list[int] | None = None,
    ) -> None:
        super().__init__(parent)
        self._reader = reader
        self._document_path = document_path
        self._document_title = document_title
        self._ai_service = ai_service
        self._symbol_pages = self._normalize_page_numbers(symbol_pages or [])
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
        self._selected_scan_checkbox = QCheckBox("Use selected pages only")
        self._selected_scan_checkbox.setToolTip(
            "Limit local scan and AI text extraction to selected pages."
        )
        self._selected_scan_checkbox.setChecked(bool(self._symbol_pages))
        self._selected_scan_checkbox.setEnabled(bool(self._symbol_pages))
        self._selected_scan_checkbox.setVisible(bool(self._symbol_pages))
        toolbar.addWidget(self._selected_scan_checkbox)
        self._scan_ai_button = QPushButton("AI Scan")
        self._scan_ai_button.setToolTip(
            "Use the configured AI provider to infer packages from the PDF text"
        )
        self._scan_ai_button.setEnabled(
            ai_service is not None
            and bool(getattr(ai_service, "api_key", "").strip())
        )
        self._scan_ai_button.clicked.connect(self._scan_ai)
        toolbar.addWidget(self._scan_ai_button)
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
        try:
            scan_pages = self._scan_pages()
            if scan_pages is not None and not scan_pages:
                QMessageBox.warning(
                    self,
                    "Symbol Scan",
                    "No selected pages were provided. Select pages in the main "
                    "window first, or uncheck this option.",
                )
                return
            pinouts = self._reader.get_all_pinouts(
                self._document_path, scan_pages=scan_pages
            )
            self._apply_scan_results(pinouts, source="local")
        except Exception as exc:  # noqa: BLE001 - surface scan errors
            QMessageBox.critical(
                self, "Scan Failed", f"Could not scan the datasheet:\n{exc}"
            )
            self._status_label.setText("Scan failed")

    def _scan_ai(self) -> None:
        """Scan the datasheet using the configured AI provider."""
        if self._ai_service is None:
            QMessageBox.warning(
                self, "AI Scan", "AI service is not configured for this session."
            )
            return
        if not bool(getattr(self._ai_service, "api_key", "").strip()):
            QMessageBox.warning(
                self,
                "AI Scan",
                (
                    "AI is configured but API key is missing.\n\n"
                    "Open AI settings and save a valid API key first."
                ),
            )
            return

        self._scan_button.setEnabled(False)
        self._scan_ai_button.setEnabled(False)
        self._status_label.setText("AI scan running...")
        self._package_list.clear()
        self._pin_table.setRowCount(0)
        self._export_button.setEnabled(False)
        self._export_diptrace_button.setEnabled(False)
        self._add_pin_button.setEnabled(False)
        self._remove_pin_button.setEnabled(False)
        try:
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()
        except Exception:
            pass
        try:
            scan_pages = self._scan_pages()
            if scan_pages is not None and not scan_pages:
                QMessageBox.warning(
                    self,
                    "AI Scan",
                    "No selected pages were provided. Select pages in the main "
                    "window first, or uncheck this option.",
                )
                return
            context = self._build_ai_context(scan_pages)
            response = self._ai_service.chat(
                [{"role": "user", "content": self._build_ai_prompt()}],
                context=context,
                tools=self._ai_tools_schema(),
                tool_executor=self._execute_ai_tool,
            )
            all_pinouts = self._parse_and_merge_ai_response(response)
            if not all_pinouts:
                self._log_debug("Tool-based AI scan returned no packages; falling back.")
                all_pinouts = self._scan_ai_fallback(scan_pages)
            if not all_pinouts:
                raise ValueError("No package data returned by the AI provider.")
            self._apply_scan_results(all_pinouts, source="ai")
            QMessageBox.information(
                self,
                "AI Scan",
                "AI scan completed. Review rows before export to ensure correctness.",
            )
        except AIServiceError as exc:
            self._log_debug(f"AI Scan failed: {exc}")
            QMessageBox.critical(self, "AI Scan Failed", f"AI provider failed:\n{exc}")
            self._status_label.setText("AI scan failed")
        except Exception as exc:  # noqa: BLE001 - user-facing error handling
            self._log_debug(f"AI Scan unexpected failure: {exc}")
            QMessageBox.critical(self, "AI Scan Failed", str(exc))
            self._status_label.setText("AI scan failed")
        finally:
            self._scan_button.setEnabled(True)
            self._scan_ai_button.setEnabled(
                bool(self._ai_service)
                and bool(getattr(self._ai_service, "api_key", "").strip())
            )

    def _scan_ai_fallback(self, scan_pages: list[int] | None) -> dict[str, list[dict]]:
        """Fallback AI scan when tool-based inference returns nothing."""
        chunks = self._collect_document_text_chunks_for_ai(scan_pages, one_shot=False)
        if not chunks:
            return {}
        merged: dict[str, list[dict]] = {}
        for chunk_index, (chunk_pages, chunk_text) in enumerate(chunks, 1):
            self._status_label.setText(
                f"AI fallback: chunk {chunk_index}/{len(chunks)} "
                f"({len(chunk_pages)} pages, {len(chunk_text)} chars)"
            )
            response = self._ai_service.chat(
                [{"role": "user", "content": self._build_ai_prompt(chunk_text)}]
            )
            if not isinstance(response, str) or not response.strip():
                continue
            try:
                self._merge_pinout_maps(merged, self._parse_ai_response(response))
            except Exception as exc:
                self._log_debug(
                    f"AI fallback chunk {chunk_index} parse failed ({exc}): "
                    f"{response[:400].replace(chr(10), ' ')}"
                )
        return merged

    def _scan_pages(self) -> list[int] | None:
        """Return the currently selected page scope, or None for full scan."""
        if not self._selected_scan_checkbox.isChecked():
            return None
        return sorted(self._symbol_pages)

    @staticmethod
    def _normalize_page_numbers(page_numbers: list[int]) -> list[int]:
        """Return sorted, unique, positive page numbers."""
        normalized: list[int] = []
        for raw in page_numbers:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                normalized.append(value)
        return sorted(set(normalized))

    def _collect_document_text_for_ai(self, scan_pages: list[int] | None = None) -> str:
        """Extract enough readable text for AI inference."""
        chunks = self._collect_document_text_chunks_for_ai(scan_pages, one_shot=True)
        text = "\n".join(text for _, text in chunks).strip()
        if not text:
            raise ValueError("No readable text was extracted from the datasheet.")
        return text

    def _build_ai_context(self, scan_pages: list[int] | None) -> str:
        """Build the compact context string passed to the AI service."""
        pages = scan_pages or []
        if not pages:
            return f"Document title: {self._document_title or 'Unknown'}"
        return (
            f"Document title: {self._document_title or 'Unknown'}\n"
            f"Selected pages: {', '.join(str(page) for page in pages)}"
        )

    def _ai_tools_schema(self) -> list[dict]:
        """Declare the tools the AI model may call during symbol extraction."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_page_text",
                    "description": (
                        "Return the extracted text of one selected page of the "
                        "current datasheet. Use this for local evidence when "
                        "the package layout is unclear."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {
                                "type": "integer",
                                "description": "1-based page number",
                            }
                        },
                        "required": ["page"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_packages",
                    "description": (
                        "Return the packages (symbol variants) found in the "
                        "selected datasheet pages, each with its pin count."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pinout",
                    "description": (
                        "Return the full pinout table for a package name such "
                        "as LQFP48 or WLP30. Use this to fetch the final rows "
                        "after identifying the package."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "package": {
                                "type": "string",
                                "description": "Package name, e.g. LQFP48",
                            }
                        },
                        "required": ["package"],
                    },
                },
            },
        ]

    def _execute_ai_tool(self, name: str, args: dict) -> dict:
        """Execute a tool requested by the AI and return a serializable result."""
        try:
            scan_pages = self._scan_pages()
            if name == "get_page_text":
                if self._reader is None:
                    return {"error": "reader unavailable"}
                if not self._document_path:
                    return {"error": "no document open"}
                page_number = int(args.get("page", 1))
                if scan_pages and page_number not in scan_pages:
                    return {"error": "page is outside the selected pages"}
                text = self._reader.get_page_text(self._document_path, page_number)
                return {"page": page_number, "text": text[:6000]}

            if name == "get_packages":
                packages = self._reader.get_all_pinouts(
                    self._document_path, scan_pages=scan_pages
                )
                items = [
                    {
                        "package": package,
                        "pin_count": self._reader.package_pin_count(package, rows),
                    }
                    for package, rows in packages.items()
                    if rows
                ]
                items.sort(key=lambda item: (item["pin_count"], item["package"]))
                return {"packages": items, "count": len(items)}

            if name == "get_pinout":
                package = str(args.get("package") or "").strip()
                if not package:
                    return {"error": "package is required"}
                rows = self._reader.get_all_pinouts(
                    self._document_path, scan_pages=scan_pages
                )
                for key, value in rows.items():
                    if self._normalize_package_key(key) == self._normalize_package_key(package):
                        return {"package": key, "count": len(value), "rows": value}
                return {"error": f"no pinout table found for package {package}"}

            return {"error": f"unknown tool: {name}"}
        except Exception as exc:
            self._log_debug(f"AI tool {name} failed: {exc}")
            return {"error": str(exc)}

    def _collect_document_text_chunks_for_ai(
        self, scan_pages: list[int] | None = None, one_shot: bool = False
    ) -> list[tuple[list[int], str]]:
        """Collect readable text chunks that are safe for AI inference."""
        document = self._reader.open(self._document_path)
        page_count = document.page_count
        if scan_pages is None:
            pages = list(range(1, page_count + 1))
        else:
            pages = [n for n in scan_pages if 1 <= n <= page_count]
        if not pages:
            return []

        chunk_size = self._AI_SCAN_CHAR_LIMIT if one_shot else self._AI_SCAN_CHUNK_CHAR_LIMIT
        chunks: list[tuple[list[int], str]] = []
        current_pages: list[int] = []
        current_parts: list[str] = []
        consumed = 0

        for page_number in pages:
            try:
                page_text = self._reader.get_page_text(
                    self._document_path, page_number
                ).strip()
            except Exception:
                page_text = ""
            if not page_text:
                continue
            block = f"===== Page {page_number} =====\n{page_text}\n"

            if len(block) > chunk_size and not current_pages:
                chunks.append(([page_number], block[:chunk_size]))
                continue

            if current_pages and consumed + len(block) > chunk_size:
                chunks.append((current_pages, "\n".join(current_parts).strip()))
                current_pages = []
                current_parts = []
                consumed = 0

            if len(block) > chunk_size:
                chunks.append(([page_number], block[:chunk_size]))
                continue

            current_pages.append(page_number)
            current_parts.append(block)
            consumed += len(block)

        if current_parts:
            chunks.append((current_pages, "\n".join(current_parts).strip()))
        return chunks

    @staticmethod
    def _merge_pinout_maps(
        base: dict[str, list[dict]], incoming: dict[str, list[dict]]
    ) -> dict[str, list[dict]]:
        """Merge AI package results and keep unique rows."""
        for package_key, rows in incoming.items():
            if not rows:
                continue
            existing_rows = base.setdefault(package_key, [])
            signature = {
                (
                    str(row.get("pin", "")).strip(),
                    str(row.get("name", "")).strip(),
                    str(row.get("type", "")).strip(),
                    str(row.get("alternate_functions", "")).strip(),
                    str(row.get("additional_functions", "")).strip(),
                )
                for row in existing_rows
            }
            for row in rows:
                candidate = (
                    str(row.get("pin", "")).strip(),
                    str(row.get("name", "")).strip(),
                    str(row.get("type", "")).strip(),
                    str(row.get("alternate_functions", "")).strip(),
                    str(row.get("additional_functions", "")).strip(),
                )
                if candidate in signature:
                    continue
                existing_rows.append(row)
                signature.add(candidate)
        return base

    def _parse_and_merge_ai_response(self, response_text: str) -> dict[str, list[dict]]:
        """Parse AI JSON output and normalize it into package rows."""
        if not isinstance(response_text, str) or not response_text.strip():
            return {}
        try:
            return self._parse_ai_response(response_text)
        except Exception as exc:
            self._log_debug(
                f"AI parse failed ({exc}): {response_text[:400].replace(chr(10), ' ')}"
            )
            return {}

    def _build_ai_prompt(self) -> str:
        """Build a strict prompt that enforces machine-readable JSON output."""
        return (
            "You are a datasheet parser.\n"
            "Use the available tools to inspect the selected datasheet pages "
            "and extract every package symbol variant and its pinout.\n"
            "Do not stop after the first package. If multiple variants exist, "
            "return all of them.\n\n"
            "Return JSON only, no markdown, with the exact schema:\n"
            '{"packages":[{"package":"LQFP48","pins":[{"pin":"1","name":"PA0",'
            '"type":"IO","alternate_functions":"AF0=I2C1","additional_functions":""}]}]}\n\n'
            "Rules:\n"
            "1) include one entry per package variant\n"
            "2) package should be a short normalized label (e.g. SO8N, QFN20, LQFP48)\n"
            "3) each pin row must include keys: pin, name, type, "
            "alternate_functions, additional_functions\n"
            "4) use empty strings for unknown fields\n"
            "5) do not output text outside JSON\n\n"
            f"Document title: {self._document_title or 'Unknown'}\n\n"
        )

    def _extract_ai_payload(self, response_text: str) -> dict | list:
        """Extract JSON object/list from model output."""
        raw = response_text.strip()
        if not raw:
            raise ValueError("AI response is empty.")
        if raw.startswith("```"):
            match = re.search(
                r"```(?:json)?\s*(.*?)```",
                raw,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if match:
                raw = match.group(1).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            for index, char in enumerate(raw):
                if char not in "[{":
                    continue
                try:
                    parsed, _ = decoder.raw_decode(raw[index:])
                    return parsed
                except json.JSONDecodeError:
                    continue

            fenced = re.search(r"\{.*\}|\[.*\]", raw, flags=re.DOTALL)
            if not fenced:
                raise ValueError("AI response did not contain a valid JSON payload.")
            return json.loads(fenced.group(0))

    def _normalize_package_key(self, package: str) -> str:
        """Normalize package names for internal matching."""
        return re.sub(r"[\s_-]", "", (package or "").upper())

    def _coerce_pin_row(self, raw: dict) -> dict:
        """Ensure each row contains all required keys."""
        return {
            "pin": str(
                raw.get("pin") or raw.get("pin_number") or raw.get("number") or ""
            ).strip(),
            "name": str(
                raw.get("name")
                or raw.get("pin_name")
                or raw.get("signal")
                or ""
            ).strip(),
            "type": str(
                raw.get("type") or raw.get("io") or raw.get("direction") or ""
            ).strip(),
            "alternate_functions": str(
                raw.get("alternate_functions")
                or raw.get("alternate")
                or raw.get("alternate_function")
                or ""
            ).strip(),
            "additional_functions": str(
                raw.get("additional_functions")
                or raw.get("additional")
                or raw.get("description")
                or raw.get("details")
                or ""
            ).strip(),
        }

    def _parse_ai_response(self, response_text: str) -> dict[str, list[dict]]:
        """Convert AI JSON output into local package->pins mapping."""
        parsed = self._extract_ai_payload(response_text)
        if isinstance(parsed, dict) and "packages" in parsed:
            package_entries = parsed["packages"]
        else:
            package_entries = parsed

        if not isinstance(package_entries, list):
            raise ValueError("AI response schema is invalid.")

        pinouts: dict[str, list[dict]] = {}
        for item in package_entries:
            if not isinstance(item, dict):
                continue
            package = str(
                item.get("package")
                or item.get("name")
                or item.get("variant")
                or ""
            ).strip()
            if not package:
                continue

            rows = item.get("pins") or item.get("pinout") or []
            if not isinstance(rows, list):
                continue
            pinouts[self._normalize_package_key(package)] = [
                self._coerce_pin_row(row)
                for row in rows
                if isinstance(row, dict)
            ]

        return {key: rows for key, rows in pinouts.items() if rows}

    def _apply_scan_results(self, pinouts: dict[str, list[dict]], source: str) -> None:
        """Populate package list and state from scan results."""
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

        self._all_pinouts = {
            self._normalize_package_key(name): list(rows)
            for name, rows in pinouts.items()
            if rows
        }
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

        for item in self._packages:
            _rows, errors = validate_pin_rows(
                self._all_pinouts[item["package"]], item["pin_count"]
            )
            state = (
                "AI inferred" if source == "ai" and not errors else ("needs review" if errors else "verified")
            )
            entry = QListWidgetItem(
                f"{item['package']} — {item['pin_count']} pins ({state})"
            )
            entry.setData(Qt.ItemDataRole.UserRole, item["package"])
            entry.setData(Qt.ItemDataRole.UserRole + 1, item["pin_count"])
            self._package_list.addItem(entry)

        if not self._packages:
            hint = self._reader.extraction_hint(self._document_path)
            self._status_label.setText(
                hint
                or (
                    "AI did not extract any package variants."
                    if source == "ai"
                    else "No packages found in this datasheet."
                )
            )
        else:
            self._status_label.setText(
                f"{len(self._packages)} package(s) found"
                + (" (AI inferred)" if source == "ai" else "")
            )

    def _on_package_selected(self) -> None:
        """Load and display the pinout of the selected package."""
        items = self._package_list.selectedItems()
        if not items:
            return
        package = items[0].data(Qt.ItemDataRole.UserRole)
        norm = self._normalize_package_key(package)
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
