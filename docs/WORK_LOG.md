# Datasheet Studio — Contributor Work Log

This is an append-only record of material project work. It complements Git
history because repository author settings do not reliably identify which AI
system performed a change.

Do not rewrite old entries to change attribution. Add a correction entry when
needed. Never include API keys, private prompts, account data, or user PDFs.

## Entry Template

```text
## YYYY-MM-DD — Phase NN — Short result

- Contributor: Human name, AI product/provider, or both
- Role: planning | implementation | test | review | documentation
- Requested by: project owner / issue / prior phase
- Scope: exact work authorized
- Changed: files or module areas
- Verification: commands/checks actually completed
- Not verified: anything not directly tested
- Commit: this commit / hash / not committed
- Handoff: next permitted action or review gate
```

## 2026-09-15 — Phase 0 — Product contract and staged plan

- Contributor: OpenAI Codex
- Role: product analysis and documentation
- Requested by: project owner in the active Codex task
- Scope: correct the product definition, recommend the knowledge-base design,
  define the AI/engine boundary, and create a small review-gated development plan
- Changed: `docs/PRODUCT_VISION.md`, `docs/DEVELOPMENT_PLAN.md`,
  `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md`,
  `docs/modules/AI_ENGINEERING_WORKFLOW.md`, and
  `docs/modules/ONLINE_DATASHEET_SEARCH.md`; added this work log and handoff
- Verification: required files exist, no trailing whitespace in the new files,
  staged diff limited to Phase 0 documentation, and `git diff --check` passed
- Not verified: no application behavior was changed or tested in Phase 0
- Commit: this commit
- Handoff: owner reviews Phase 0; Phase 1 may begin only after explicit
  continuation

## 2026-09-15 — Phase 1 — Baseline verified, classified, committed, pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: review, test, and baseline preservation
- Requested by: project owner ("شروع کن" after being briefed on the Phase 1
  handoff)
- Scope: Phase 1 only — inspect uncommitted files/diffs, read the Tool Registry
  and Flyback v1 source, run regression checks, separate source from
  artifacts, update status/handoff, commit and push, then stop at the review
  gate. No Knowledge Base v2 work.
- Changed: no source changes; documentation updates only
  (`docs/WORK_LOG.md`, `docs/HANDOFF.md`, `docs/DEVELOPMENT_PLAN.md`,
  `docs/CURRENT_STATUS.md`) recorded on top of the pre-existing uncommitted
  baseline (Tool Registry + Flyback v1 + packaging + docs) which was committed
  unchanged.
- Verification: `python -m compileall -q src tests` passed; full
  `pytest tests` run in the current checkout: **143 passed in 61.99 s**;
  offscreen startup smoke test exited cleanly with 2 registered tools
  (`symbol-creator`, `flyback-designer`); `git add -An` preview confirmed only
  source/tests/docs/packaging-spec files are tracked-included (no PDFs,
  databases, build output, or secrets).
- Not verified: packaged Nuitka executable was not built or launched in this
  pass; visual desktop verification (screenshot-level) was not performed.
  The earlier automated Windows screenshot attempt by the previous contributor
  also remained unverified.
- Commit: this commit
- Handoff: stop at the Phase 1 review gate. Owner may install/run the baseline
  and request corrections before Phase 2 (Knowledge Base domain/schema).

## 2026-09-15 — Phase 2 — Knowledge-base domain schema implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه بده" — acceptance of Phase 1 and
  continuation to Phase 2)
- Scope: Phase 2 only per `docs/DEVELOPMENT_PLAN.md` — domain types for
  source objects, document revisions, aliases, provenance/evidence, component
  profiles, review states, and library identity; canonical serialization and
  validation; SHA-256 streaming hash service and duplicate identity rules. No
  library UI change and no user file moves.
