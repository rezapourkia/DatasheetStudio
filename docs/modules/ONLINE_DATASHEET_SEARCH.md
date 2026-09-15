# Datasheet Studio — Bottom Online Datasheet Search

**Status:** Planned replacement/extension of the current browser dialog

## 1. User Experience

A compact, collapsible strip at the bottom of the main Datasheet Studio window
contains a part-number search field. Results expand above the strip without
covering the PDF workspace and can be collapsed with one click.

Each result shows source, manufacturer, exact part number, short description,
document revision/date when available, and whether a direct PDF is available.
Actions are **Preview/Open**, **Save to Library**, and **Copy Link**.

## 2. Search Architecture

```text
UI query → SearchService → enabled source adapters → normalized result model
→ deduplication/ranking → preview → explicit download → validation → library
```

Adapters declare capabilities: search, metadata, direct PDF, authentication,
rate limit, and terms/licence notes. Official APIs and manufacturer catalogues
are preferred. A source without a permitted programmatic interface opens in a
normal browser rather than being scraped.

Initial adapters should be chosen independently of the UI. DigiKey exposes an
[official Product Information API](https://developer.digikey.com/products/product-information-v4/productsearch/productdetails?prod=true),
while manufacturer catalogues can provide authoritative document links.
Credentials, quotas, and availability are external configuration and must be
reported honestly.

## 3. Download Safety

- Downloads occur only after an explicit user action.
- Content type, PDF signature, size limit, final URL, and SHA-256 are checked.
- A downloaded file opens as a temporary preview before library acceptance.
- The Add-to-Library dialog shows detected part, manufacturer, revision, tags,
  and duplicates before committing.
- Saving does not imply engineering verification.

## 4. Acceptance Criteria

- Search is available without leaving the main document workspace.
- One failing provider does not discard results from other providers.
- Duplicate PDFs are detected by content hash.
- A saved result immediately appears in local search and can be opened.
- With no configured API, permitted links and browser fallback remain usable.
