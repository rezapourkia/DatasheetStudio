# Datasheet Studio — Knowledge-Base Domain Schema (Phase 2)

**Status:** Active module contract

**Parent contract:** `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md` (storage
layout and search contract)

**Plan reference:** Phase 2 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

Define the versioned, validated domain types for the engineering knowledge
base before any storage, index, or UI migration is built. Phase 2 delivers
types, validation, canonical serialization, and content hashing only. It does
not change the current library UI and does not move user files.

Implementation: `src/datasheet_studio/models/knowledge_base.py` (domain types,
Qt-free, network-free) and `src/datasheet_studio/services/knowledge_hash.py`
(streaming SHA-256 and record digests).

## 2. Record Types

| Kind string | Type | Purpose |
|---|---|---|
| `source-object` | `SourceObject` | One immutable file identified by SHA-256 |
| `document-revision` | `DocumentRevision` | A datasheet revision bound to one source object |
| `component-profile` | `ComponentProfile` | Engineering facts for one component revision |
| `magnetics-record` | `MagneticsRecord` | Core/core-set/material/bobbin records |
| `library-identity` | `LibraryIdentity` | `library.toml` identity and schema version |

Every engineering fact is an `EvidenceField` carrying `Provenance`:

```text
name, value, unit, value_min/value_typ/value_max, conditions,
source_hash, page, table_or_figure, extractor_version, imported_at,
confidence, review_state, reviewed_by, reviewed_at
```

## 3. Review States

Allowed states: `unreviewed`, `extracted`, `reviewed`, `verified`,
`rejected` (from `ENGINEERING_KNOWLEDGE_BASE.md` §4).

Rules enforced by validation:

- `verified` requires non-empty `reviewed_by` and `reviewed_at` (ISO-8601).
- `reviewed_by`/`reviewed_at` may only appear on human review states
  (`reviewed`, `verified`, `rejected`).
- Automated import and AI extraction may assign at most `extracted`
  (`is_automated_assignable()`); promoting to `reviewed`/`verified` is a
  human-only operation performed by future UI, never by parsing code.
- `confidence` is `None` or a finite float in `[0, 1]`.

## 4. Validation Rules

- `source_hash` must be 64 lowercase hex characters (SHA-256).
- `page` is `None` or an integer `>= 1`.
- `imported_at`, `reviewed_at`, and LibraryIdentity timestamps accept
  ISO-8601 strings (a trailing `Z` is normalized to `+00:00`).
- `size_bytes >= 0`; `original_filename` is a bare file name (no `/`, `\`,
  or drive letter).
- Numeric `value_min <= value_typ <= value_max` when the provided subset is
  comparable.
- Alias `kind` is one of `part-number`, `ordering-code`, `oem`, `marketing`,
  `other`.
- Tags are non-empty and unique per record.
- Unknown keys are **rejected** with a descriptive `RecordValidationError`.
  Record evolution is handled by `schema_version` upgrades, not by silent
  extra fields.

## 5. Serialization and Versioning

- `to_dict()`/`from_dict()` round-trip losslessly; constructors validate on
  both paths.
- `dump_record(record)` wraps the payload as
  `{"schema_version": 2, "record_kind": "...", "record": {...}}` and writes
  UTF-8 JSON.
- `load_record(...)` rejects envelopes whose `schema_version` differs from the
  current one with `KnowledgeBaseVersionError` (the upgrade path for v1
  `library.json` data is Phase 4, not a silent conversion).
- `LibraryIdentity.schema_version` must equal the current schema version.

## 6. Duplicate Identity

- Two `SourceObject`s with the same SHA-256 are the same source object.
- `SourceObject.merged(a, b)` is the deterministic resolution of a duplicate:
  the hashes and sizes must match; source URLs and aliases are unioned in
  first-seen order; first non-empty value wins for scalar fields.
- Duplicate detection is by content hash only, never by file name.

## 7. Path Safety

All paths stored inside records are relative to the library root with POSIX
separators. `validate_relative_path()` rejects:

- absolute paths and Windows drive letters;
- `..`, `.` and empty segments;
- backslashes;
- paths outside the allowed roots passed by the caller (default:
  `records/`, `objects/`, `extracted/`, `catalogs/`, `projects/`,
  `ai-runs/`).

## 8. Content Hashing

`services/knowledge_hash.py`:

- `sha256_bytes(data)` / `sha256_file(path, chunk_size=1 MiB)` — streaming,
  constant-memory hashing for large PDFs.
- `canonical_record_hash(record)` — SHA-256 over the canonical JSON
  (`sort_keys=True`, compact separators, UTF-8) so record equality is
  reproducible across platforms and dict orderings.

## 9. Acceptance Tests

Unit tests in `tests/unit/test_knowledge_base_schema.py` and
`tests/unit/test_knowledge_hash.py` cover:

1. round-trip of every record type (fixtures under
   `tests/fixtures/knowledge_base/`);
2. invalid-schema rejection (unknown keys, bad review state, `verified`
   without reviewer, malformed hash/date/confidence, bad numeric order);
3. hashing correctness against known vectors and a multi-chunk file;
4. duplicate identity and merge rules;
5. path-safety rejection cases;
6. version-upgrade rejection for `schema_version != 2`;
7. the bundled DK124 and EE19/17 example records validate and contain no
   `verified` field (they are illustrative only).

## 10. Out of Scope (Phase 2)

- Writing/reading the on-disk library layout (Phase 3/4).
- SQLite/FTS index (Phase 3).
- Library UI changes or file migration (Phase 4).
- Controller-profile-specific schema fields (Phase 8).
