# Datasheet Studio — Real Magnetics Catalogue Foundation (Phase 12)

**Status:** Active module contract — **Plan:** Phase 12 in `docs/DEVELOPMENT_PLAN.md`

> Review correction (2026-09-15, `docs/REVIEW_FINDINGS.md`): provenance
> (source hash + page) is now REQUIRED on every record; duplicate codes,
> partial/non-positive loss coefficients, invalid gap options are
> rejected; pack ordering uses the import timestamp (microsecond) — not
> lexicographic versions. A no-CLI Persian pack manager
> (**Tools → Knowledge Base → مدیر کاتالوگ مغناطیسی…**) handles
> open/preview-diff/install/rollback. **Still open:** a real downloaded
> manufacturer pack (the TDK example in tests is a fixture, not official
> data) and recording URL/licensing per pack field — this phase remains
> at REVIEW and is NOT reported as a delivered real core bank.

## Contract

1. **Records** (`models/magnetics_catalog.py`): `CoreRecord` (exact
   `ordering_code`, family as alias only, typed geometry Ae/Aw/le/MLT/Ve,
   Bmax, material code, bobbin codes, gap options), `MaterialRecord`
   (permeability, valid frequency/temperature domains, Steinmetz
   k/α/β when published), `BobbinRecord` (winding window, creepage,
   declared compatible core codes) — each with source hash/page and review
   state.
2. **Validation rules** (enforced on construction and on pack load):
   missing/positive geometry, valid curve domains (min < max), referenced
   materials/bobbins exist, **same-manufacturer links only** (mixed-maker
   assumptions rejected), and bobbin compatibility must be declared by the
   bobbin itself. Review states are limited to `extracted`/`reviewed`;
   `verified` can never be imported.
3. **Versioned packs**: `CatalogPack(provider, pack_version, manifest_hash)`
   with envelope JSON (schema 2). `KnowledgeVault.write_catalog_pack`
   stores `catalogs/<provider>/<version>/{pack.json, manifest.md}`;
   `catalog_packs()`/`latest_catalog_pack()` read the offline cache;
   `rollback_catalog_pack` deletes only that pack folder. `pack_diff`
   gives an update preview (added/removed/changed codes).
4. **Selection UI**: the Flyback core combo appends exact catalogue cores
   (labelled `code · maker (review_state)`) from installed packs; selecting
   one fills the geometry spins. Generic `EE19/17` sample entries remain
   clearly-marked samples.

## Acceptance tests — `tests/unit/test_magnetics_catalog.py`

Round-trip, all four rejection rules, verified-import ban, pack diff,
install/offline-reload/rollback, and the Flyback combo listing + geometry
selection.
