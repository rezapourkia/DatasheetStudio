"""Review round 3, item 2: the REAL close button must not abandon a worker.

Reproduces the report: clicking «بستن» while the migration worker runs
closes the dialog without requesting cancellation.
"""

from pathlib import Path

import pymupdf

from datasheet_studio.infrastructure.storage.library_store import LibraryStore
from datasheet_studio.ui.dialogs.library_upgrade_dialog import LibraryUpgradeDialog


def make_v1(tmp_path: Path) -> Path:
    root = tmp_path / "v1"
    store = LibraryStore.create(root, name="Close")
    pdf = tmp_path / "a.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "DK124")
    doc.save(str(pdf))
    doc.close()
    store.add_item_from_source(
        pdf, manufacturer_folder="M", manufacturer="M", part_number="P1"
    )
    return root


def test_real_close_button_cancels_instead_of_abandoning(qapp_instance, tmp_path):
    dialog = LibraryUpgradeDialog(str(make_v1(tmp_path)))
    try:
        assert dialog._close_button is not None

        class _FakeWorker:
            def __init__(self):
                self.cancel_requested = False

            def isRunning(self):
                return True

        finished_codes = []
        dialog.finished.connect(finished_codes.append)

        fake = _FakeWorker()
        dialog._worker = fake
        # route the worker's cancel through the dialog's event like the real one
        original_set = dialog._cancel_event.set
        dialog._cancel_event.set = lambda: (
            setattr(fake, "cancel_requested", True), original_set()
        )

        dialog._close_button.click()  # the REAL close button

        assert fake.cancel_requested, "close must request cancellation"
        assert dialog._pending_close is True
        assert finished_codes == [], "dialog must NOT be closed while running"

        # once the worker is done, the pending close completes
        dialog._worker = None
        dialog._maybe_finish_pending_close()
        assert finished_codes == [
            __import__("PySide6.QtWidgets", fromlist=["QDialog"]).QDialog.DialogCode.Rejected
        ], "dialog closes after the worker finishes"
    finally:
        dialog.close()
