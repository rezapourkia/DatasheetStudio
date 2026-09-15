# Datasheet Studio — Complete Document Text/OCR Coverage (Phase 7)

**Status:** Active module contract

**Parent contracts:** `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md` (§2
`extracted/<source-hash>/` layout, §3 page-aware search),
`docs/modules/KNOWLEDGE_BASE_SCHEMA.md`

**Plan reference:** Phase 7 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

Make "the full document text" a first-class, auditable artifact: every page
of every source PDF is extracted, classified, cached by content hash, and
indexed for page-aware search. A document can be called **complete** only
when every page is accounted for. Scanned pages are detected and routed
through a replaceable OCR boundary instead of being silently ignored.

## 2. Coverage Ledger

Per page, one of:

| Status | Meaning |
|---|---|
| `pending` | Not yet attempted |
| `extracted` | Embedded text found (≥ `MIN_SEARCHABLE_CHARS` significant characters) |
| `scanned` | Text-poor page — needs OCR |
| `ocr` | OCR adapter produced text for a previously scanned page |
| `failed` | Extraction raised (corrupt page, reader error); reason kept |

`DocumentCoverage.is_complete` is `True` only when every page is `extracted`
or `ocr`. **A "complete document" claim is impossible while any page is
`pending`, `scanned`, or `failed`** — enforced in code and tested.

The ledger (`coverage.json`) and normalized full text (`full-text.md`, one
`<!-- page:N -->` marker before each page's text) are stored under the vault
at `extracted/<source-hash>/`, addressed by content hash per the
knowledge-base layout. Extraction runs through `infrastructure/pdf`
(PyMuPDF stays isolated there).

## 3. Cache and Reuse

- Cached artifacts record `extractor_version` and `page_count`. Reopening a
  previously extracted source **reuses the cache** when the versions and page
  counts match — no re-extraction (tested).
- A version bump or a different page count forces re-extraction.
- Cancellation aborts before writing: the previous cache stays intact.
- Runs are incremental per page: pages already `extracted`/`ocr` in a
  compatible cache keep their text; only non-complete pages are reprocessed.
- Standalone use without a vault (no cache) is supported for the coverage
  dialog on any open PDF.

## 4. OCR Boundary

`infrastructure/ocr` defines the `OcrAdapter` protocol
(`is_available() -> bool`, `ocr_page(pdf_path, page) -> str`) and ships
`NoOcrAdapter` (always unavailable). No OCR engine is bundled in this phase —
the adapter is chosen/wired when the owner selects an engine (Tesseract or an
AI OCR service in a later decision). OCR is opt-in per run; adapter failures
leave the page `scanned` and are reported, never fatal.

## 5. Index Integration

After a run with an accepted vault, every `extracted`/`ocr` page's text is
pushed into the rebuildable index (`page_texts`), making the whole document
searchable page-by-page from the bottom strip (snippet + page number).
Missing vault/index simply skips indexing (standalone mode).

## 6. Desktop Surface

A registered tool (**Tools → Knowledge Base → پوشش متن سند…**) opens a
Persian RTL dialog for the currently open PDF: per-page status table
(صفحه/وضعیت/تعداد نویسه), overall completeness banner, «استخراج متن» with a
worker thread, progress bar, and cancellation; an OCR button appears only
when an adapter is available. Results are cached/indexed when a vault is
active.

## 7. Acceptance Tests

`tests/unit/test_text_extraction.py`, `tests/unit/test_extraction_dialog.py`:

1. mixed fixtures (searchable + scanned + failed page via injected reader
   error) produce the correct ledger and `is_complete is False`;
2. all-searchable document reaches `is_complete is True`;
3. second run reuses the cache (no re-extraction; counter-proven) and a
   version/page-count mismatch re-extracts;
4. cancellation mid-run raises and leaves the previous cache intact;
5. fake OCR adapter turns `scanned` → `ocr` and completes the document;
   `NoOcrAdapter` is unavailable and leaves pages `scanned`;
6. indexed vault: page text becomes searchable (page hit with page number);
7. dialog: table renders statuses, run populates coverage, cancel button
   wiring (offscreen).

## 8. Out of Scope (Phase 7)

- A real OCR engine (pending decision), chunking/evidence JSON artifacts
  (`chunks.json`, `evidence.json` — later phases), and OCR quality review
  UI.