- Changed: added `docs/modules/KNOWLEDGE_BASE_SCHEMA.md` (contract written
  before code), `src/datasheet_studio/models/knowledge_base.py`,
  `src/datasheet_studio/services/knowledge_hash.py`,
  `tests/unit/test_knowledge_base_schema.py`,
  `tests/unit/test_knowledge_hash.py`,
  `tests/fixtures/knowledge_base/*.json`,
  `docs/examples/knowledge_base/*.md` (owner-review examples), two entries in
  the `pyproject.toml` deploy file list, and status updates in
  `docs/DEVELOPMENT_PLAN.md`, `docs/CURRENT_STATUS.md` (new section 16),
  `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md` (status line), and this log.
- Verification: 44 new unit tests pass (round-trip of every record type from
  fixtures, invalid-schema rejection incl. unknown keys and `verified`
  without reviewer, path-safety cases, duplicate merge, version-upgrade
  rejection incl. a legacy v1 envelope, hash known-vectors and a ~5 MB
  multi-chunk file, canonical-hash key-order stability); compile check
  passed; full regression **187 passed in 63.51 s**; import scan confirms no
  Qt/network dependency in the domain and hash modules. Two implementation
  fixes were made after first test run (empty-note merge precedence in
  `SourceObject.merged`; a malformed expectation inside the canonical-JSON
  test itself).
- Not verified: example records use placeholder source hashes and are not
  bound to real DK124/EE17 documents; nothing here was exercised through the
  desktop UI (by design — Phase 2 has no UI surface).
- Commit: this commit
- Handoff: owner reviews the DK124 and EE19/17 example records at the Phase 2
  gate; Phase 3 (SQLite/FTS index) starts only after acceptance.

## 2026-09-15 — Phase 3 — Rebuildable SQLite/FTS index implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("اوکی / ادامه بده" — acceptance of Phase 2 and
  continuation to Phase 3)
- Scope: Phase 3 only per `docs/DEVELOPMENT_PLAN.md` — SQLite/FTS index
  adapter over the Phase 2 domain records, atomic rebuild, corruption
  recovery, search grammar with maker/type/core/material/verified filters,
  page-aware and field-aware search context, and a recorded performance
  result. No UI, no library-folder migration.
- Changed: added `docs/modules/KNOWLEDGE_INDEX.md` (contract first),
  `src/datasheet_studio/infrastructure/storage/knowledge_index.py`,
  `tests/unit/test_knowledge_index.py`, one `pyproject.toml` deploy-list
  entry, and status updates (`docs/DEVELOPMENT_PLAN.md`,
  `docs/CURRENT_STATUS.md` §17, `docs/HANDOFF.md`, this log).
- Verification: 19 new unit tests pass — lifecycle/upsert/remove, unique-key
  conflict handling, transaction rollback leaves index unchanged,
  delete-file-and-rebuild produces identical search results (documents,
  fields, and page snippets), corruption recovery from a garbage file,
  deterministic ordering, Persian free-text search, filter behaviors
  (maker/type/core/material/verified), and a 1,500-document synthetic
  performance fixture (build ≈ 0.2 s; part/field/page queries ≤ 4 ms;
  asserted budgets build < 90 s, query < 2 s). Full regression **206 passed
  in 66.20 s**. FTS5 availability (incl. Persian tokenization) verified
  against the bundled SQLite 3.49.1 before implementation.
- Issues found and fixed during this pass: (1) the first design shared one
  FTS table across record kinds and collided on rowids — replaced with one
  FTS table per kind; (2) FTS5 auxiliary functions (`snippet`/`bm25`) do not
  accept bare table aliases in joined queries — rewritten with full table
  names; (3) three test expectations were corrected against verified
  tokenizer behavior (`DK124` is a single token; quoted phrases with spaces
  are not supported) and a `verified` field needs reviewer fields.
- Not verified: no desktop UI exists for the index (by design); the UI-thread
  offload requirement is documented for Phase 4/5 integration but not
  exercised; timings are from the development machine only.
