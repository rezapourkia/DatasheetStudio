# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Last implementation contributor:** ZCode (Z.ai, GLM)

**Review contributor:** OpenAI Codex (documentation/static review only)

**Confirmed state (round 5):** round-4 fixes `fa34368`/`9c09222`/`3f6df97` verified by the reviewer (85 related tests); documentation HEAD `a0ebe56`. Round 4 reviewed `374186c`; round 3 reviewed `dc6a433`. — four remaining defects were
reproduced by the owner's reviewer and fixed in `e26455d` (whole-project
preservation on open/save), `bd0d8b9` (real close button cancels the
migration worker), `f659f1d` (extraction deficiencies stay visible: model
contradictions survive the merge; the not-complete warning is composed
into the final status), and `3e624c1` (catalogue rejects NaN/inf values
and malformed SHA-256 provenance). Round-3 fixes were confirmed by the reviewer. Round 4 reproduced three
further cases at `374186c`, each fixed and tested separately: row-shift
of output identity on deletion (`fa34368`), pending close guaranteed by
the real `QThread.finished` signal (`9c09222`), and finite
frequency/temperature bounds on materials (`3f6df97`). Post-round-4 regression (ZCode's own run): **363 passed in 74.30 s**; reviewer confirmation: **85 related tests passed**. These items are now reviewer-confirmed. Phase 12 is NOT complete — the ordered next work is (1) the real manufacturer magnetics pack and (2) the Phase-11 outputs/scenarios editors; Phase 13 stays blocked.
**Branch:** `feature/datasheet-to-design-v2`

**HEAD / origin:** `483846b` — Phase 12 magnetics catalogue foundation

**Active phase:** Phase 12 — `REVIEW`; corrective work required before Phase 13

## Current Result — Review Corrections Applied (2026-09-15)

Owner instruction: apply `docs/REVIEW_FINDINGS.md` corrections in order,
test-first, without starting Phase 13. All fixes are TDD (tests were RED on
the pre-fix code) and each was committed separately; the per-item status
table with test evidence lives in `docs/REVIEW_FINDINGS.md` §Correction
Status.

**Fixed and tested (red → green):**

1. **P0 — Flyback prefill safety** (`7b94a2e`): automatic prefill uses only
   reviewed/verified `engine_view()` values; extracted values surface as
   inactive suggestions requiring explicit user action; the banner reports
   per-required-field states, never a whole-profile acceptance claim.
2. **P1 — Phase-4 atomic acceptance & close safety** (`91b5f3d`):
   `mark_accepted()` runs BEFORE `knowledgeBasePath` is published (a
   failure publishes nothing — failure-injection tested); the upgrade
   dialog refuses close while the worker runs and closes after cancel.
3. **P1 — Phase-9 complete-document extraction** (`52f7ccf`): 40-page/4k
   caps removed; coverage-led chunked extraction over ALL ledger-complete
   pages; deterministic merge with recorded contradictions; per-chunk
   request/response + merge.md + metadata.json archived under
   `ai-runs/<run-id>/chunks/…`; unaccounted pages are reported and block
   any "complete" claim; the dialog shows them.
4. **P1 — Phase-12 validation & no-CLI management** (`1e8cc94`): provenance
   (source hash + page) required on every record; duplicate codes, partial/
   non-positive loss coefficients, and invalid gap options rejected; pack
   ordering by import timestamp (not lexicographic; 9-vs-10 tested); new
   Persian RTL pack manager (**Tools → Knowledge Base → مدیر کاتالوگ
   مغناطیسی…**) with open/validate/preview-diff/install/rollback, zero CLI.
5. **P2 — Phase-11 terminology**: docs/contract now say "64-output-capable"
   and list the missing rail/scenario editors as an OPEN item.

Full regression after round-1 corrections: 345 passed (ZCode's own run).
Round-2 corrections (owner follow-up) then landed: real-button UI-path
tests (AI consent→run→display→accept→archive incl. provider/model in the
chunk archive and the real retry button; Flyback project save→open via the
actual buttons), full settings separation from the user's store (all
`QSettings(org, app)` migrated to `QSettings()` + session INI fixture under
pytest tmp, asserted not-registry), and cleanup of the blocked
`.pytest_cache/review-*` folders. Post-round-2 regression (ZCode's own
run): **349 passed in 70.14 s**. Bugs the new tests exposed and fixed:
missing QWidget import crashed the AI dialog mid-render; `_accept` clobbered
the chunk archive via the old `archive_run`; provider/model were not
archived; page texts were lost without a vault cache.

**NOT done (remaining — do not claim otherwise):**

- Phase 12: a real downloaded manufacturer pack with exact ordering codes
  and per-field URL/licensing provenance — the TDK data in tests is a
  fixture. Phase 12 remains at `REVIEW`.
- Phase 11: rail/scenario editors (isolation group, load range, priority,
  rectifier/capacitor references, feedback participation, scenario editing)
  are domain-only; the multi-output desktop workflow is not yet usable.
- Phase 13 has NOT been started (owner instruction).
- Inherited open gates: owner's real-library migration/vault flows, real
  DigiKey credentials, and a real-provider AI extraction run.

## Mandatory Review Findings

See `docs/REVIEW_FINDINGS.md` — including the appended §Correction Status
table mapping every item to its commit and tests.

## What ZCode Did Well

- Markdown-first phase contracts, focused commits, explicit AI attribution,
  and an append-only work log are consistently present.
- Domain records, evidence states, content hashing, rebuildable FTS indexing,
  provider isolation, and v1-preservation paths have substantial automated
  coverage.
- Real DigiKey, embedded-browser, OCR, real-controller extraction, owner-vault,
  and real magnetics-pack limitations were generally documented rather than
  presented as verified.
- HEAD and origin matched at the review boundary; no uncommitted implementation
  work was present.

## Next Permitted Action for ZCode

None automatically. The owner reviews this correction pass and decides the
next slice: (a) bind a real manufacturer magnetics pack (source, codes,
licensing) to close the Phase-12 gate; (b) build the Phase-11 rail/scenario
editors; or (c) accept and start Phase 13 explicitly. Phase 13 must not
begin without owner acceptance.

## Required Reading

1. `docs/REVIEW_FINDINGS.md`
2. `docs/DEVELOPMENT_PLAN.md` and `docs/PRODUCT_VISION.md`
3. `docs/modules/FLYBACK_HANDOFF.md`
4. `docs/modules/AI_EXTRACTION_ARTIFACTS.md`
5. `docs/modules/LIBRARY_UPGRADE.md`
6. `docs/modules/FLYBACK_DOMAIN_V2.md`
7. `docs/modules/MAGNETICS_CATALOG.md`
8. `docs/CURRENT_STATUS.md` sections 19–26 and `docs/WORK_LOG.md`

## Verification Rule

Do not repeat recorded test counts as current facts without rerunning the
relevant checks. Do not use unit-test success to promote illustrative data or
untested provider/browser/OCR behavior to verified. Never use unreviewed AI
facts as deterministic engineering inputs without an explicit user action.
