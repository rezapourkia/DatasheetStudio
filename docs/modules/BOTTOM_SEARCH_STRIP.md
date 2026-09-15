# Datasheet Studio — Bottom Search Strip (Phase 5)

**Status:** Implemented — owner review pending

**Parent contracts:** `docs/modules/ONLINE_DATASHEET_SEARCH.md`,
`docs/modules/KNOWLEDGE_INDEX.md`, `docs/PRODUCT_VISION.md` §5

**Plan reference:** Phase 5 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

A small, collapsible Persian/RTL search strip docked at the bottom of the
main window (between the four panels and the status bar). It is the single
entry point for finding datasheets — first against the local knowledge base,
later against permitted online sources (Phase 6). Normal PDF work is never
obscured: collapsed, the strip is one thin bar.

## 2. Sources (Phase 5 = local + mock only)

| Source | Data | Enabled |
|---|---|---|
| `local-kb` (کتابخانه محلی) | The Phase 3 index of the accepted v2 vault (`QSettings: knowledgeBasePath`); documents, parameters, and page text with snippets | Fully working: **Open** launches the PDF (at the matched page when the hit is a page/field hit) |
| `mock-online` (نمایشی) | Deterministic fake rows derived from the query; no network | UX only: rows, Copy Link; **Preview/Save disabled** until Phase 6 |

No network call, credential, or real provider exists in this phase. If no
v2 vault is active, the local source shows a guidance state pointing to
**Library → Upgrade Library to v2…** (the existing browser dialog remains
available as fallback under Library → Search Datasheets Online…).

## 3. UI Behavior

- **Collapsed bar:** magnifier button + hint text + `Ctrl+K` toggles/focuses.
- **Expanded:** query box, source filter (همه / کتابخانه محلی / نمایشی),
  search button, and compact result rows (icon, title, subtitle, highlighted
  snippet). Live search debounced (~350 ms) plus Enter/button search.
- **States:** hint (empty query), searching, results, no-results, error
  (message + retry), no-vault guidance. States are covered by UI tests.
- **Per-row actions:** باز کردن (Open — local only), کپی لینک (Copy Link —
  online/mock URL, or local file path), ذخیره در کتابخانه (Save — disabled
  until Phase 6, tooltip explains).
- **Threading:** every search runs in a `QThread` worker (rule
  `KNOWLEDGE_INDEX.md` §2); stale results are discarded via a generation
  counter. The index connection is opened and closed inside the worker.
- RTL layout order, keyboard focus flow, and no interference with the
  four-panel splitter (the strip lives outside it).

## 4. Normalized Result Contract

`services/search_service.py` defines `SearchResult`
(`provider_id, kind, title, subtitle, snippet, pdf_path, page, url,
can_preview, can_save, source_label`) plus a `SearchProvider` protocol and a
`SearchService` that fans a query out to providers, isolating per-provider
failures (one failing source never hides the others — required by Phase 6).

## 5. Acceptance Tests

`tests/unit/test_search_service.py`, `tests/unit/test_search_strip.py`:

1. service: mock provider deterministic output; local provider resolves
   real PDF paths and pages against a migrated vault; missing-vault state;
   per-provider error isolation;
2. strip: all states render; debounce search path; open signal carries
   path+page; copy-link uses clipboard; disabled Save affordance; collapse
   toggling; RTL direction;
3. main window: strip present, Ctrl+K action registered (offscreen smoke).

## 6. Out of Scope (Phase 5)

- Real network adapters, download, validation, save-to-library (Phase 6).
- Search-grammar UI help beyond existing index filters (later refinement).

## 7. Implementation Record — 2026-09-15

- `services/search_service.py` implements the normalized result, provider,
  response, local-vault, mock, and provider-isolation contracts. The mock URLs
  use `example.invalid` and cannot preview or save; no network library or call
  exists in this module.
- `ui/widgets/search_strip.py` implements the collapsed/expanded Persian RTL
  widget, source filter, 350 ms debounce, explicit search, all documented
  states, compact rows, clipboard action, disabled Phase-6 save action, and a
  generation counter that discards stale thread results.
- The main window hosts the strip in a fixed bottom `QDockWidget`. This keeps
  the existing four-panel `QSplitter` unchanged as the central widget and
  places search between the workspace and status bar.
- Local searches open/close `KnowledgeIndex` inside the search thread. Search
  hit references now expose source hash and matched page where available so
  the provider can resolve the content-addressed PDF and the main window can
  navigate to the page.
- `Ctrl+K` is an application shortcut in the View menu and expands/focuses the
  query entry.

Verification performed in the implementation checkout:

- focused Phase-5/index/main-window regression: **48 passed**;
- thread lifecycle and stale-result focused checks: **28 passed**;
- full regression: **236 passed in 65.12 s**;
- `python -m compileall -q src tests`: passed;
- visible Windows run: collapsed strip, expanded strip, Ctrl+K, RTL order, and
  preservation of the four-panel workspace inspected successfully.

Not yet verified: opening a result from the owner's migrated real vault,
packaged/Nuitka executable behavior, DPI variants, or any real online provider.
Qt accessibility reported the old AI editor as focused even while the query
box visibly had focus, so automated Windows text entry is not claimed; the Qt
offscreen tests cover focusability, debounce, Enter/button path, and actions.