- Commit: this commit
- Handoff: owner reviews search syntax and result ordering (representative
  part/core queries) at the Phase 3 gate; Phase 4 (safe v1→v2 library
  upgrade UI) starts only after acceptance.

## 2026-09-15 — Phase 4 — Safe Library v1 → v2 desktop upgrade implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه بده" — acceptance of Phase 3 and
  continuation to Phase 4)
- Scope: Phase 4 only per `docs/DEVELOPMENT_PLAN.md` — migration preview,
  recoverable backup, copy/hash/import without deleting originals, duplicate/
  ambiguous/skipped/failure reporting, cancel and rollback from the desktop
  UI. First phase with a visible UI change.
- Changed: added `docs/modules/LIBRARY_UPGRADE.md` (contract first),
  `src/datasheet_studio/infrastructure/storage/knowledge_vault.py`,
  `src/datasheet_studio/services/library_migration.py`,
  `src/datasheet_studio/ui/dialogs/library_upgrade_dialog.py`,
  `is_valid_pdf_file()` in `src/datasheet_studio/infrastructure/pdf/reader.py`,
  a Library-menu action in `main_window.py`, three test modules
  (`test_knowledge_vault.py`, `test_library_migration.py`,
  `test_library_upgrade_dialog.py`), `pyproject.toml` deploy-list entries,
  and status doc updates.
- Verification: 21 new unit tests pass — vault layout/object dedup by hash/
  envelope round-trip/TOML identity/accept/rollback; migration success with
  v1 files and manifest byte-identical afterwards, records + searchable
  index + report files written; duplicates (one object, two records);
  invalid PDF and missing file skipped with reasons; simulated
  `PermissionError` on object copy reported per-item while migration
  continues; cancellation and injected unexpected error remove the partial
  vault; rollback after success; preview counts; dialog preview/report/
  accept/rollback offscreen (QSettings cleaned up). Full regression
  **227 passed in 64.98 s**; compile check and offscreen startup smoke
  passed. Test fixes during the pass: byte-identical duplicate fixture
  (PyMuPDF embeds metadata so two saves differ), required `manufacturer`
  argument, and permission patch aimed at the vault module's `shutil`.
- Not verified: cancellation through the real worker thread inside a visible
  desktop session; migration of the owner's real library copy (this is the
  Phase 4 review gate); large-library timings beyond the Phase 3 fixture.
- Commit: this commit
- Handoff: owner runs **Library → Upgrade Library to v2** on a copy of a real
  library and reviews preview/report/accept/rollback; Phase 5 (bottom search
  strip UX shell) starts only after acceptance.

## 2026-09-15 — Phase 5 — Bottom local/mock search strip implemented

- Contributor: ZCode (Z.ai, GLM) for the initial uncommitted module contract;
  OpenAI Codex for contract review, implementation, tests, documentation, and
  visual verification
- Role: documentation-first handoff, implementation, test, and review
- Requested by: project owner, who explicitly asked OpenAI Codex to continue
  after Z.AI reached its account limit
- Scope: Phase 5 only — Persian RTL bottom search UX, accepted local-v2-vault
  adapter, deterministic mock source, states/actions/threading, and main-window
  integration. No real network, download, validation, or save-to-library.
- Changed: added `services/search_service.py`,
  `ui/widgets/search_strip.py`, `test_search_service.py`, and
  `test_search_strip.py`; extended Phase-3 search-hit references with source
  hash/page for PDF resolution; integrated a bottom dock and Ctrl+K in
  `main_window.py`; updated the deploy file list and phase/status/handoff docs.
- Verification: independently re-ran the incoming baseline (**227 passed**);
  focused Phase-5/index/main-window suite **48 passed**; focused lifecycle/stale
  checks **28 passed**; full regression **236 passed in 65.12 s**; compileall
  passed. Visible Windows inspection confirmed collapsed/expanded sizing,
  Ctrl+K, RTL placement, and unchanged four-panel workspace.
