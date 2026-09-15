"""Review round 3, item 1: real open/save must preserve the WHOLE project.

Reproduces the reported loss: after opening a project and saving it again
with the real buttons, ic_id, isolation_group, feedback, and custom
scenarios reverted to defaults.
"""

import json
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog

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


def _rich_project():
    return FlybackProject(
        name="rich",
        ic_id="DK125",
        switch_id="custom-switch",
        notes="keep me",
        outputs=[
            OutputSpec(
                "iso-rail", 5.0, 0.5, output_id="o9", isolation_group="iso2",
                priority=5, load_min_a=0.1, load_max_a=0.6,
                rectifier_id="SS16", capacitor_id="220uF-16V", feedback=False,
            )
        ],
        scenarios=[ScenarioSpec("custom-hot", bus_v=200.0, load_fraction=0.7,
                                ambient_c=85.0)],
    )


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_open_then_save_preserves_entire_project(qapp_instance, tmp_path, monkeypatch):
    target = tmp_path / "rich.flyback.json"
    original = _rich_project()
    target.write_text(
        json.dumps(bundle_to_dict(original, default_core(), ()), ensure_ascii=False),
        encoding="utf-8",
    )

    dialog = FlybackDesignerDialog()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    try:
        dialog._open_project_button.click()

        # The loss happens at form→project rebuild: everything the form does
        # not show must survive a save performed right after opening.
        dialog._save_project_button.click()

        reloaded, _core, _parts = bundle_from_dict(
            json.loads(target.read_text(encoding="utf-8"))
        )
        assert reloaded.ic_id == "DK125", "ic_id reverted to default dk124"
        assert reloaded.switch_id == "custom-switch"
        assert reloaded.notes == "keep me"
        out = reloaded.outputs[0]
        assert out.isolation_group == "iso2", "isolation reverted to main"
        assert out.feedback is False, "feedback reverted to True"
        assert out.output_id == "o9" and out.priority == 5
        assert out.load_min_a == 0.1 and out.load_max_a == 0.6
        assert out.rectifier_id == "SS16" and out.capacitor_id == "220uF-16V"
        assert [s.name for s in reloaded.scenarios] == ["custom-hot"], (
            "scenarios reverted to the default matrix"
        )
    finally:
        dialog.close()


def test_in_form_project_keeps_unshown_fields_after_open(qapp_instance, tmp_path, monkeypatch):
    target = tmp_path / "rich2.flyback.json"
    original = _rich_project()
    target.write_text(
        json.dumps(bundle_to_dict(original, default_core(), ()), ensure_ascii=False),
        encoding="utf-8",
    )
    dialog = FlybackDesignerDialog()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    try:
        dialog._open_project_button.click()
        rebuilt = dialog._project_from_form()
        assert rebuilt.ic_id == "DK125"
        assert rebuilt.outputs[0].isolation_group == "iso2"
        assert rebuilt.outputs[0].feedback is False
        assert [s.name for s in rebuilt.scenarios] == ["custom-hot"]
    finally:
        dialog.close()
