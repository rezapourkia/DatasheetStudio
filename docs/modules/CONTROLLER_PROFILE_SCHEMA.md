# Datasheet Studio — Controller Profile and Evidence Schema (Phase 8)

**Status:** Active module contract

**Parent contracts:** `docs/modules/KNOWLEDGE_BASE_SCHEMA.md` (evidence
fields, review states), `docs/modules/AI_ENGINEERING_WORKFLOW.md`

**Plan reference:** Phase 8 in `docs/DEVELOPMENT_PLAN.md`

## 1. Purpose

Define the strict, reusable schema for a switching-controller IC profile:
identity, limits, timing, switch model, startup/bias, protection, feedback,
operating mode, and application constraints — each field carrying evidence
(page/table), unit, min/typ/max, conditions, and review state. The Flyback
engine will consume **only accepted values plus explicit unknowns**; AI
extraction (Phase 9) can fill fields but never verify them.

## 2. Field Registry

`models/controller_profile.py` defines `FIELD_SPECS`: canonical name →
`FieldSpec(section, label_fa, kind, unit, minimum, maximum, enum_values,
required)`. Unknown field names are rejected. Numeric values are range- and
unit-checked against the spec; enum fields must use allowed values. Required
fields: `frequency_khz`, `current_limit_a`, `switch_voltage_limit_v`.
Sections: limits, timing, switch, startup, protection, feedback, mode,
application.

## 3. Profile Record

`ControllerProfile` reuses the Phase 2 `EvidenceField` (value/unit/min-typ-
max/conditions/provenance/review_state) plus identity (manufacturer, part
number, package, source hash/revision, profile version), explicit
`contradictions` and `unknown_facts`, and envelope serialization
(`record_kind: "controller-profile"`, schema version 2; unsupported versions
are rejected — upgrades are explicit functions, never silent).

## 4. Review States and the AI Cap

Phase 2 rules apply unchanged: `verified` requires reviewer + timestamp;
`ControllerProfile.from_extraction(...)` (the AI/import path) **rejects any
field already marked reviewed/verified** — automation may only produce
`unreviewed`/`extracted`. The human form (this phase) performs promotions.

## 5. Engine View

`profile.engine_view()` returns:

- `values`: only fields whose review state is `reviewed` or `verified`
  (the "accepted" set), each with unit and evidence page;
- `unknowns`: spec'd fields with no accepted value — the engine must treat
  them as unknowns, never zeros;
- `contradictions` and `unsupported` notes as-is.

## 6. Storage and UI

- `KnowledgeVault.write_controller_profile(profile)` stores
  `records/components/<maker>/<part>/<profile-version>/profile.json`
  (envelope) and upserts the Phase 3 index (`components` table), making
  profiles searchable (e.g. `maker:linkage dk124`).
- Registered tool **Tools → Knowledge Base → پروفایل کنترلر…** opens the
  editable Persian RTL form for the open document: grouped sections, per-
  field value editor, unit label, review-state selector (verified prompts
  for reviewer), evidence page/table inputs, contradiction/unknown notes,
  open/save (vault when active, JSON file otherwise).

## 7. Acceptance Tests

`tests/unit/test_controller_profile.py`, `test_controller_profile_dialog.py`:

1. complete fixture → engine view has all required accepted values, no
   required unknowns;
2. partial fixture → missing/extracted-only fields listed as unknowns;
3. contradictory fixture → contradictions surfaced by the engine view;
4. wrong unit (e.g. Hz vs kHz) → rejected;
5. wrong page (0) → rejected (Phase 2 provenance rule exercised);
6. unsupported operating mode → rejected;
7. out-of-range numeric → rejected;
8. `from_extraction` with a verified field → rejected (AI cap);
9. vault round-trip: saved profile validates, is indexed, and searchable;
10. dialog: loads spec'd sections, editing updates value, verified flow
    requires reviewer, save writes a loadable file (offscreen).

## 8. Out of Scope (Phase 8)

- AI prompt/automation (Phase 9), Flyback consumption (Phase 10+), curve
  data (loss coefficients), and auto-detection of fields from PDF text.
