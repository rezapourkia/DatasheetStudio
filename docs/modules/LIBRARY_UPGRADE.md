# Datasheet Studio — Safe Library v1 → v2 Upgrade (Phase 4)

**Status:** Active module contract

**Parent contracts:** `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md` (§2 layout,
§5 migration direction), `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`,
`docs/modules/KNOWLEDGE_INDEX.md`

**Plan reference:** Phase 4 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

Move a v1 `library.json` library into the v2 knowledge-base vault from the
desktop UI, without ever deleting or rewriting the v1 library. The owner can
preview, run, inspect a report, cancel, roll back, and only then accept.

## 2. Non-Negotiable Safety Rules

1. The v1 folder is never modified: no file is moved, deleted, or rewritten.
   A precautionary copy of `library.json` is stored inside the new vault at
   `migration/backup-library.json`.
2. The v2 vault is a **new** folder (default: sibling of the v1 root, name
   `<v1name>-v2`, user-selectable). All v2 content is content-addressed and
   rebuildable.
3. Interruption (user cancel or unexpected error) removes the partial vault;
   the v1 library keeps working.
4. Rollback deletes only the v2 vault folder.
5. Final acceptance is explicit: it marks `accepted = true` in
   `library.toml` and stores the vault path in `QSettings`
   (`knowledgeBasePath`). The v1 panel keeps working during the transition;
   v2 becomes the single browsing surface in a later phase.

## 3. Vault Layout (written by migration)

```text
<vault>/
├── library.toml            # schema_version=2, identity, accepted flag
├── library.sqlite          # rebuildable Phase 3 index
├── objects/sha256/<hh>/<hash>.pdf
├── records/datasheets/<maker>/<part>/<rev>/record.md + record.json
└── migration/
    ├── backup-library.json
    ├── report.json
    └── report.md
```

- `record.json` is the Phase 2 versioned envelope (machine truth);
  `record.md` is the human-readable summary converted from v1.
- `library.toml` is written/read with stdlib only (manual writer,
  `tomllib` reader) and its identity fields validate against the Phase 2
  `LibraryIdentity` domain type.

## 4. Migration Semantics

Per v1 item, in order:

- file missing → **skipped** entry (reason recorded);
- not a valid PDF (PyMuPDF check in `infrastructure/pdf`) → **skipped**;
- SHA-256 already imported → **duplicate** entry: no second object, the item
  still gets its own document record referencing the same source hash;
- copy/read `PermissionError`-style `OSError` → **failure** entry, migration
  continues with the next item;
- empty part number (derived from file name) or empty manufacturer
  (defaulted) → recorded as **ambiguous** while still importing;
- record-path collision → unique suffix `-2`, `-3`, … .

After all items: the Phase 3 index is rebuilt from the document records and
`migration/report.{json,md}` are written. Unexpected exceptions abort the
whole run: the partial vault is deleted and `MigrationError` is raised.

Document mapping: kind `datasheet → datasheet`,
`application_note → application-note`, `software → other`; revision is
`migrated-1` (v1 has no revision data); summaries become `record.md`
content; tags are preserved.

## 5. Desktop UI (Persian, RTL)

**Library → ارتقای کتابخانه به نسخهٔ ۲…** opens `LibraryUpgradeDialog`:

1. **Preview** (worker thread): v1 item count, files found/missing, bytes to
   copy, chosen target folder.
2. **Run** (worker thread, cancellable): progress bar per item; cancel aborts
   and removes the partial vault.
3. **Report**: imported / duplicate / skipped / failed / ambiguous counts and
   itemized reasons; buttons: **تأیید نهایی و فعال‌سازی** (accept),
   **حذف v2 و بازگشت** (rollback), close.

No CLI step exists at any point.

## 6. Acceptance Tests

`tests/unit/test_knowledge_vault.py`,
`tests/unit/test_library_migration.py`,
`tests/unit/test_library_upgrade_dialog.py`:

1. vault layout, object dedup by hash, envelope round-trip, TOML identity,
   accept flag, rollback removes the vault;
2. migration success (v1 files and manifest byte-identical afterwards;
   records/index/report written; index answers a part-number query);
3. duplicate file → one object, two records, duplicate entry;
4. invalid PDF and missing file → skipped with reasons;
5. simulated `PermissionError` on copy → failure entry, migration continues;
6. cancellation mid-run → vault removed, v1 intact;
7. rollback after success → vault removed;
8. dialog: preview numbers render; report rendering; final acceptance writes
   `QSettings` (`knowledgeBasePath`) and marks the vault accepted
   (offscreen).

## 7. Out of Scope (Phase 4)

- Browsing/searching the v2 library in the main window (later phases).
- Importing manufacturer folders not registered in `library.json`
  (the v1 "reindex" behavior stays a v1 feature).
- Non-datasheet kinds beyond the documented mapping.