- Issues found and fixed: PySide6 could abort across repeated searches with the
  initial `QObject.moveToThread/deleteLater` lifecycle; replaced it with a
  bounded QThread object and shutdown wait, then added stale-result coverage.
- Not verified: result opening against the owner's real migrated vault,
  packaged executable/DPI variants, real online providers, download, or save.
  Windows accessibility exposed the old disabled AI editor as focused despite
  the visually focused query field, so UI-automation typing is not claimed.
- Commit: this commit
- Handoff: stop at Phase 5 `REVIEW`; owner approves/corrects the search layout
  before Phase 6 connects an official online source.

## 2026-09-15 — Phase 6 — Online source adapter framework implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه بده… تو ادامه بده" after reporting
  that OpenAI Codex had completed Phase 5)
- Scope: Phase 6 only per `docs/DEVELOPMENT_PLAN.md` — provider contract,
  concurrent cancellation-safe search coordination, bounded HTTP client,
  first official adapter (DigiKey), validated download with
  preview-before-save into the accepted v2 vault, settings UI. Browser
  fallback preserved; no scraping.
- Prior-agent work verified first: Codex's Phase 5 commit `f2215f4` was
  re-verified in the current checkout (compile OK; full suite **236 passed**;
  offscreen smoke with the strip present) before building on it.
- Changed: added `docs/modules/ONLINE_ADAPTER_FRAMEWORK.md` (contract first),
  `src/datasheet_studio/models/search.py`,
  `src/datasheet_studio/infrastructure/web/{__init__,http_client,digikey}.py`,
  `src/datasheet_studio/services/online_import.py`,
  `src/datasheet_studio/ui/dialogs/online_sources_dialog.py`; reworked
  `services/search_service.py` (domain types moved to models, concurrency +
  cancellation; `create_phase5_search_service` kept for compatibility);
  extended `ui/widgets/search_strip.py` (DigiKey source, پیش‌نمایش/ذخیره
  affordances, dynamic provider choices, `display_message`); wired
  main-window workers (download/save off the GUI thread) and a
  Library-menu settings action; `pyproject.toml` deploy-list entries;
  status doc updates.
- Verification: 22 new offline unit tests (`test_http_client.py`,
  `test_digikey_adapter.py`, `test_online_import.py`,
  `test_online_sources_dialog.py`) covering timeout, HTTP 429, malformed
  JSON, oversized download, mid-stream cancellation, non-PDF signature,
  token happy path + caching + unconfigured notice, vault dedup +
  searchability + guidance errors, strip preview/save signals, and the
  settings dialog round-trip; full regression **258 passed in 66.39 s**;
  compile check and offscreen startup smoke (source combo shows DigiKey).
- Not verified: the real DigiKey API (no credentials available here) — the
  adapter is tested only through a mocked transport and the owner must run
  تست اتصال with real credentials; secure OS key storage remains pending
  (ADR-009).
- Commit: this commit
- Handoff: owner reviews DigiKey usefulness with real credentials at the
  Phase 6 gate; Phase 7 (complete document text/OCR coverage) starts only
  after acceptance.

## 2026-09-15 — Phase 6 correction — Embedded Chromium browser per owner direction

- Contributor: ZCode (Z.ai, GLM)
- Role: implementation and test (owner-requested in-phase correction)
- Requested by: project owner — the online search must be a Google-style web
  search inside Datasheet Studio with in-app PDF opening and library saving;
  the system-browser round trip is unacceptable.
- Scope: Phase 6 correction only (Change Control §7). No new phase started.
- Changed: rewrote `ui/dialogs/datasheet_browser.py` (RTL Chromium dialog,
  engine selector, back/forward/reload, query search, validated download→
  vault save with viewer-open action), added `web` source to the search
  strip (`web_search_requested` signal; excluded from the "all" fan-out),
  wired `main_window._open_datasheet_browser(query)` to the vault import
  service, added ADR-021 + decision index row, updated
  `docs/modules/ONLINE_DATASHEET_SEARCH.md` §5, this log, CURRENT_STATUS §20,
  and HANDOFF; new tests in `tests/unit/test_datasheet_browser.py`.
