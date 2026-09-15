# Datasheet Studio — Current Handoff

**Updated:** 2026-09-15

**Contributor:** ZCode (Z.ai, GLM)

**Branch:** `feature/datasheet-to-design-v2`

**Active phase:** Phase 11 — `REVIEW`

## Completed Result

Phases 1–7 were accepted. Phase 8 (controller profile schema) and Phase 9 (AI extraction artifacts + review UI) are implemented, tested, and pushed per their contracts:

- `models/controller_profile.py` — strict field registry (~27 fields with
  units/ranges/enums; required: frequency_khz, current_limit_a,
  switch_voltage_limit_v), Phase 2 evidence/review states, the AI cap
  (`from_extraction` rejects reviewed/verified inputs), and
  `engine_view()` exposing only accepted values + explicit unknowns and
  contradictions (the future Flyback-engine contract). Versioned envelope
  (`controller-profile`, schema 2).
- `KnowledgeVault.write_controller_profile` stores
  `records/components/<maker>/<part>/<version>/profile.json` and upserts
  the index (profiles searchable).
- Registered tool **Tools → Knowledge Base → پروفایل کنترلر…** — editable
  Persian RTL form (value/unit/review-state/page+table per field,
  open/save to vault or JSON).

Recorded verification: full regression **293 passed in 68.24 s** (16 new
tests), compile check and offscreen startup smoke passed (four tools).

## Working Tree

Expected clean except ignored local artifacts (`build/`, `dist/`,
`dist-native/`, `.venv`, caches, crash reports, local PDFs). Never commit
those. Preserve any later uncommitted owner/agent work.

## Not Verified

- A real OCR engine (none selected yet — owner decision: e.g. Tesseract or
  an AI OCR service; the adapter boundary is ready).
- Coverage runs against the owner's real DK124/DK125/TMG0656 documents
  (Phase 7 review gate).
- Open items inherited from earlier gates: real DigiKey credentials, the
  owner's real-library migration/vault flows.
- `chunks.json` / `evidence.json` artifacts are intentionally out of scope
  (later phases).

## Next Permitted Action

Stop at the Phase 8 owner-review gate. The owner should open
**Tools → Knowledge Base → پروفایل کنترلر…** and approve the editable form
and the extracted field set (sections, units, enums, required fields).
Corrections stay within Phase 8. After acceptance, the next phase is
Phase 9 — AI extraction artifacts and review UI — starting with its own
Markdown contract. Do not start Phase 9 before that.

## Required Reading for the Next Contributor

1. `AGENTS.md` if present at the repository/workspace boundary
2. `docs/HANDOFF.md`, `docs/DEVELOPMENT_PLAN.md`, and `docs/PRODUCT_VISION.md`
3. `docs/modules/CONTROLLER_PROFILE_SCHEMA.md` (Phase 8 contract)
3b. `docs/modules/TEXT_EXTRACTION_COVERAGE.md` (Phase 7 contract)
4. `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`, `KNOWLEDGE_INDEX.md`,
   `LIBRARY_UPGRADE.md`, `ONLINE_ADAPTER_FRAMEWORK.md`
5. `docs/CURRENT_STATUS.md` (section 25 is the newest record) and
   `docs/WORK_LOG.md`
6. `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` (incl. ADR-021)

## Verification Rule

Do not repeat the results above as current facts without rerunning the
relevant checks in the new checkout. Do not infer contributor identity from
Git author; use commit trailers and the append-only work log.
