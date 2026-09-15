"""Native Persian/RTL PySide6 interface for Flyback Designer."""

from __future__ import annotations

from copy import deepcopy
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .defaults import SAMPLE_CORES, SAMPLE_PARTS, default_core, default_project
from .engine import (
    CalculationResult,
    CoreSpec,
    FlybackProject,
    OutputSpec,
    calculate,
)
from .persistence import FlybackProjectFileError, load_bundle, save_bundle


LOG = logging.getLogger("datasheet_studio.tools.flyback")


class FlybackDesignerDialog(QDialog):
    """Editable native DCM pre-design workspace."""

    def __init__(self, parent=None, *, prefill: dict | None = None,
                 controller_meta: dict | None = None) -> None:
        self._prefill = dict(prefill or {})
        self._controller_meta = dict(controller_meta or {})
        super().__init__(parent)
        self.setWindowTitle("طراح فلای‌بک — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1220, 780)
        self.setMinimumSize(980, 650)

        self._fields: dict[str, QDoubleSpinBox] = {}
        self._loading = False
        self._parts = tuple(deepcopy(SAMPLE_PARTS))
        self._cores_by_id = {
            core.core_id: deepcopy(core) for core in SAMPLE_CORES
        }
        self._last_result: CalculationResult | None = None
        self._recalculate_timer = QTimer(self)
        self._recalculate_timer.setSingleShot(True)
        self._recalculate_timer.setInterval(180)
        self._recalculate_timer.timeout.connect(self.recalculate)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        root.addWidget(self._build_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_input_tabs())
        splitter.addWidget(self._build_result_tabs())
        splitter.setSizes([520, 700])
        root.addWidget(splitter, 1)
        root.addLayout(self._build_actions())

        project = default_project()
        for key, value in self._prefill.items():
            if hasattr(project, key):
                setattr(project, key, value)
        self._apply_project(project, default_core())
        self.recalculate()
        self._show_controller_banner()

    def _show_controller_banner(self) -> None:
        meta = self._controller_meta
        if not meta:
            return
        status = meta.get("status", "")
        unknowns = meta.get("unknowns", "")
        text = (
            "کنترلرِ سند باز: {maker} {part} — نسخهٔ پروفایل {version} — وضعیت: {status}"
        ).format(
            maker=meta.get("manufacturer", ""),
            part=meta.get("part_number", ""),
            version=meta.get("profile_version", "؟"),
            status=status,
        )
        if unknowns:
            text += " — مقادیر مجهول: " + unknowns
        notice = QLabel(text)
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "QLabel { background: #eef4ff; color: #1c3d6e;"
            " border: 1px solid #b8cdf0; border-radius: 6px; padding: 6px; }"
        )
        row = QHBoxLayout()
        row.addWidget(notice)
        self.layout().insertLayout(1, row)

    def _build_header(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("طراح native منبع تغذیه فلای‌بک")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        notice = QLabel(
            "پیش‌طراحی DCM — نتیجه جایگزین تطبیق دیتاشیت، شبیه‌سازی، "
            "نمونه‌سازی و آزمون ایمنی نیست. تمام داده‌های داخلی نمونه و تأییدنشده‌اند."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "QLabel { background: #fff4ce; color: #5c4400; border: 1px solid #e6ca6a; "
            "border-radius: 6px; padding: 8px; }"
        )
        layout.addWidget(notice)
        return box

    def _build_input_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setMinimumWidth(430)

        source_page, source_form = self._form_page()
        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._schedule_recalculate)
        source_form.addRow("نام پروژه", self._name_edit)
        self._add_spin(source_form, "حداقل باس DC", "vin_min_v", 1, 1000, 2, " V")
        self._add_spin(source_form, "حداکثر باس DC", "vin_max_v", 1, 1500, 2, " V")
        self._add_spin(source_form, "فرکانس", "frequency_khz", 1, 1000, 2, " kHz")
        self._add_spin(source_form, "بازده فرضی", "efficiency_pct", 1, 99.9, 2, " %")
        self._add_spin(source_form, "دیوتی low-line", "duty", 0.01, 0.79, 4)
        self._add_spin(source_form, "حد جریان پیک", "current_limit_a", 0.01, 100, 3, " A")
        self._add_spin(source_form, "حد ولتاژ کلید", "switch_voltage_limit_v", 1, 5000, 1, " V")
        self._switch_type = QComboBox()
        self._switch_type.addItem("BJT داخلی/خارجی", "bjt")
        self._switch_type.addItem("MOSFET", "mosfet")
        self._switch_type.currentIndexChanged.connect(self._schedule_recalculate)
        source_form.addRow("نوع کلید", self._switch_type)
        self._add_spin(source_form, "VCE تخمینی", "vce_v", 0, 20, 3, " V")
        self._add_spin(source_form, "RDS(on)", "rdson_ohm", 0, 100, 4, " Ω")
        self._add_spin(source_form, "زمان صعود", "switch_rise_ns", 0, 10000, 1, " ns")
        self._add_spin(source_form, "زمان نزول", "switch_fall_ns", 0, 10000, 1, " ns")
        tabs.addTab(source_page, "منبع و کلید")

        magnetic_page, magnetic_form = self._form_page()
        self._core_combo = QComboBox()
        for core in self._cores_by_id.values():
            self._core_combo.addItem(core.name, core.core_id)
        self._core_combo.currentIndexChanged.connect(self._load_selected_core)
        magnetic_form.addRow("هسته نمونه", self._core_combo)
        self._add_spin(magnetic_form, "سطح مؤثر Ae", "ae_mm2", 0.01, 10000, 3, " mm²")
        self._add_spin(magnetic_form, "سطح پنجره Aw", "aw_mm2", 0.01, 100000, 3, " mm²")
        self._add_spin(magnetic_form, "طول مسیر le", "le_mm", 0.01, 10000, 3, " mm")
        self._add_spin(magnetic_form, "طول متوسط دور MLT", "mlt_mm", 0.01, 10000, 3, " mm")
        self._add_spin(magnetic_form, "حجم مؤثر Ve", "ve_mm3", 0.01, 1e7, 3, " mm³")
        self._add_spin(magnetic_form, "Bmax هسته", "bmax_t", 0.001, 2, 4, " T")
        self._add_spin(magnetic_form, "چگالی شار هدف", "b_target_t", 0.001, 2, 4, " T")
        self._add_spin(magnetic_form, "چگالی جریان", "current_density_a_mm2", 0.01, 30, 3, " A/mm²")
        self._add_spin(magnetic_form, "ضریب پرشدگی مجاز", "fill_factor", 0.01, 0.79, 4)
        self._add_spin(magnetic_form, "حداکثر قطر هر رشته", "max_strand_diameter_mm", 0.01, 5, 3, " mm")
        self._add_spin(magnetic_form, "نشتی فرضی", "leakage_pct", 0, 50, 3, " %")
        self._add_spin(magnetic_form, "چگالی تلفات هسته", "core_loss_density_kw_m3", 0, 100000, 2, " kW/m³")
        self._add_spin(magnetic_form, "عایق رزرو", "insulation_mm", 0, 10, 3, " mm")
        tabs.addTab(magnetic_page, "هسته و سیم‌پیچ")

        support_page, support_form = self._form_page()
        self._add_spin(support_form, "افت هر دیود پل", "bridge_drop_v", 0, 10, 3, " V")
        self._add_spin(support_form, "کلمپ بالاتر از باس", "clamp_above_bus_v", 0.01, 2000, 2, " V")
        self._add_spin(support_form, "ریپل کلمپ", "clamp_ripple_pct", 0.01, 99, 2, " %")
        self._add_spin(support_form, "مقاومت پایین TL431", "tl431_bottom_kohm", 0.01, 10000, 3, " kΩ")
        self._add_spin(support_form, "CTR اپتوکوپلر", "optocoupler_ctr_pct", 0.01, 1000, 2, " %")
        self._add_spin(support_form, "جریان LED اپتو", "optocoupler_led_current_ma", 0.01, 100, 3, " mA")
        self._add_spin(support_form, "افت LED اپتو", "optocoupler_vf_v", 0, 10, 3, " V")
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("یادداشت ساخت، پین‌های بوبین و الزامات ایمنی…")
        self._notes_edit.setMinimumHeight(130)
        support_form.addRow("یادداشت", self._notes_edit)
        tabs.addTab(support_page, "کلمپ و فیدبک")

        outputs_page = QWidget()
        outputs_layout = QVBoxLayout(outputs_page)
        self._outputs_table = QTableWidget(0, 4)
        self._outputs_table.setHorizontalHeaderLabels(
            ["نام", "ولتاژ (V)", "جریان (A)", "افت دیود (V)"]
        )
        self._outputs_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 4):
            self._outputs_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._outputs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._outputs_table.itemChanged.connect(self._schedule_recalculate)
        outputs_layout.addWidget(self._outputs_table, 1)
        output_actions = QHBoxLayout()
        add_output = QPushButton("+ افزودن خروجی")
        add_output.clicked.connect(self._add_output)
        remove_output = QPushButton("− حذف خروجی")
        remove_output.clicked.connect(self._remove_output)
        output_actions.addWidget(add_output)
        output_actions.addWidget(remove_output)
        output_actions.addStretch()
        outputs_layout.addLayout(output_actions)
        tabs.addTab(outputs_page, "خروجی‌ها")

        return tabs

    @staticmethod
    def _form_page() -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(14, 14, 14, 14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setVerticalSpacing(9)
        return page, form

    def _add_spin(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str = "",
    ) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        spin.valueChanged.connect(self._schedule_recalculate)
        form.addRow(label, spin)
        self._fields[key] = spin

    def _build_result_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        self._summary_table = self._result_table(["پارامتر", "مقدار"])
        self._summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self._summary_table, "خلاصه طراحی")

        self._windings_table = self._result_table(
            ["سیم‌پیچ", "دور", "پیک A", "RMS A", "رشته", "قطر mm", "مقاومت Ω", "تلفات W"]
        )
        self._windings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self._windings_table, "سیم‌پیچ‌ها")

        self._losses_table = self._result_table(["بخش", "تلفات"])
        self._losses_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self._losses_table, "تلفات و فیدبک")

        self._warnings = QTextBrowser()
        self._warnings.setOpenExternalLinks(False)
        tabs.addTab(self._warnings, "خطاها و هشدارها")
        return tabs

    @staticmethod
    def _result_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _build_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        open_button = QPushButton("باز کردن پروژه…")
        open_button.clicked.connect(self._open_project)
        save_button = QPushButton("ذخیره پروژه…")
        save_button.clicked.connect(self._save_project)
        reset_button = QPushButton("بازنشانی نمونه")
        reset_button.clicked.connect(self._reset_project)
        calculate_button = QPushButton("محاسبه")
        calculate_button.setDefault(True)
        calculate_button.clicked.connect(self.recalculate)
        close_button = QPushButton("بستن")
        close_button.clicked.connect(self.accept)
        actions.addWidget(open_button)
        actions.addWidget(save_button)
        actions.addWidget(reset_button)
        actions.addStretch()
        self._status = QLabel()
        actions.addWidget(self._status)
        actions.addWidget(calculate_button)
        actions.addWidget(close_button)
        return actions

    def _schedule_recalculate(self, *_args) -> None:
        if not self._loading:
            self._recalculate_timer.start()

    def _load_selected_core(self, index: int) -> None:
        if self._loading or index < 0:
            return
        selected_id = self._core_combo.itemData(index)
        selected = self._cores_by_id.get(selected_id)
        if selected is None:
            return
        self._loading = True
        try:
            for key in ("ae_mm2", "aw_mm2", "le_mm", "mlt_mm", "ve_mm3", "bmax_t"):
                self._fields[key].setValue(getattr(selected, key))
        finally:
            self._loading = False
        self._schedule_recalculate()

    def _add_output(self) -> None:
        if self._outputs_table.rowCount() >= 8:
            QMessageBox.information(self, "خروجی‌ها", "حداکثر هشت خروجی پشتیبانی می‌شود.")
            return
        self._append_output(OutputSpec(f"خروجی {self._outputs_table.rowCount() + 1}", 5, 0.5))
        self._schedule_recalculate()

    def _remove_output(self) -> None:
        if self._outputs_table.rowCount() <= 1:
            QMessageBox.information(self, "خروجی‌ها", "حداقل یک خروجی لازم است.")
            return
        row = self._outputs_table.currentRow()
        if row < 0:
            row = self._outputs_table.rowCount() - 1
        self._outputs_table.removeRow(row)
        self._schedule_recalculate()

    def _append_output(self, output: OutputSpec) -> None:
        row = self._outputs_table.rowCount()
        self._outputs_table.insertRow(row)
        values = [output.name, output.voltage_v, output.current_a, output.diode_drop_v]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._outputs_table.setItem(row, column, item)

    def _project_from_form(self) -> FlybackProject:
        outputs: list[OutputSpec] = []
        for row in range(self._outputs_table.rowCount()):
            def cell(column: int) -> str:
                item = self._outputs_table.item(row, column)
                return item.text().strip() if item else ""

            try:
                outputs.append(
                    OutputSpec(
                        name=cell(0) or f"خروجی {row + 1}",
                        voltage_v=float(cell(1)),
                        current_a=float(cell(2)),
                        diode_drop_v=float(cell(3)),
                    )
                )
            except ValueError as exc:
                raise ValueError(f"اعداد خروجی {row + 1} معتبر نیستند.") from exc

        value = lambda key: self._fields[key].value()
        return FlybackProject(
            name=self._name_edit.text().strip() or "پروژه بدون نام",
            vin_min_v=value("vin_min_v"),
            vin_max_v=value("vin_max_v"),
            frequency_khz=value("frequency_khz"),
            efficiency_pct=value("efficiency_pct"),
            duty=value("duty"),
            b_target_t=value("b_target_t"),
            current_density_a_mm2=value("current_density_a_mm2"),
            fill_factor=value("fill_factor"),
            current_limit_a=value("current_limit_a"),
            switch_voltage_limit_v=value("switch_voltage_limit_v"),
            switch_type=self._switch_type.currentData(),
            vce_v=value("vce_v"),
            rdson_ohm=value("rdson_ohm"),
            switch_rise_ns=value("switch_rise_ns"),
            switch_fall_ns=value("switch_fall_ns"),
            bridge_drop_v=value("bridge_drop_v"),
            leakage_pct=value("leakage_pct"),
            clamp_above_bus_v=value("clamp_above_bus_v"),
            clamp_ripple_pct=value("clamp_ripple_pct"),
            max_strand_diameter_mm=value("max_strand_diameter_mm"),
            insulation_mm=value("insulation_mm"),
            core_loss_density_kw_m3=value("core_loss_density_kw_m3"),
            tl431_bottom_kohm=value("tl431_bottom_kohm"),
            optocoupler_ctr_pct=value("optocoupler_ctr_pct"),
            optocoupler_led_current_ma=value("optocoupler_led_current_ma"),
            optocoupler_vf_v=value("optocoupler_vf_v"),
            notes=self._notes_edit.toPlainText(),
            outputs=outputs,
        )

    def _core_from_form(self) -> CoreSpec:
        value = lambda key: self._fields[key].value()
        index = self._core_combo.currentIndex()
        core_id = self._core_combo.itemData(index) or "custom"
        core_name = self._core_combo.currentText() or "هسته سفارشی"
        return CoreSpec(
            core_id=core_id,
            name=core_name,
            ae_mm2=value("ae_mm2"),
            aw_mm2=value("aw_mm2"),
            le_mm=value("le_mm"),
            mlt_mm=value("mlt_mm"),
            ve_mm3=value("ve_mm3"),
            bmax_t=value("bmax_t"),
            verified=False,
            source="مقادیر واردشده در فرم؛ تا زمان تطبیق دستی تأییدنشده.",
        )

    def _apply_project(self, project: FlybackProject, core: CoreSpec) -> None:
        self._loading = True
        try:
            self._cores_by_id[core.core_id] = deepcopy(core)
            self._name_edit.setText(project.name)
            for key in (
                "vin_min_v", "vin_max_v", "frequency_khz", "efficiency_pct", "duty",
                "b_target_t", "current_density_a_mm2", "fill_factor", "current_limit_a",
                "switch_voltage_limit_v", "vce_v", "rdson_ohm", "switch_rise_ns",
                "switch_fall_ns", "bridge_drop_v", "leakage_pct", "clamp_above_bus_v",
                "clamp_ripple_pct", "max_strand_diameter_mm", "insulation_mm",
                "core_loss_density_kw_m3", "tl431_bottom_kohm", "optocoupler_ctr_pct",
                "optocoupler_led_current_ma", "optocoupler_vf_v",
            ):
                self._fields[key].setValue(getattr(project, key))
            self._switch_type.setCurrentIndex(0 if project.switch_type == "bjt" else 1)
            self._notes_edit.setPlainText(project.notes)

            core_index = self._core_combo.findData(core.core_id)
            if core_index < 0:
                self._core_combo.addItem(core.name, core.core_id)
                core_index = self._core_combo.count() - 1
            self._core_combo.setCurrentIndex(core_index)
            for key in ("ae_mm2", "aw_mm2", "le_mm", "mlt_mm", "ve_mm3", "bmax_t"):
                self._fields[key].setValue(getattr(core, key))

            self._outputs_table.setRowCount(0)
            for output in project.outputs:
                self._append_output(output)
        finally:
            self._loading = False

    def recalculate(self) -> None:
        try:
            project = self._project_from_form()
            core = self._core_from_form()
        except ValueError as exc:
            self._show_errors((str(exc),))
            return
        result = calculate(project, core, self._parts)
        self._last_result = result
        if result.errors:
            self._show_errors(result.errors)
            return
        self._render_result(result)

    def _show_errors(self, errors: tuple[str, ...]) -> None:
        self._summary_table.setRowCount(0)
        self._windings_table.setRowCount(0)
        self._losses_table.setRowCount(0)
        html = "<h3 style='color:#b42318'>خطاهای ورودی</h3><ul>" + "".join(
            f"<li>{self._escape(error)}</li>" for error in errors
        ) + "</ul>"
        self._warnings.setHtml(html)
        self._status.setText("ورودی نامعتبر")
        self._status.setStyleSheet("color: #b42318; font-weight: 600;")

    def _render_result(self, result: CalculationResult) -> None:
        summary = [
            ("توان خروجی", f"{result.output_power_w:.3f} W"),
            ("توان ورودی فرضی", f"{result.input_power_w:.3f} W"),
            ("اندوکتانس مغناطیس‌کننده", f"{result.magnetising_inductance_h * 1e6:.3f} µH"),
            ("جریان پیک اولیه", f"{result.primary_peak_a:.4f} A"),
            ("تعداد دور اولیه", str(result.primary_turns)),
            ("ولتاژ بازتابی", f"{result.reflected_voltage_v:.3f} V"),
            ("دیوتی دمگنتیزاسیون", f"{result.demagnetisation_duty * 100:.2f} %"),
            ("چگالی شار پیک", f"{result.flux_density_t:.5f} T"),
            ("پرشدگی پنجره", f"{result.window_fill_ratio * 100:.2f} %"),
            ("گپ تخمینی", f"{result.air_gap_mm:.4f} mm"),
            ("AL هدف", f"{result.al_nh_turn2:.3f} nH/turn²"),
            ("تنش کلید", f"{result.switch_stress_v:.2f} V"),
            ("بازده تخمینی پس از تلفات", f"{result.estimated_efficiency_pct:.2f} %"),
            ("ریپل خروجی اول", f"{result.first_output_ripple_v:.4f} V"),
            ("عمق نفوذ مس", f"{result.skin_depth_mm:.4f} mm"),
        ]
        self._fill_two_column(self._summary_table, summary)

        windings = [("اولیه", result.primary)] + [
            (output.spec.name, output.winding) for output in result.outputs
        ]
        self._windings_table.setRowCount(len(windings))
        for row, (name, winding) in enumerate(windings):
            values = [
                name, winding.turns, f"{winding.peak_a:.4f}", f"{winding.rms_a:.4f}",
                winding.strands, f"{winding.wire_diameter_mm:.3f}",
                f"{winding.resistance_ohm:.4f}", f"{winding.copper_loss_w:.4f}",
            ]
            for column, value in enumerate(values):
                self._windings_table.setItem(row, column, QTableWidgetItem(str(value)))
        self._windings_table.resizeColumnsToContents()

        feedback = result.feedback
        losses = [
            ("مس", f"{result.copper_loss_w:.4f} W"),
            ("هسته", f"{result.core_loss_w:.4f} W"),
            ("پل ورودی", f"{result.bridge_loss_w:.4f} W"),
            ("هدایت کلید", f"{result.switch_conduction_loss_w:.4f} W"),
            ("سوئیچینگ کلید", f"{result.switch_switching_loss_w:.4f} W"),
            ("RCD", "نامعتبر" if result.snubber_power_w is None else f"{result.snubber_power_w:.4f} W"),
            ("RCD مقاومت", "—" if result.snubber_resistance_ohm is None else f"{result.snubber_resistance_ohm / 1000:.3f} kΩ"),
            ("RCD خازن", "—" if result.snubber_capacitance_f is None else f"{result.snubber_capacitance_f * 1e9:.3f} nF"),
            ("کل تلفات", f"{result.total_loss_w:.4f} W"),
            ("مقاومت بالای TL431", f"{feedback.top_resistor_kohm:.3f} kΩ"),
            ("مقاومت LED اپتو", f"{feedback.led_resistor_kohm:.3f} kΩ"),
            ("جریان کلکتور اپتو", f"{feedback.collector_current_ma:.3f} mA"),
        ]
        self._fill_two_column(self._losses_table, losses)

        if result.warnings:
            html = "<h3 style='color:#8a5a00'>هشدارهای طراحی</h3><ol>" + "".join(
                f"<li style='margin:6px'>{self._escape(warning)}</li>"
                for warning in result.warnings
            ) + "</ol>"
            self._status.setText(f"محاسبه شد — {len(result.warnings)} هشدار")
            self._status.setStyleSheet("color: #8a5a00; font-weight: 600;")
        else:
            html = "<h3 style='color:#137333'>خطای عددی یا هشدار فعال وجود ندارد.</h3>"
            self._status.setText("محاسبه شد")
            self._status.setStyleSheet("color: #137333; font-weight: 600;")
        html += (
            "<p><b>یادآوری:</b> نبود هشدار به معنی آماده‌بودن برای تولید یا "
            "تأیید ایمنی نیست.</p>"
        )
        self._warnings.setHtml(html)

    @staticmethod
    def _fill_two_column(table: QTableWidget, rows: list[tuple[str, str]]) -> None:
        table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(label))
            value_item = QTableWidgetItem(value)
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 1, value_item)
        table.resizeColumnsToContents()

    @staticmethod
    def _escape(text: str) -> str:
        return (
            str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    def _save_project(self) -> None:
        try:
            project = self._project_from_form()
            core = self._core_from_form()
        except ValueError as exc:
            QMessageBox.warning(self, "ذخیره پروژه", str(exc))
            return
        result = calculate(project, core, self._parts)
        if result.errors:
            QMessageBox.warning(self, "ذخیره پروژه", "ابتدا خطاهای ورودی را برطرف کنید.")
            return
        suggested = f"{project.name or 'flyback-design'}.flyback.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره پروژه فلای‌بک", suggested, "Flyback Project (*.flyback.json);;JSON (*.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".flyback.json"
        try:
            save_bundle(path, project, core, self._parts)
        except OSError as exc:
            QMessageBox.critical(self, "ذخیره پروژه", f"ذخیره فایل ممکن نشد:\n{exc}")
            return
        self._status.setText(f"ذخیره شد: {Path(path).name}")
        LOG.info("Flyback project saved: %s", path)

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "باز کردن پروژه فلای‌بک", "", "Flyback Project (*.flyback.json *.json);;All Files (*)"
        )
        if not path:
            return
        try:
            project, core, parts = load_bundle(path)
            validation = calculate(project, core, parts)
            if validation.errors:
                raise FlybackProjectFileError("؛ ".join(validation.errors))
        except FlybackProjectFileError as exc:
            QMessageBox.critical(self, "باز کردن پروژه", str(exc))
            return
        self._parts = parts or tuple(deepcopy(SAMPLE_PARTS))
        self._apply_project(project, core)
        self.recalculate()
        self._status.setText(f"باز شد: {Path(path).name}")
        LOG.info("Flyback project opened: %s", path)

    def _reset_project(self) -> None:
        answer = QMessageBox.question(
            self,
            "بازنشانی",
            "مقادیر فعلی با نمونه اولیه جایگزین شوند؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._parts = tuple(deepcopy(SAMPLE_PARTS))
        self._apply_project(default_project(), default_core())
        self.recalculate()