- Verification: 5 new offline tests; full regression **263 passed in 69.98 s**;
  compile check + offscreen startup smoke passed (strip lists the web
  source). QtWebEngine import verified in the project venv; the dialog keeps
  its graceful system-browser fallback when the engine cannot start.
- Not verified: real Google browsing/download inside a visible desktop
  session (owner review); DigiKey with real credentials (still open from
  Phase 6).
- Commit: this commit
- Handoff: owner tries the embedded browser (strip «وب» source or Library →
  Search Datasheets Online...): Google search, open a PDF, save it to the
  library — all inside the app. Corrections stay within Phase 6.

## 2026-09-15 — Phase 7 — Complete document text/OCR coverage implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه بده / برای فعلا خوبه" — Phase 6
  acceptance including the embedded-browser correction)
- Scope: Phase 7 only per `docs/DEVELOPMENT_PLAN.md` — coverage ledger,
  normalized page markers, text-poor detection, pluggable OCR boundary,
  background progress/cancellation, hash-addressed extraction cache, index
  integration.
- Changed: added `docs/modules/TEXT_EXTRACTION_COVERAGE.md` (contract
  first), `src/datasheet_studio/services/text_extraction.py`,
  `src/datasheet_studio/infrastructure/ocr/__init__.py`,
  `src/datasheet_studio/ui/dialogs/extraction_coverage_dialog.py`,
  `src/datasheet_studio/tools/text_coverage_tool.py` (registered under
  category "Knowledge Base"), `pyproject.toml` deploy entries, tests
  (`test_text_extraction.py`, `test_extraction_dialog.py`), and status doc
  updates; `test_flyback_dialog.py` tool/category expectations updated for
  the third registered tool.
- Verification: 14 new unit tests — mixed searchable/scanned/failed ledger,
  completeness rule, failed-page tolerance, cache reuse (extraction counter
  proves no re-run), page markers, cancellation leaves cache intact,
  fake-OCR completes scanned docs, NoOcrAdapter/absence keeps `scanned`,
  page-text searchability through the vault index, dialog banners/table,
  registry entry; full regression **277 passed in 67.13 s**; compile check
  and offscreen startup smoke (three tools registered) passed. Service fix
  during the pass: the index is now created on demand when a vault has no
  index file yet (page indexing was silently skipped before).
- Not verified: a real OCR engine (none selected — pending owner decision),
  coverage of the owner's real DK124/DK125/TMG0656 documents (review gate),
  and chunk/evidence artifacts (`chunks.json`, `evidence.json` — later
  phases by contract).
- Commit: this commit
- Handoff: owner runs Tools → Knowledge Base → پوشش متن سند… on a
  representative datasheet at the Phase 7 gate; Phase 8 (controller profile
  and evidence schema) starts only after acceptance.

## 2026-09-15 — Phase 8 — Controller profile and evidence schema implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه بده" — Phase 7 acceptance)
- Scope: Phase 8 only per `docs/DEVELOPMENT_PLAN.md`.
- Changed: added `docs/modules/CONTROLLER_PROFILE_SCHEMA.md` (contract
  first), `models/controller_profile.py`,
  `KnowledgeVault.write_controller_profile`,
  `ui/dialogs/controller_profile_dialog.py`,
  `tools/controller_profile_tool.py` (registered), `pyproject.toml` deploy
  entries, tests (`test_controller_profile.py`,
  `test_controller_profile_dialog.py`), and status doc updates;
  `test_flyback_dialog.py` tool expectations updated for the fourth tool.
