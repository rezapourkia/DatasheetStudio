# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Contributor:** ZCode (Z.ai, GLM)

**Branch:** `feature/datasheet-to-design-v2`

**Active phase:** Phase 7 — `REVIEW`

## Completed Result

Phases 1–6 were accepted (Phase 5 implemented by OpenAI Codex, `f2215f4`,
re-verified by ZCode; Phase 6 included the owner-directed embedded-browser
correction, ADR-021). Phase 7 (complete document text/OCR coverage) is
implemented, tested, and pushed per `docs/modules/TEXT_EXTRACTION_COVERAGE.md`:

- `services/text_extraction.py` — page-by-page coverage ledger
  (`extracted` / `scanned` / `ocr` / `failed` with reasons); a document is
  `is_complete` only when every page is accounted for. Artifacts cached by
  content hash under the vault (`extracted/<hash>/coverage.json` +
  `full-text.md` with `<!-- page:N -->` markers); compatible caches are
  reused without re-extraction; cancellation never touches the previous
  cache.
- `infrastructure/ocr` — replaceable OCR boundary; `NoOcrAdapter` ships by
  default (no engine chosen yet — pending owner decision).
- Index integration — extracted page text is pushed into the rebuildable
  index so whole documents are searchable page-by-page from the bottom
  strip; the index is created on demand.
- Desktop surface: registered tool **Tools → Knowledge Base → پوشش متن
  سند…** — Persian RTL dialog with per-page status table, completeness
  banner, worker-thread extraction with progress and cancellation.

Recorded verification: full regression **277 passed in 67.13 s** (14 new
tests), compile check and offscreen startup smoke passed.

## Working Tree

Expected clean except ignored local artifacts (`build/`, `dist/`,
`dist-native/`, `.venv`, caches, crash reports, local PDFs). Never commit
those. Preserve any later uncommitted owner/agent work.

## Not Verified

- A real OCR engine (none selected yet — owner decision: e.g. Tesseract or
  an AI OCR service; the adapter boundary is ready).
- Coverage runs against the owner's real DK124/DK125/TMG0656 documents
  (Phase 7 review gate).
- Open items inherited from earlier gates: real DigiKey credentials, the
  owner's real-library migration/vault flows.
- `chunks.json` / `evidence.json` artifacts are intentionally out of scope
  (later phases).

## Next Permitted Action

Stop at the Phase 7 owner-review gate. The owner should open a
representative datasheet (DK124 / DK125 / TMG0656) and run
**Tools → Knowledge Base → پوشش متن سند…**, checking the ledger, the
completeness banner, cancellation, and that page text shows up in bottom-
strip search. After acceptance, the next phase is Phase 8 — controller
profile and evidence schema — starting with its own Markdown contract. Do
not start Phase 8 before that.

## Required Reading for the Next Contributor

1. `AGENTS.md` if present at the repository/workspace boundary
2. `docs/HANDOFF.md`, `docs/DEVELOPMENT_PLAN.md`, and `docs/PRODUCT_VISION.md`
3. `docs/modules/TEXT_EXTRACTION_COVERAGE.md` (Phase 7 contract)
4. `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`, `KNOWLEDGE_INDEX.md`,
   `LIBRARY_UPGRADE.md`, `ONLINE_ADAPTER_FRAMEWORK.md`
5. `docs/CURRENT_STATUS.md` (section 21 is the newest record) and
   `docs/WORK_LOG.md`
6. `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` (incl. ADR-021)

## Verification Rule

Do not repeat the results above as current facts without rerunning the
relevant checks in the new checkout. Do not infer contributor identity from
Git author; use commit trailers and the append-only work log.
