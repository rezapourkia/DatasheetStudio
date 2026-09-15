# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Contributor:** ZCode (Z.ai, GLM)

**Branch:** `feature/datasheet-to-design-v2`

**Active phase:** Phase 6 — `REVIEW`

## Completed Result

Phases 1–5 were accepted for sequencing. Phase 5 was implemented by OpenAI
Codex (commit `f2215f4`) and re-verified in the current checkout by ZCode
(compile OK, full suite 236 passed, offscreen smoke) before Phase 6 began.
Phase 6 (online source adapter framework) is implemented, tested, and pushed:

- **Library → Online Sources Settings…** — enable DigiKey, store Client
  ID/Secret locally (QSettings; plain-text limitation documented), test the
  connection from a worker thread.
- **Bottom strip** — sources: همه / کتابخانهٔ محلی / DigiKey / نمایشی. Online
  rows with a datasheet URL offer **پیش‌نمایش** (validated temp download,
  opened in the viewer, nothing stored) and **ذخیره در کتابخانه**
  (validated download → content-addressed vault import → incremental index
  update → immediately searchable locally).
- Framework: shared domain types (`models/search.py`), concurrent
  cancellation-safe `SearchService`, bounded stdlib HTTP client
  (`infrastructure/web/http_client.py`: timeouts, 429 mapping, size caps,
  cancellation, %PDF signature), official DigiKey v4 adapter
  (`infrastructure/web/digikey.py`), `services/online_import.py`.
- Per-provider isolation preserved; unconfigured DigiKey is a guidance
  notice, not an error. Browser fallback untouched.

Recorded verification: full regression **258 passed in 66.39 s** (22 new
offline tests using a mocked HTTP transport), compile check and offscreen
startup smoke passed.

## Working Tree

Expected clean except ignored local artifacts (`build/`, `dist/`,
`dist-native/`, `.venv`, caches, crash reports, local PDFs). Never commit
those. Preserve any later uncommitted owner/agent work.

## Not Verified

- **The real DigiKey integration is UNTESTED** — no valid credentials were
  available; all network behavior is covered only through the mocked
  transport. Mark it tested only after the owner runs تست اتصال with real
  credentials.
- Secure OS key storage (ADR-009) remains pending; credentials are stored
  plainly in QSettings exactly like the current AI keys.
- The owner's real migrated vault flows (open Phase 4/5 review items:
  real-library migration, real-vault search) remain unexercised.

## Next Permitted Action

Stop at the Phase 6 owner-review gate. The owner should exercise DigiKey
with real credentials (**Library → Online Sources Settings… → تست اتصال**),
judge result usefulness, and try the preview/save flow in the bottom strip.
After acceptance, the next phase is Phase 7 — complete document text/OCR
coverage — starting with its own Markdown contract. Do not start Phase 7
before that.

## Required Reading for the Next Contributor

1. `AGENTS.md` if present at the repository/workspace boundary
2. `docs/HANDOFF.md`, `docs/DEVELOPMENT_PLAN.md`, and `docs/PRODUCT_VISION.md`
3. `docs/modules/ONLINE_ADAPTER_FRAMEWORK.md` (Phase 6 contract)
4. `docs/modules/BOTTOM_SEARCH_STRIP.md`, `KNOWLEDGE_INDEX.md`,
   `KNOWLEDGE_BASE_SCHEMA.md`, `LIBRARY_UPGRADE.md`
5. `docs/CURRENT_STATUS.md` (section 19 is the newest record) and
   `docs/WORK_LOG.md`
6. `docs/ARCHITECTURE.md` and `docs/DECISIONS.md`

## Verification Rule

Do not repeat the results above as current facts without rerunning the
relevant checks in the new checkout. Do not infer contributor identity from
Git author; use commit trailers and the append-only work log.
