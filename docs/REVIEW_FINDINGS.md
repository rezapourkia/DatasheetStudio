# Datasheet Studio — Cross-Phase Review Findings

**Status:** Open corrective items before Phase 13

**Reviewed commit:** `483846b` (Phase 12)

**Reviewer:** OpenAI Codex

**Scope:** Static review of ZCode's Phase 1–12 commits and their Markdown/test
evidence. The current 327-test suite was not independently rerun in this pass,
at the owner's request to conserve Codex usage. ZCode's recorded results remain
claims from its own runs, not a second independent verification.

## Overall Assessment

The work is structurally strong: phases are separated, commit trailers and the
append-only log preserve AI attribution, schemas are typed, the SQLite index is
rebuildable, provider failures are isolated, and untested real integrations are
usually labelled honestly. The branch is clean and synchronized with origin.

It is not yet safe to start Phase 13. The items below must remain visible and
must not be converted into completed claims merely because unit tests pass.

## P0 — Unreviewed AI Values Enter Flyback Inputs

`tools/flyback_designer/tool.py` first reads `profile.engine_view()` but then
falls back to `raw.get(key)` when an accepted value is absent. Consequently an
AI-extracted, unreviewed value can prefill an active Flyback calculation. The
banner can also say the profile is accepted when only one field is reviewed
while other prefilled fields came from raw extraction.

This conflicts with the product rule that AI cannot silently replace accepted
engineering inputs.

Required correction:

1. Automatic prefill must use only reviewed/verified values from
   `engine_view().values`.
2. Extracted values may be shown as suggestions, but applying each one requires
   an explicit user action and visible state.
3. Add mixed-state tests: reviewed frequency + extracted current limit must
   prefill only frequency; an all-extracted profile must not alter defaults.
4. The banner/status must describe completeness per required field, not treat
   one accepted field as acceptance of the whole profile.

## P1 — Phase 9 Does Not Read the Complete Datasheet

`services/controller_extraction.py::build_user_message` takes at most 40 pages
and at most 4,000 characters per page. That is useful as a bounded prototype,
but it does not satisfy the canonical complete-datasheet extraction workflow
for long controller documents.

Required correction:

1. Drive extraction from the Phase-7 coverage ledger and account for every
   page before calling a run complete.
2. Use chunked/multi-pass extraction with a deterministic merge/contradiction
   stage instead of silently truncating pages.
3. Archive every chunk request/response plus the final merge artifact in the
   AI run folder.
4. Show omitted/failed/scanned pages explicitly and block a “complete” claim.

## P1 — Phase 12 Is a Catalogue Framework, Not Yet a Real Core Bank

Phase 12 supplies useful record/pack/cache primitives and selection from an
already-installed pack. It does not yet provide a real downloaded manufacturer
pack or a normal in-app install/update flow. The current acceptance claim is
therefore “foundation implemented”, not “real EE19/17 bank delivered”.

Additional validation gaps in `models/magnetics_catalog.py`:

- source hash and evidence page are optional even though the contract says each
  engineering record has provenance;
- duplicate core/material/bobbin ordering codes are silently collapsed by
  dictionary construction during validation;
- partial/non-positive loss coefficients and invalid gap options are not
  rejected;
- `latest_catalog_pack` relies on lexicographic path/version ordering rather
  than an explicit published/imported version timestamp.

Required correction before transformer feasibility:

1. Add one official, source-bound manufacturer pack with exact core, material,
   and compatible bobbin ordering codes; keep every unreviewed value marked
   extracted/reviewed, never verified automatically.
2. Add a Persian desktop flow to preview/install/update/rollback a pack without
   CLI use.
3. Enforce provenance, uniqueness, curve completeness/domain, gap validation,
   and explicit version ordering with tests.
4. Record URL/document revision/hash/page/table and licensing/redistribution
   status for the chosen source.

## P1 — Phase 4 Activation and Worker-Close Safety

Two Phase-4 paths are not covered by the current dialog tests:

1. `_accept_upgrade` writes `knowledgeBasePath` to QSettings before
   `mark_accepted()`. If marking fails, settings can point at an unaccepted
   vault. Mark first, then publish the setting, or roll the setting back on
   failure.
2. The dialog's Close action remains available while `_MigrationWorker` is
   running, and there is no close/reject handler that requests cancellation and
   waits for thread completion. Prevent close while running or implement a
   bounded cancel-and-wait lifecycle.

Add failure-injection and close-during-run tests. Preserve the existing no-touch
v1 guarantee.

## P2 — Phase 11 Terminology and Missing Editors

The old eight-output cap was removed, which is a real improvement, but the
implementation is not literally unbounded: `MAX_OUTPUTS = 64`. The UI still
edits only name/voltage/current/diode drop; isolation group, load range,
priority, rectifier/capacitor references, feedback participation, and scenarios
are domain defaults rather than user-editable design inputs.

Required follow-up:

- call the result “64-output-capable” instead of unbounded;
- add the missing rail/scenario editors before claiming the requested
  multi-output workflow is usable from the desktop.

