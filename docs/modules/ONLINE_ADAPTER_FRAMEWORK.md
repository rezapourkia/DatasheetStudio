# Datasheet Studio — Online Source Adapter Framework (Phase 6)

**Status:** Active module contract

**Parent contracts:** `docs/modules/ONLINE_DATASHEET_SEARCH.md`,
`docs/modules/BOTTOM_SEARCH_STRIP.md`

**Plan reference:** Phase 6 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

Turn the Phase 5 search strip into a framework that can talk to permitted
online sources safely: provider-neutral coordination, one official adapter
(**DigiKey Product Information v4**), validated download with
preview-before-save, and explicit save into the v2 knowledge vault. The
browser dialog remains the fallback for sources without a permitted
programmatic interface.

## 2. Layering

```text
models/search.py                    SearchResult/Response, ProviderUnavailable (domain)
services/search_service.py          SearchService (concurrent, cancellation-safe),
                                    LocalKnowledgeProvider, MockOnlineProvider, factory
infrastructure/web/http_client.py   stdlib HTTP: timeout, size cap, cancellation,
                                    %PDF signature check, redirect/429 mapping
infrastructure/web/digikey.py       official DigiKey adapter (token + keyword search)
services/online_import.py           download → validate → preview/save into the vault
ui/dialogs/online_sources_dialog.py credentials & enable toggle (QSettings)
```

## 3. Provider Contract

Providers implement `search(query, *, limit) -> Sequence[SearchResult]` and
raise `ProviderUnavailable` for configuration/state problems (shown as a
notice, not an error). `SearchService` runs providers concurrently in a
bounded thread pool inside the strip's existing worker thread, keeps
per-provider failures isolated (one failing source never hides others),
preserves deterministic provider ordering, and accepts a `cancel_event`;
a cancelled search returns what completed plus a cancellation notice.

## 4. DigiKey Adapter (first official adapter)

- OAuth2 client-credentials token (`/v1/oauth2/token`) with in-memory cache
  and expiry, then `POST /products/v4/search/keyword`.
- Credentials are external configuration stored locally in `QSettings`
  (`onlineSources/digikeyEnabled|digikeyClientId|digikeyClientSecret`),
  never committed. Plain-text storage limitation is documented (same as the
  current AI keys; ADR-009 secure storage remains pending).
- Disabled/unconfigured ⇒ `ProviderUnavailable` pointing at
  **Library → Online Sources Settings…**.
- **The real DigiKey integration is UNTESTED in this phase** — no valid
  credentials were available here. Everything around it is tested with a
  mocked HTTP transport. The settings dialog has a **تست اتصال** button; the
  status must be marked tested only after the owner exercises it with real
  credentials.

## 5. Download Safety (preview before save)

`OnlineImportService`:

- `download_pdf(url)` streams to a temp folder with a 50 MB cap, cancellation
  checks, and a `%PDF-` signature check; returns path + SHA-256 + size +
  final URL.
- **پیش‌نمایش**: the downloaded temp PDF opens in the viewer; nothing is
  stored yet.
- **ذخیره در کتابخانه**: requires an **accepted** v2 vault; the object is
  imported content-addressed (duplicate PDFs resolve to the same object and
  are reported as duplicates), a document record is written, and the index is
  updated incrementally — the saved item must immediately appear in local
  search (tested). Saving never marks anything `verified`.
- No vault ⇒ clear error directing to **Library → Upgrade Library to v2…**.

## 6. Acceptance Tests (all offline, mocked transport)

`tests/unit/test_http_client.py`, `test_digikey_adapter.py`,
`test_online_import.py`, additions to `test_search_service.py` and
`test_search_strip.py`:

1. HTTP: success with redirect tracking; timeout; HTTP 429 rate-limit
   mapping; oversized download abort; mid-stream cancellation; non-PDF
   signature rejection.
2. DigiKey: unconfigured → unavailable notice; token+search happy path →
   normalized results with `can_save` when a datasheet URL exists; malformed
   JSON → clear error; 429 → rate-limited error.
3. Search service: concurrent execution keeps provider order; cancellation
   returns partial results + notice; provider isolation (existing).
4. Import: duplicate content → one object, duplicate reported; saved result
   findable via the local index; missing/unaccepted vault → clear errors.
5. Strip: online rows show پیش‌نمایش/ذخیره affordances wired to signals;
   source filter includes DigiKey.
6. Settings dialog: enable/credential round-trip in QSettings; test
   connection with an injected tester.

## 7. Out of Scope (Phase 6)

- Additional adapters (owner chooses the next provider at the review gate).
- Scraping of any kind; sources without permitted interfaces stay in the
  browser fallback.
- Secure OS key storage (ADR-009 pending decision).