- Verification: 16 new tests (complete/partial/contradictory engine views,
  wrong-unit/wrong-page/unsupported-mode/out-of-range/unknown-field
  rejection, AI reviewed/verified cap, envelope round-trip + version/kind
  rejection, vault storage with index searchability, offscreen form
  load/collect/save round-trip); full regression **293 passed in 68.24 s**;
  compile + offscreen startup smoke (four tools) passed.
- Not verified: AI extraction automation (Phase 9), Flyback consumption of
  engine views (Phase 10+), owner approval of field set/form (review gate).
- Commit: this commit
- Handoff: owner reviews the form and field set at the Phase 8 gate; Phase 9
  (AI extraction artifacts and review UI) starts only after acceptance.

## 2026-09-15 — Phase 9 — AI extraction artifacts and review UI implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه بده" — Phase 8 acceptance)
- Scope: Phase 9 only per `docs/DEVELOPMENT_PLAN.md`.
- Changed: `docs/modules/AI_EXTRACTION_ARTIFACTS.md` (contract),
  `prompts/controller_extraction_v1.md`,
  `services/controller_extraction.py`,
  `ui/dialogs/ai_extraction_review_dialog.py`, `tools/ai_extraction_tool.py`
  (registered), `pyproject.toml` deploy entries,
  `tests/unit/test_controller_extraction.py`, status docs.
- Verification: 11 new tests; full regression **304 passed in 68.22 s**;
  compile + smoke passed.
- Not verified: real provider execution (owner gate), diff-vs-existing
  profile (next refinement).
- Commit: this commit
- Handoff: owner runs one end-to-end real extraction at the Phase 9 gate;
  Phase 10 (current-datasheet handoff to Flyback) starts after acceptance.

## 2026-09-15 — Phase 10 — Current-datasheet handoff to Flyback implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه" — Phase 9 acceptance)
- Scope: Phase 10 only per `docs/DEVELOPMENT_PLAN.md`.
- Changed: `docs/modules/FLYBACK_HANDOFF.md` (contract first),
  `ToolContext` (+source_hash, +controller_profile),
  `KnowledgeVault.controller_profiles_for`, `MainWindow._tool_context`,
  Flyback dialog ctor (prefill + controller banner), Flyback tool prefill
  logic, `tests/unit/test_flyback_handoff.py`.
- Verification: 8 new tests; full regression **312 passed in 66.85 s**;
  compile passed. Fix during pass: tests patch the dialog module (the tool
  imports it lazily inside run()).
- Not verified: owner's visual check of the banner/prefill (review gate).
- Commit: this commit
- Handoff: owner verifies PDF → Tools → Flyback flow at the Phase 10 gate;
  Phase 11 (Flyback domain v2 outputs/scenarios) starts after acceptance.

## 2026-09-15 — Phase 11 — Flyback domain v2 outputs and scenarios implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه" — Phase 10 acceptance)
- Scope: Phase 11 only per `docs/DEVELOPMENT_PLAN.md`.
- Changed: `docs/modules/FLYBACK_DOMAIN_V2.md` (contract first), engine
  (OutputSpec v2 fields, MAX_OUTPUTS=64, ScenarioSpec, group/load/priority
  validation, power_summary), persistence (typed ScenarioSpec loading,
  v1-missing-scenarios default), dialog (64-output cap),
  `tests/unit/test_flyback_domain_v2.py`.
- Verification: 6 new tests; full regression **317 passed in 67.04 s**.
  Fixes during pass: persistence stored raw dict scenarios (typed loading
  added) and missing v1 scenarios became [] instead of the default matrix.
- Not verified: owner-built representative designs (review gate).
- Commit: this commit
- Handoff: owner builds one-output, dual-isolated, and multi-output
  designs at the Phase 11 gate; Phase 12 (real magnetics catalogue
  foundation) starts after acceptance.

