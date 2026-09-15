# Datasheet Studio — Engineering Knowledge Base

**Status:** Planned architecture

**Depends on:** Local Datasheet Library, PDF Service, AI Assistant

**Supersedes:** treating `library.json` as the final large-library design

## 1. Purpose

Provide one portable, searchable, deduplicated store for datasheets, extracted
engineering facts, manufacturer catalogues, magnetic data, AI evidence, and the
projects that use them.

## 2. Storage Contract

```text
EngineeringLibrary/
├── library.toml                    # identity and schema version
├── library.sqlite                  # rebuildable index + FTS, not sole truth
├── objects/sha256/                 # immutable PDFs and source files by hash
├── records/
│   ├── datasheets/<maker>/<part>/<revision>/record.md
│   ├── components/<maker>/<part>/<revision>/profile.json
│   └── magnetics/<maker>/<family>/<part>/record.md
├── extracted/<source-hash>/
│   ├── full-text.md                # page markers preserved
│   ├── chunks.json
│   └── evidence.json
├── catalogs/<provider>/<pack-version>/
│   ├── manifest.md
│   └── normalized.json
├── projects/<project-id>/
│   ├── design.md
│   ├── design.json
│   └── runs/<run-id>/
└── ai-runs/<run-id>/
    ├── request.md
    ├── response.md
    └── metadata.json
```

All paths stored in records are relative to the library root. Original source
objects are never edited in place. Duplicate downloads resolve to the same
content hash while retaining all known source URLs and aliases.

## 3. Search Contract

SQLite FTS indexes:

- part number and aliases;
- manufacturer and document type;
- title, tags, notes, and summary;
- page-aware extracted text;
- normalized parameter names and values;
- core shape, material, dimensions, and compatible bobbins;
- projects that reference the record.

The UI offers one search grammar with filters such as `maker:`, `type:`,
`material:`, `core:`, and `verified:`. A missing or corrupt index must not lose
documents; the user can rebuild it from records and objects.

## 4. Provenance and Review States

Every engineering field supports:

```text
value, unit, min/typ/max, conditions, source_hash, page, table_or_figure,
extractor_version, imported_at, confidence, review_state, reviewed_by,
reviewed_at
```

Allowed review states are `unreviewed`, `extracted`, `reviewed`, `verified`, and
`rejected`. Automated import and AI extraction may produce `extracted` only.
`verified` requires explicit human comparison with the exact source revision.

## 5. Migration Direction

The current self-contained `library.json` library remains readable during the
transition. A runtime upgrade flow must:

1. make a recoverable backup;
2. hash and import each PDF without deleting the old copy;
3. convert summaries to Markdown records;
4. build the SQLite index;
5. report skipped or ambiguous items;
6. require explicit user confirmation before switching the active library.

No developer-only CLI migration may be required for normal operation.

## 6. Acceptance Criteria

- A library with thousands of PDFs remains responsive during search.
- Adding the same PDF twice creates no duplicate source object.
- Search results identify the matching page or field.
- Moving the library folder preserves every internal link.
- The database can be rebuilt without losing PDFs, profiles, notes, or review
  decisions.
- Backup/export is available in the desktop UI.
