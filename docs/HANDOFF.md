# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Contributor:** ZCode (Z.ai, GLM)

**Branch:** `feature/datasheet-to-design-v2`

**Active phase:** Phase 4 — `REVIEW`

## Completed Result

Phases 1–3 were accepted by the owner. Phase 4 (safe Library v1 → v2 desktop
upgrade) is implemented, tested, and pushed. **First visible UI change of the
v2 effort:**

- **Library → Upgrade Library to v2 (Knowledge Base)...** opens the Persian
  RTL upgrade dialog for the active v1 library.
- Flow: preview → cancellable worker-thread run with progress → itemized
  report (imported/duplicate/ambiguous/skipped/failed with reasons) →
  explicit **final acceptance** (marks `library.toml accepted=true`, stores
  `knowledgeBasePath` in QSettings) or **rollback** (deletes the v2 vault).
- New modules: `infrastructure/storage/knowledge_vault.py` (v2 layout, TOML
  identity, content-addressed objects, records + envelopes, migration
  reports), `services/library_migration.py` (orchestration, duplicate/
  ambiguous/skipped/failed semantics, cancel + cleanup), and
  `ui/dialogs/library_upgrade_dialog.py`.
- Safety rules honored and tested: v1 never modified (byte-identical after
  migration), manifest backed up into the vault, partial vault removed on
  cancel/error, rollback deletes only v2.

Recorded verification: full regression **227 passed in 64.98 s** (21 new
tests), compile check and offscreen startup smoke passed.

## Working-Tree Warning

The working tree is expected to be clean except ignored local artifacts
(`build/`, `dist/`, `dist-native/`, `nuitka-crash-report.xml`, test PDFs,
`__pycache__`, `.venv`). Never commit those.

## Current Permitted Action

None automatically — Phase 4 sits at its owner review gate. The owner should
run the upgrade on a **copy of a real library**: open the library
(Library → Open Library Folder...), then **Library → Upgrade Library to v2
(Knowledge Base)...**, and review preview, report, final acceptance, and
rollback per `docs/modules/LIBRARY_UPGRADE.md`. After acceptance, the next
phase is Phase 5 — the bottom search-strip UX shell. Do not start Phase 5
before that.

## Not Verified in Phase 4

- Cancellation through the real worker thread in a visible desktop session
  (tests call the migrator and dialog slots directly).
- Migration of the owner's real library (that is the review gate).
- The v2 vault is not yet browsable in the main window; that surface arrives
  in Phase 5+.

## Required Reading for the Next Contributor

1. `AGENTS.md` if present at the repository/workspace boundary
2. `docs/HANDOFF.md` and `docs/DEVELOPMENT_PLAN.md`
3. `docs/modules/LIBRARY_UPGRADE.md` (Phase 4 contract)
4. `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`, `KNOWLEDGE_INDEX.md`
5. `docs/CURRENT_STATUS.md` (section 18 is the newest record)
6. `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` (ADR-019)

## Verification Rule

The next contributor must not claim the migration or full test suite is
verified merely because this document says so. It must run the tests in the
current checkout and record the actual result.
