# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Contributors:** ZCode (initial Phase 5 module contract); OpenAI Codex
(review, implementation, tests, docs, and visual check)

**Branch:** `feature/datasheet-to-design-v2`

**Active phase:** Phase 5 — `REVIEW`

## Completed Result

Phase 5 adds the bottom datasheet-search UX without crossing into Phase 6:

- Persian RTL collapsed bar below the unchanged four-panel splitter; Ctrl+K
  expands and targets the query workflow.
- Local provider searches the accepted v2 vault selected by
  `QSettings: knowledgeBasePath`; SQLite is opened and closed inside a worker
  thread, and document/page/field hits resolve to their content-addressed PDF
  and page where source evidence exists.
- Deterministic `mock-online` rows exercise the future online-result layout but
  perform no network access. Preview and Save remain disabled; Copy Link works.
- Hint/searching/results/no-results/no-vault/error states, 350 ms debounce,
  source filter, retry, stale-result generation guard, thread shutdown, and
  provider-failure isolation are implemented and tested.
- Existing **Library → Search Datasheets Online...** remains the fallback.

## Verification Performed by OpenAI Codex

- Incoming Phase-4 baseline: **227 passed in 66.62 s**.
- Focused Phase-5/index/main-window regression: **48 passed**.
- Focused thread lifecycle/stale-result suite: **28 passed**.
- Full regression after implementation: **236 passed in 65.12 s**.
- `python -m compileall -q src tests`: passed.
- Visible Windows run: collapsed and expanded strip, Ctrl+K, RTL order, and
  preservation of the four-panel workspace were inspected successfully.

## Working Tree

After the Phase-5 commit the tree should be clean except ignored local artifacts
(`build/`, `dist/`, `dist-native/`, `.venv`, caches, crash reports, and local
PDFs). Do not commit those. Preserve any later uncommitted owner/agent work.

## Not Verified

- Search/open against the owner's migrated real knowledge vault.
- Packaged Nuitka executable and alternate DPI/scaling configurations.
- Windows UI Automation text entry: Qt exposed the disabled AI editor as the
  accessibility focus while the new query field visibly had focus. Qt widget
  tests cover focusability, debounce, explicit search, and row actions.
- No real network provider, download, validation, or Save to Library exists in
  Phase 5; none is claimed tested.
- Phase-4 real-library migration and visible cancellation limitations remain as
  recorded in `docs/modules/LIBRARY_UPGRADE.md`.

## Next Permitted Action

Stop at the Phase 5 owner-review gate. The owner should try Ctrl+K, local/mock
filters, collapse/expand behavior, and opening results from a migrated copy.
Apply any requested corrections inside Phase 5. Begin Phase 6 only after the
owner explicitly accepts this UX; Phase 6 must start with its own Markdown
contract/update before adding network/download/save behavior.

## Required Reading for the Next Contributor

1. `AGENTS.md` if present at the repository/workspace boundary
2. `docs/HANDOFF.md`, `docs/DEVELOPMENT_PLAN.md`, and `docs/PRODUCT_VISION.md`
3. `docs/modules/BOTTOM_SEARCH_STRIP.md`
4. `docs/modules/KNOWLEDGE_INDEX.md` and `KNOWLEDGE_BASE_SCHEMA.md`
5. `docs/CURRENT_STATUS.md` section 19 and `docs/WORK_LOG.md`
6. `docs/ARCHITECTURE.md` and `docs/DECISIONS.md`

## Verification Rule

Do not repeat the results above as current facts without rerunning the relevant
checks in the new checkout. Do not infer contributor identity from Git author;
use commit trailers and the append-only work log.
