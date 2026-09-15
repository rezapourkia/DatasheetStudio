# Datasheet Studio — AI Extraction Artifacts and Review UI (Phase 9)

**Status:** Active module contract — implements
`docs/modules/AI_ENGINEERING_WORKFLOW.md` for controller profiles

**Plan reference:** Phase 9 in `docs/DEVELOPMENT_PLAN.md`

## Contract

0. **Complete-document rule (review P1, 2026-09-15):** extraction is driven
   by the Phase-7 coverage ledger and is chunked — `chunk_plan` splits ALL
   pages (no 40-page/4k-character caps anymore; `build_user_message` passes
   page text in full). `extract_complete` merges chunks deterministically
   (first occurrence wins) and records conflicts as contradictions with both
   values/pages. Pages not accounted for by the ledger are reported as
   `omitted_pages`, and the run can never claim `complete` while any page is
   unaccounted for. Every chunk request/response plus `merge.md` and
   `metadata.json` are archived under `ai-runs/<run-id>/chunks/…`. The
   review dialog uses this path and shows omitted pages explicitly.
1. **Versioned prompt:** `src/datasheet_studio/prompts/controller_extraction_v1.md`
   (`PROMPT_VERSION = controller_extraction_v1`) defines the strict JSON
   response shape, allowed-field rule, unit and page-citation requirements,
   contradiction handling, and truncation warnings. The user message is
   built by `build_user_message` from the Phase 7 page-aware text with
   `<!-- page:N -->` markers.
2. **Explicit consent:** sending document text to the provider happens only
   after the dialog's consent checkbox + button (never automatic).
3. **Validation** (`parse_response`): invalid JSON, truncation (JSON decode
   position), unknown field names, wrong units, and out-of-range page
   citations become structured `ExtractionIssue`s — the run stays usable if
   some candidates validate.
4. **Acceptance gate:** `accepted_profile` builds the reusable profile from
   ONLY the fields the reviewer ticked, each with review state `extracted`
   (never reviewed/verified — the Phase 8 AI cap applies) and provenance
   `ai:<prompt-version>:<run-id>` with the model's confidence. Unticked or
   issue-carrying fields do not enter the profile (dialog unticks them).
5. **Archived artifacts:** each run is stored under the vault at
   `ai-runs/<run-id>/` — `request.md`, `response.md`, and `metadata.json`
   (prompt version, provider, model, source hash, validation result,
   issues, candidate names). Without an active vault, archiving is skipped.
6. **Offline reuse:** saved profiles load in the Phase 8 form and the index
   without any network.
7. **Transport failures** (provider error, pre-send cancellation) surface
   as clear messages with a retry button; they never write partial state.

## Acceptance (tested in `tests/unit/test_controller_extraction.py`)

Invalid JSON, truncation, missing unit, bad citation, unknown field,
pre-send cancellation, provider failure wrapping, acceptance gating (only
ticked fields; all `extracted`; engine view empty until human review),
vault storage + offline reload, and artifact archiving.

## Out of scope

Real-provider execution quality (owner review gate with a real controller
document), multi-provider prompt variants, and diff-against-existing
profile editing (next refinement).