## 2026-09-15 — Phase 12 — Real magnetics catalogue foundation implemented and pushed

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation-first implementation and test
- Requested by: project owner ("ادامه" — Phase 11 acceptance)
- Scope: Phase 12 only.
- Changed: `docs/modules/MAGNETICS_CATALOG.md`, `models/magnetics_catalog.py`,
  vault pack storage/rollback, Flyback combo catalog loading,
  `tests/unit/test_magnetics_catalog.py`, `pyproject.toml` deploy entry.
- Verification: 10 new tests; full regression **327 passed in 67.01 s**.
  Fix during pass: CoreSpec field name (`bmax_t`).
- Not verified: a real downloaded manufacturer pack (fixture data in tests
  is illustrative; owner review gate).
- Commit: this commit
- Handoff: owner checks the first supported core family's codes/drawings;
  Phase 13 (transformer feasibility) starts after acceptance.

## 2026-09-15 — Cross-phase static review before Phase 13

- Contributor: OpenAI Codex
- Role: static review and documentation only; no implementation code changed
- Requested by: project owner, specifically to assess Z.AI's work and update
  Markdown for continuation while conserving Codex weekly usage
- Scope: inspect Phase 1–12 commit evidence and the critical Phase 4/9/10/11/12
  paths; refresh the stale handoff and record actionable corrections
- Changed: added `docs/REVIEW_FINDINGS.md`; refreshed `docs/HANDOFF.md` and the
  current-action section of `docs/DEVELOPMENT_PLAN.md`; appended this log entry
- Verification: confirmed a clean branch at `483846b`, with HEAD equal to
  `origin/feature/datasheet-to-design-v2`; inspected commit trailers/work logs
  and the relevant source/contracts. No current test suite was run in this
  review at the owner's request. ZCode's latest recorded result is 327 passing.
- Findings: unreviewed AI values can prefill Flyback; extraction is capped at
  40 pages × 4,000 characters; Phase-12 real pack/pack-manager and validation
  gaps; Phase-4 acceptance/close lifecycle gaps; Phase-11 64-output wording and
  missing advanced rail/scenario editors
- Not verified: runtime behavior, current test result, real providers/browser,
  real OCR, real controller PDFs, real user vault, or manufacturer pack data
- Commit: this commit
- Handoff: ZCode must follow `docs/REVIEW_FINDINGS.md` corrections before
  beginning Phase 13.

## 2026-09-15 — Review corrections — P0 + P1(×3) + P2 applied via TDD, each committed separately

- Contributor: ZCode (Z.ai, GLM)
- Role: corrective implementation and test per owner instruction and
  `docs/REVIEW_FINDINGS.md` (reviewer: OpenAI Codex)
- Scope: no Phase-13 work. Ordered corrections with failing-test-first
  discipline; per-item status table appended to `docs/REVIEW_FINDINGS.md`.
- Changed: commits `42cce8d` (review docs preserved), `7b94a2e` (P0 prefill),
  `91b5f3d` (Phase-4 lifecycle), `52f7ccf` (Phase-9 complete document),
  `1e8cc94` (Phase-12 hardening + pack manager + Phase-11 terminology).
- Verification: every fix has tests that were RED on the pre-fix code (11
  new red→green tests total across four files); full regression after all
  corrections **345 passed in 73.23 s**; compile check passed.
- Not fixed (explicitly remaining): real manufacturer pack + per-field
  URL/licensing provenance for Phase 12; Phase-11 rail/scenario editors;
  anything Phase 13+.
- Commit: this commit
- Handoff: see the corrected HANDOFF below; Phase 12 stays at `REVIEW`.

## 2026-09-15 — Review round 2 — real-button tests + settings separation

- Contributor: ZCode (Z.ai, GLM)
- Role: corrective implementation and test per owner instruction (findings
  relayed from the owner's independent review round; reviewer artifacts
  cleaned from .pytest_cache)
- Scope: no Phase-13 work. Register round-2 items, fix with test-first
  discipline where behavior changed.
