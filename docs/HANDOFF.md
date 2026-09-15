# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Contributor:** ZCode (Z.ai, GLM)

**Branch:** `feature/datasheet-to-design-v2`

**Active phase:** Phase 3 — `REVIEW`

## Completed Result

Phases 1–2 were accepted by the owner. Phase 3 (rebuildable SQLite/FTS index)
is implemented, tested, and pushed.

Delivered per `docs/modules/KNOWLEDGE_INDEX.md`:

- `src/datasheet_studio/infrastructure/storage/knowledge_index.py` —
  `KnowledgeIndex`: stdlib SQLite/FTS5 adapter over the Phase 2 domain
  records. One rowid-aligned FTS table per record kind; incremental
  upsert/remove; explicit transactions with rollback; atomic rebuild (temp
  file + `os.replace`); `recover()` for corrupt index files.
- Search: prefix-AND free terms (Persian supported), filters `maker:`,
  `type:`, `core:`, `material:`, `verified:`; hits grouped by kind with
  page/field context and highlighted snippets.
- SQLite is an index only (ADR-019): a test deletes the database file,
  rebuilds from records, and asserts identical results.
- No UI in this phase; the synchronous adapter must be called from a worker
  thread by the Phase 4/5 UI (documented in the contract §2).

Recorded verification: full regression **206 passed in 66.20 s** (19 new
tests). Performance fixture (1,500 documents / 6,000 fields / 3,000 pages):
build ≈ 0.2 s, queries ≤ 4 ms (development machine).

## Working-Tree Warning

The working tree is expected to be clean except ignored local artifacts
(`build/`, `dist/`, `dist-native/`, `nuitka-crash-report.xml`, test PDFs,
`__pycache__`, `.venv`, `*.rebuild-tmp`). Never commit those.

## Current Permitted Action

None automatically — Phase 3 sits at its owner review gate. The owner should
review **search syntax and result ordering** with representative part/core
queries (grammar and verified tokenizer notes in
`docs/modules/KNOWLEDGE_INDEX.md` §5–§6). After acceptance, the next phase is
Phase 4 — the safe Library v1 → v2 desktop upgrade. Do not start Phase 4
before that.

## Not Verified in Phase 3

- No desktop UI exercises the index (none exists yet).
- Worker-thread offload is a documented requirement, not a running
  integration.
- Timings come from the development machine only.

## Required Reading for the Next Contributor

1. `AGENTS.md` if present at the repository/workspace boundary
2. `docs/HANDOFF.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/modules/KNOWLEDGE_BASE_SCHEMA.md` and
   `docs/modules/KNOWLEDGE_INDEX.md`
5. `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md`
6. `docs/CURRENT_STATUS.md` (section 17 is the newest record)
7. `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` (ADR-019)

## Verification Rule

The next contributor must not claim the index or full test suite is verified
merely because this document says so. It must run the tests in the current
checkout and record the actual result.
