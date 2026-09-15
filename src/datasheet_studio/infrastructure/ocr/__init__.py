"""Replaceable OCR boundary (Phase 7).

No OCR engine is bundled; adapters are plugged in when the owner selects one.
The protocol is deliberately tiny so a future Tesseract wrapper or an
AI-backed OCR service can implement it without touching extraction logic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OcrAdapter(Protocol):
    """OCR contract: one page of one PDF in, recognized text out."""

    name: str

    def is_available(self) -> bool: ...

    def ocr_page(self, pdf_path: str, page: int) -> str: ...


class NoOcrAdapter:
    """Default adapter: OCR is never available until an engine is wired."""

    name = "none"

    def is_available(self) -> bool:
        return False

    def ocr_page(self, pdf_path: str, page: int) -> str:  # pragma: no cover
        raise RuntimeError("هیچ موتور OCRای متصل نشده است.")
