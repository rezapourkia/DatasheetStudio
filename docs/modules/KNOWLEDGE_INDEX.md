# Datasheet Studio — Knowledge-Base Index (Phase 3)

**Status:** Active module contract

**Parent contract:** `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md` (§3 search
contract), schema in `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`

**Plan reference:** Phase 3 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

A rebuildable SQLite/FTS5 index over the durable knowledge-base records.
SQLite is an index and transaction layer only — Markdown/JSON record files
and source objects remain the sole durable truth (ADR-019). Deleting
`library.sqlite` must never lose data; everything in it can be rebuilt from
records.

Implementation: `src/datasheet_studio/infrastructure/storage/knowledge_index.py`
(stdlib `sqlite3` only; no new dependency; FTS5 verified available in the
bundled SQLite 3.49.1, including Persian text).

## 2. Threading and UI Rule

The adapter is synchronous and single-connection. The desktop UI must call
`rebuild`/`search` from a worker thread (never the GUI thread); the Phase 5
search strip and Phase 4 migration UI own that integration. This phase ships
no UI.

## 3. Index Layout

Rowid-aligned FTS5 tables (no triggers; all writes go through the adapter):

```text
meta                 index_version
sources              sha256 PK, size, media type, filename, imported_at
documents            record_path UNIQUE, maker, part, type, revision, …
components           (maker, part, profile_version) UNIQUE
magnetics            (maker, family, kind, designation) UNIQUE
aliases / tags       per owner table + rowid
fields               owner + name/unit/value/min-typ-max/review_state/page
page_texts           (source_hash, page) PK, extracted text
fts_docs/fts_fields/fts_pages   FTS5, rowid == owning table rowid
```

## 4. Public API

- `KnowledgeIndex.open(path)` — open or create; raises `IndexCorruptError`
  when the file is not a usable database.
- `recover(path, records, page_texts)` — delete the broken file and rebuild.
- `upsert_*` / `remove_document(record_path)` — incremental maintenance.
- `add_page_text(source_hash, page, text)` — page-aware extracted text.
- `rebuild(records, page_texts)` — **atomic**: builds into a temp file and
  `os.replace`s it; returns `IndexStats`. Never leaves a half-written index.
- `transaction()` — context manager; a failed statement rolls the whole batch
  back (tested).
- `search(query, kinds=..., limit=...)` — returns `SearchHit`s ordered by
  FTS5 rank (bm25) with deterministic tie-breaks (rowid, page).
- `stats()` / `check_integrity()`.

## 5. Query Grammar

Free terms are prefix-matched and AND-combined (`dk 124` ≈ `"dk"* AND
"124"*`), matching partial part numbers and Persian words (unicode61
tokenizer). Filters:

| Filter | Applies to | Meaning |
|---|---|---|
| `maker:<text>` | documents/components | manufacturer contains text |
| `type:<doc-type>` | documents | exact document type (`datasheet`, …) |
| `core:<text>` | magnetics | family or designation contains text |
| `material:<text>` | fields | `material*` field values contain text |
| `verified:yes` / `verified:no` | fields | review state is / is not `verified` |

Hits are grouped by kind in a fixed order (document, component, magnetics,
field, page) and each group is rank-ordered. Every hit carries a `ref`
identity (e.g. `record_path`, `sha256`, page number) plus a highlighted
`snippet`, so results identify the matching page or field.

Tokenizer note (verified behavior): `unicode61` treats `DK124` as one token,
so `dk1` matches but the bare suffix `124` does not — quote-free terms are
whitespace tokens and there is no quoted-phrase support.

## 6. Acceptance Tests

`tests/unit/test_knowledge_index.py`:

1. create/upsert/delete lifecycle and unique-key conflicts;
2. transaction rollback leaves the index unchanged;
3. atomic rebuild: equivalent search results after deleting the file and
   rebuilding from the same records (incl. page and field snippets);
4. corruption recovery from a garbage file;
5. query grammar: free terms, each filter, combined filters, unknown filter
   ignored per contract, empty query returns ranked overview;
6. performance: a synthetic library (≈1,500 documents, 6,000 fields, 3,000
   pages) rebuilds and answers representative queries with recorded timings
   inside asserted budgets (build < 90 s, query < 2 s each). Recorded result
   on the development machine (2026-09-15): build ≈ 0.2 s; part-number,
   field-filter, and page queries each ≤ 4 ms.

## 7. Out of Scope (Phase 3)

- Any UI (Phase 4/5).
- Reading/writing the v2 library folder layout or migrating `library.json`
  (Phase 4).
- OCR/text-extraction pipelines (Phase 7) — page text arrives through
  `add_page_text` only.