- Changed: conftest `isolated_qsettings` (INI under pytest tmp; app org/app
  names on QApplication); migration of all `QSettings(org, app)` call sites
  (8 src files + 3 test files) to `QSettings()`; `TextExtractionService
  .last_page_texts`; AI dialog fixes (QWidget import, removal of the
  clobbering `archive_run` call, provider/model forwarded to the chunk
  archive, in-memory texts fallback); Flyback dialog keeps real open/save
  button references; `tests/unit/test_review_round2.py` (4 tests: settings
  isolation, AI real-button flow to archive, retry path, Flyback
  save→open buttons); REVIEW_FINDINGS §Round 2.
- Verification: full regression **349 passed in 70.14 s** (ZCode's own
  run); no leftover review temp folders under .pytest_cache.
- Not verified: anything Phase 13+ (not started, per owner instruction).
- Commit: this commit
- Handoff: see HANDOFF — Phase 12 remains at REVIEW; Phase 13 blocked
  pending owner acceptance.

## 2026-09-15 — Review round 3 — four reproduced defects fixed one-by-one

- Contributor: ZCode (Z.ai, GLM)
- Role: corrective implementation and test per owner-relayed findings
  (reviewed commit dc6a433; reviewer re-verified the round-2 fixes and
  reproduced the four remaining defects)
- Scope: no Phase-13 work; no "fully fixed" claims. Each item: reproduction
  test red on the reported behavior → fix → dedicated commit.
- Changed: r3-1 whole-project preservation on open/save (`e26455d`);
  r3-2 real close button cancels the migration worker (`bd0d8b9`);
  r3-3 extraction deficiencies stay visible (model contradictions survive
  the merge; final status composes the not-complete warning) (`f659f1d`);
  r3-4 catalogue NaN/inf/hash validation (`3e624c1`); REVIEW_FINDINGS
  §Round 3 (per-item entries); HANDOFF refreshed with the new HEAD.
- Verification: 10 new reproduction tests (all red before their fix);
  full regression **359 passed in 78.00 s** (ZCode's own run).
- Not verified: owner re-verification of the four items; Phase-13 start
  remains blocked.
- Commit: this commit
- Handoff: statuses are "fixed & tested, awaiting owner re-verification".

## 2026-09-15 — Review round 4 — three reproduced cases fixed one-by-one

- Contributor: ZCode (Z.ai, GLM)
- Role: corrective implementation and test per owner-relayed findings
  (reviewed commit 374186c; round-3 fixes confirmed by the reviewer)
- Scope: no Phase-13 work; no "fully fixed" claims.
- Changed: `fa34368` (row-bound output identity), `9c09222` (pending close
  via QThread.finished), `3f6df97` (finite material bounds); round-4
  section in REVIEW_FINDINGS; HANDOFF HEAD corrected from 483846b to the
  round-4 reviewed commit; this entry.
- Verification: 4 new reproduction tests (red before their fixes; the
  pending-close test drives the real preview→start path and never calls
  the helper manually); full regression **363 passed in 74.30 s**
  (ZCode's own run).
- Not verified: owner re-verification; Phase 13 blocked.
- Commit: this commit

## 2026-09-15 — Review round 5 — confirmations recorded

- Contributor: ZCode (Z.ai, GLM)
- Role: documentation of the owner-relayed reviewer confirmation
- Scope: record the independent confirmation (85 related tests) of the
  round-4 fixes; refresh HANDOFF's stale HEAD reference; keep Phase 12
  open. No code changes.
- Changed: REVIEW_FINDINGS §Round 5, HANDOFF confirmed-state header and
  next-work wording, this entry.
- Verification: none new (ZCode reran nothing this pass; the 85-test
  result is the reviewer's independent run, recorded as such).
- Not verified / still open: the real manufacturer pack, the Phase-11
  outputs/scenarios editors, Phase 13 start.
- Commit: this commit
