"""Review round 4: three remaining reproductions (374186c)."""

import json
import time
from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication, QFileDialog

from datasheet_studio.models.magnetics_catalog import CatalogValidationError
from datasheet_studio.services.library_migration import MigrationReport
from datasheet_studio.tools.flyback_designer.dialog import FlybackDesignerDialog
from datasheet_studio.tools.flyback_designer.engine import (
    FlybackProject,
    OutputSpec,
    ScenarioSpec,
)
from datasheet_studio.tools.flyback_designer.persistence import (
    bundle_from_dict,
    bundle_to_dict,
)
from datasheet_studio.tools.flyback_designer.defaults import default_core

from tests.unit.test_magnetics_catalog import material

NAN = float("nan")
INF = float("inf")


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _project(rows):
    return FlybackProject(
        outputs=[
            OutputSpec(name, 5.0 + index, 0.1, output_id=f"o{index}",
                       isolation_group=group, feedback=feedback,
                       priority=index)
            for index, (name, group, feedback) in enumerate(rows)
        ],
        scenarios=[ScenarioSpec("s1", bus_v=200.0)],
    )


def _open_with(monkeypatch, target, project):
    target.write_text(
        json.dumps(bundle_to_dict(project, default_core(), ()), ensure_ascii=False),
        encoding="utf-8",
    )
    dialog = FlybackDesignerDialog()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    dialog._open_project_button.click()
    return dialog


def test_deleting_first_output_keeps_second_output_identity(qapp_instance, tmp_path, monkeypatch):
    target = tmp_path / "del.flyback.json"
    dialog = _open_with(
        monkeypatch, target,
        _project([("A", "gA", False), ("B", "gB", True)]),
    )
    try:
        dialog._outputs_table.setCurrentCell(0, 0)  # select row 0 (A)
        dialog._remove_output_button.click()  # deletes the selected row

        dialog._save_project_button.click()
        reloaded, _c, _p = bundle_from_dict(json.loads(target.read_text(encoding="utf-8")))
        assert [o.name for o in reloaded.outputs] == ["B"]
        out = reloaded.outputs[0]
        assert out.output_id == "o1", "B inherited A's identity"
        assert out.isolation_group == "gB", "B inherited A's isolation"
        assert out.feedback is True, "B inherited A's feedback"
        assert out.priority == 1
    finally:
        dialog.close()


def test_delete_middle_add_new_and_save(qapp_instance, tmp_path, monkeypatch):
    target = tmp_path / "mid.flyback.json"
    dialog = _open_with(
        monkeypatch, target,
        _project([("A", "gA", False), ("B", "gB", True), ("C", "gC", False)]),
    )
    try:
        dialog._outputs_table.setCurrentCell(1, 0)  # select middle row (B)
        dialog._remove_output_button.click()
        dialog._add_output_button.click()  # fresh output with defaults
        dialog._save_project_button.click()

        reloaded, _c, _p = bundle_from_dict(json.loads(target.read_text(encoding="utf-8")))
        by_name = {o.name: o for o in reloaded.outputs}
        assert by_name["A"].isolation_group == "gA"
        assert by_name["C"].isolation_group == "gC" and by_name["C"].output_id == "o2"
        new = next(o for o in reloaded.outputs if o.name not in ("A", "C"))
        assert new.isolation_group == "main" and new.feedback is True  # defaults
    finally:
        dialog.close()


def test_pending_close_completes_via_real_thread_finished(qapp_instance, tmp_path, monkeypatch):
    from datasheet_studio.ui.dialogs.library_upgrade_dialog import (
        LibraryUpgradeDialog,
        _MigrationWorker,
    )

    from tests.unit.test_review_r3_close_button import make_v1

    source = make_v1(tmp_path)
    dialog = LibraryUpgradeDialog(str(source))
    try:
        report = MigrationReport(source_root="s", target_root="t")

        def slow_run(self):
            # result message is emitted while the thread keeps running
            self.progressed.emit(1, 1, "row")
            self.finished_ok.emit(report)
            time.sleep(0.5)

        monkeypatch.setattr(_MigrationWorker, "run", slow_run)
        target = tmp_path / "vault-t"
        dialog._target_edit.setText(str(target))
        finished_codes = []
        dialog.finished.connect(finished_codes.append)

        dialog._do_preview()  # real preview enables the start button
        dialog._start_button.click()  # the real start path wires everything
        assert _wait_until(lambda: dialog._report is not None), "result shown"
        dialog.reject()  # close requested while the thread truly runs
        assert finished_codes == [], "must not close while running"
        assert dialog._pending_close is True

        # ONLY the real QThread.finished signal may complete the close here.
        assert _wait_until(lambda: bool(finished_codes), timeout=4.0), (
            "dialog did not close after the real thread finished"
        )
    finally:
        if dialog._worker is not None:
            dialog._worker.wait(3000)
        dialog.close()


def test_material_bounds_must_be_finite():
    with pytest.raises(CatalogValidationError):
        material(freq_min_khz=NAN)
    with pytest.raises(CatalogValidationError):
        material(temp_max_c=INF)
