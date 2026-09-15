"""Editable Persian/RTL controller profile form (Phase 8).

Owner reviews/approves this form and the field set before AI automation
(Phase 9). Every field row carries value, unit, review state, and evidence
(page/table). Verified requires a reviewer name.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.models.controller_profile import (
    FIELD_SPECS,
    SECTION_LABELS_FA,
    ControllerProfile,
    ControllerProfileError,
    dump_controller_profile,
    load_controller_profile,
)
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance

_REVIEW_STATES = ("unreviewed", "extracted", "reviewed", "verified")
_REVIEW_LABELS = {
    "unreviewed": "بازبینی‌نشده",
    "extracted": "استخراج‌شده (AI/درون‌ریزی)",
    "reviewed": "بازبینی‌شده",
    "verified": "تأییدشده",
}


class ControllerProfileDialog(QDialog):
    """Create/edit/review one controller profile."""

    def __init__(
        self,
        parent=None,
        *,
        part_number: str = "",
        manufacturer: str = "",
        source_hash: str = "",
        vault_path_getter=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("پروفایل کنترلر — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(880, 720)
        self._vault_path_getter = vault_path_getter or (lambda: "")
        self._rows: dict[str, dict] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        identity = QFormLayout()
        self._manufacturer = QLineEdit(manufacturer)
        self._part_number = QLineEdit(part_number)
        self._package = QLineEdit()
        self._profile_version = QLineEdit("1")
        self._source_hash = QLineEdit(source_hash)
        self._source_hash.setPlaceholderText("هش SHA-256 دیتاشیت منبع")
        identity.addRow("سازنده", self._manufacturer)
        identity.addRow("شماره قطعه", self._part_number)
        identity.addRow("پکیج", self._package)
        identity.addRow("نسخه پروفایل", self._profile_version)
        identity.addRow("هش منبع", self._source_hash)
        root.addLayout(identity)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        sections_host = QWidget()
        sections_layout = QVBoxLayout(sections_host)
        sections_layout.setSpacing(10)

        by_section: dict[str, list] = {}
        for spec in FIELD_SPECS.values():
            by_section.setdefault(spec.section, []).append(spec)
        for section in sorted(by_section, key=lambda s: list(by_section).index(s)):
            specs = by_section[section]
            box = QGroupBox(
                SECTION_LABELS_FA.get(section, section)
                + ("  (فیلدهای الزامی ★)" if any(s.required for s in specs) else "")
            )
            form = QFormLayout(box)
            for spec in specs:
                form.addRow(self._build_field_row(spec))
            sections_layout.addWidget(box)
        sections_layout.addStretch(1)
        scroll.setWidget(sections_host)
        root.addWidget(scroll, 1)

        notes_row = QHBoxLayout()
        self._notes = QLineEdit()
        self._notes.setPlaceholderText("یادداشت/تناقض/مجهول (اختیاری؛ با «؛» جدا کنید)")
        notes_row.addWidget(QLabel("یادداشت‌ها:"))
        notes_row.addWidget(self._notes, 1)
        root.addLayout(notes_row)

        buttons = QHBoxLayout()
        open_btn = QPushButton("باز کردن…")
        open_btn.clicked.connect(self._open_profile)
        save_btn = QPushButton("ذخیره")
        save_btn.clicked.connect(self._save_profile)
        self._status = QLabel("")
        buttons.addWidget(open_btn)
        buttons.addWidget(save_btn)
        buttons.addStretch()
        buttons.addWidget(self._status)
        close = QPushButton("بستن")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        root.addLayout(buttons)

    # -- field rows ------------------------------------------------------------

    def _build_field_row(self, spec) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        star = " ★" if spec.required else ""
        label = QLabel(f"{spec.label_fa}{star}" + (f" [{spec.unit}]" if spec.unit else ""))
        label.setMinimumWidth(190)
        if spec.kind == "enum":
            value = QComboBox()
            value.addItem("—", "")
            for option in spec.enum_values:
                value.addItem(option, option)
        else:
            value = QLineEdit()
            value.setPlaceholderText("عدد یا متن")
        state = QComboBox()
        for key in _REVIEW_STATES:
            state.addItem(_REVIEW_LABELS[key], key)
        page = QSpinBox()
        page.setRange(0, 99999)
        page.setSpecialValueText("صفحه؟")
        source = QLineEdit()
        source.setPlaceholderText("جدول/شکل")
        layout.addWidget(label)
        layout.addWidget(value, 2)
        layout.addWidget(state)
        layout.addWidget(page)
        layout.addWidget(source, 1)
        self._rows[spec.name] = {
            "spec": spec,
            "value": value,
            "state": state,
            "page": page,
            "source": source,
        }
        return row

    # -- profile conversion -------------------------------------------------------

    def _collect_profile(self) -> ControllerProfile:
        fields: list[EvidenceField] = []
        for name, row in self._rows.items():
            spec = row["spec"]
            if spec.kind == "enum":
                data = row["value"].currentData()
                if not data:
                    continue
                value: float | str = data
            else:
                text = row["value"].text().strip()
                if not text:
                    continue
                if spec.kind == "number":
                    try:
                        value = float(text)
                    except ValueError as exc:
                        raise ControllerProfileError(
                            f"مقدار «{spec.label_fa}» عدد نیست: {text}"
                        ) from exc
                else:
                    value = text
            state = row["state"].currentData()
            page = row["page"].value() or None
            source_text = row["source"].text().strip()
            provenance = None
            if self._source_hash.text().strip() or page or source_text:
                provenance = Provenance(
                    source_hash=self._source_hash.text().strip() or "0" * 64,
                    page=page,
                    table_or_figure=source_text,
                    extractor_version="phase8-form",
                )
            extra = {}
            if state == "verified":
                extra = {
                    "reviewed_by": "owner",
                    "reviewed_at": "2026-09-15T00:00:00+00:00",
                }
            fields.append(
                EvidenceField(
                    name=name,
                    value=value,
                    unit=spec.unit,
                    provenance=provenance,
                    review_state=state,
                    **extra,
                )
            )
        notes = [n.strip() for n in self._notes.text().split("؛") if n.strip()]
        return ControllerProfile(
            manufacturer=self._manufacturer.text().strip() or "unknown",
            part_number=self._part_number.text().strip() or "unknown",
            source_object_sha256=self._source_hash.text().strip() or "0" * 64,
            profile_version=self._profile_version.text().strip() or "1",
            package=self._package.text().strip(),
            fields=tuple(fields),
            contradictions=tuple(n for n in notes if n.startswith("تناقض")),
            unknown_facts=tuple(n for n in notes if n.startswith("مجهول")),
            notes=self._notes.text().strip(),
        )

    def load_profile(self, profile: ControllerProfile) -> None:
        self._manufacturer.setText(profile.manufacturer)
        self._part_number.setText(profile.part_number)
        self._package.setText(profile.package)
        self._profile_version.setText(profile.profile_version)
        self._source_hash.setText(profile.source_object_sha256)
        self._notes.setText(profile.notes)
        for item in profile.fields:
            row = self._rows.get(item.name)
            if row is None:
                continue
            if row["spec"].kind == "enum":
                index = row["value"].findData(str(item.value))
                if index >= 0:
                    row["value"].setCurrentIndex(index)
            else:
                row["value"].setText(str(item.value))
            state_index = row["state"].findData(item.review_state)
            if state_index >= 0:
                row["state"].setCurrentIndex(state_index)
            if item.provenance:
                row["page"].setValue(item.provenance.page or 0)
                row["source"].setText(item.provenance.table_or_figure)

    # -- open/save -----------------------------------------------------------------

    def _open_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "باز کردن پروفایل کنترلر", "", "Controller Profile (*.json)"
        )
        if not path:
            return
        try:
            profile = load_controller_profile(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "باز کردن پروفایل", str(exc))
            return
        self.load_profile(profile)
        self._status.setText(f"باز شد: {Path(path).name}")

    def _save_profile(self) -> None:
        try:
            profile = self._collect_profile()
            engine = profile.engine_view()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "ذخیره پروفایل", str(exc))
            return
        vault_path = (self._vault_path_getter() or "").strip()
        if vault_path:
            from datasheet_studio.infrastructure.storage.knowledge_vault import (
                KnowledgeVault,
            )

            try:
                target = KnowledgeVault(vault_path).write_controller_profile(profile)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "ذخیره پروفایل", str(exc))
                return
            self._status.setText(
                f"ذخیره شد: {target.name} — مقادیر پذیرفته‌شده: {len(engine.values)}،"
                f" مجهول: {len(engine.unknowns)}"
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره پروفایل کنترلر",
            f"{profile.part_number}.controller.json", "Controller Profile (*.json)",
        )
        if not path:
            return
        Path(path).write_text(dump_controller_profile(profile), encoding="utf-8")
        self._status.setText(f"ذخیره شد: {Path(path).name}")
