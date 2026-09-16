"""Review round 3, item 3: extraction deficiencies must stay visible.

Reproduces the report: (a) an unprocessed page's warning is overwritten by
the final candidates message; (b) model-declared contradictions vanish in
the merge.
"""

import json
import time
from pathlib import Path

import pymupdf

from PySide6.QtWidgets import QApplication

from datasheet_studio.services.controller_extraction import extract_complete
from datasheet_studio.ui.dialogs.ai_extraction_review_dialog import (
    AiExtractionReviewDialog,
)


def _wait_until(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_model_declared_contradictions_survive_the_merge():
    def chat(prompt: str) -> str:
        return json.dumps(
            {
                "manufacturer": "Linkage",
                "part_number": "DK124",
                "fields": [
                    {"name": "frequency_khz", "value": 65.0,
                     "unit": "kHz", "page": 1},
                ],
                "contradictions": [
                    "مدل: در متن دو مقدار متفاوت برای جریان حدی ذکر شده است."
                ],
                "unknown_facts": [],
            },
            ensure_ascii=False,
        )

    outcome = extract_complete(
        chat, part_number="DK124", page_texts={1: "text"},
        complete_pages=(1,), page_count=1, source_hash="a" * 64,
    )
    assert any(
        "جریان حدی" in c for c in outcome.result.contradictions
    ), "model-declared contradiction was dropped by the merge"


def test_unprocessed_page_warning_stays_in_final_status(qapp_instance, tmp_path):
    pdf = tmp_path / "two_page.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "DK124 controller frequency 65kHz text")
    doc.new_page()  # empty → unprocessed (scanned/pending in the ledger)
    doc.save(str(pdf))
    doc.close()

    def chat(prompt: str) -> str:
        return json.dumps(
            {
                "manufacturer": "Linkage",
                "part_number": "DK124",
                "fields": [
                    {"name": "frequency_khz", "value": 65.0,
                     "unit": "kHz", "page": 1},
                ],
                "contradictions": [],
                "unknown_facts": [],
            },
            ensure_ascii=False,
        )

    dialog = AiExtractionReviewDialog(
        pdf_path=str(pdf), ai_chat=chat, vault_path_getter=lambda: "",
    )
    try:
        dialog._consent.setChecked(True)
        dialog._run_button.click()
        assert _wait_until(lambda: dialog._table.rowCount() == 1)

        final = dialog._status.text()
        assert "۱" in final or "1" in final  # candidates were reported…
        assert "صفحهٔ ۲" in final or "صفحهٔ 2" in final or "۲" in final or "2" in final, (
            "the unprocessed page-2 warning was overwritten by the final message"
        )
        assert "نیست" in final and "حساب" in final
    finally:
        dialog.close()