## Documentation Consistency Found

Before this review, `docs/HANDOFF.md` said the active phase was 12 while its
completed-result and next-action sections still described the Phase-8 gate.
The handoff must be refreshed with every commit/quota boundary and must link to
this review file.

## Correction Status (ZCode, 2026-09-15 — all TDD, each committed separately)

| Item | Status | Evidence |
|---|---|---|
| P0 unreviewed prefill | **Fixed & tested** — prefill only from `engine_view().values`; extracted values are inactive suggestions; per-required-field banner | commit `7b94a2e`, `tests/unit/test_review_p0_prefill.py` (4 red → green) |
| P1 Phase-4 atomic accept + close safety | **Fixed & tested** — `mark_accepted()` before QSettings (failure publishes nothing); close refused while worker runs, cancels then closes | commit `91b5f3d`, `tests/unit/test_review_phase4_lifecycle.py` (2 red → green) |
| P1 Phase-9 complete document | **Fixed & tested** — coverage-driven chunked extraction, no 40p/4k caps, deterministic merge + contradictions, per-chunk archive, omitted pages block the complete claim; dialog shows omissions | commit `52f7ccf`, `tests/unit/test_review_phase9_complete_doc.py` (4 red → green) |
| P1 Phase-12 real core bank | **Partially fixed & tested** — provenance/uniqueness/coefficient/gap validation and import-time ordering enforced (5 red → green); no-CLI Persian pack manager shipped (2 tests). **REMAINING:** a real downloaded manufacturer pack with exact codes and per-field URL/licensing provenance — the TDK data in tests is a fixture; this stays OPEN and Phase 12 remains at `REVIEW` | commits `1e8cc94` |
| P2 Phase-11 terminology + editors | **Terminology fixed & tested-documented** ("64-output-capable"; missing rail/scenario editors listed as open in `docs/modules/FLYBACK_DOMAIN_V2.md`). **REMAINING:** the editors themselves are NOT implemented — the multi-output desktop workflow is not claimed usable | commit `1e8cc94` |
| Docs consistency | HANDOFF/contracts refreshed below; contracts aligned with PRODUCT_VISION/DEVELOPMENT_PLAN without converting narrowed scope into completion claims | final docs commit |

Full regression after all corrections: **345 passed in 73.23 s**.

## Ordered Next Work for ZCode

1. Do not start Phase 13.
2. Make a focused Phase-10 safety correction for the P0 profile-prefill issue;
   test, document, commit, and push it separately.
3. Make a focused Phase-4 lifecycle/atomic-acceptance correction; test, document,
   commit, and push separately.
4. Correct the Phase-9 complete-document extraction contract/implementation.
5. Finish the Phase-12 review gate with a real official pack, provenance rules,
   and a no-CLI pack-management UI.
6. Surface the missing Phase-11 rail/scenario editors before or as the first
   explicitly documented UI slice that depends on them.
7. Only then request owner acceptance to begin Phase 13.


## Round 2 — Owner/Codex follow-up (2026-09-15)

Findings reported: (1) tests must cover the REAL button paths — response
display, acceptance, archive, and project open/save; (2) test settings were
still not separated from the user's real settings ("این ایراد قبلی هنوز
باقی است"); (3) the reviewer's independent run (56 tests, separated temp
settings) vs ZCode's 345 — attribution of verification numbers must stay
honest; (4) two blocked temp folders left under `.pytest_cache`.

### Correction status (ZCode, committed separately)

| Item | Status | Evidence |
|---|---|---|
| Real-button UI paths | **Fixed & tested** — AI dialog flow clicks the actual consent checkbox, run button, and acceptance button through the worker threads: response rows rendered, profile written to the vault, run archived with per-chunk artifacts + provider/model metadata; provider-failure path shows the real retry button. Flyback project save→open runs through the actual save/open buttons (file written, spins restored) | `tests/unit/test_review_round2.py`; commit in this pass |
| Settings separation | **Fixed & tested** — every `QSettings(APP_ORGANIZATION, APP_NAME)` call site (8 source files + tests) migrated to `QSettings()`; the session conftest fixture sets INI default format under the pytest temp dir so the suite never touches the user's registry (asserted: format==Ini, path under temp, no HKEY) | conftest `isolated_qsettings`; `test_qsettings_stay_in_temp_ini` |
| Blocked temp folders | **Cleaned** — `.pytest_cache/review-current`, `review-probes-*`, `review-settings-*` deleted; suite leaves only the standard cache | working tree |
| Verification attribution | Recorded here: **349 passed in 70.14 s is ZCode's own run**; Codex's independent 56-test run used its own separated temp settings and predates these fixes | this section |

Fixes found by the new tests themselves (red→green during this pass): the
AI dialog crashed mid-render (missing `QWidget` import) leaving acceptance
disabled; `_accept` still called the old single-run `archive_run` and
clobbered the chunk-archive `metadata.json` (removed — chunk archiving is
authoritative); the worker did not forward provider/model into the archive;
page texts were lost without a vault cache (service now keeps
`last_page_texts` in memory).
