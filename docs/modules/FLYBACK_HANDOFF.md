# Datasheet Studio — Current-Datasheet Handoff to Flyback (Phase 10)

**Status:** Active module contract — **Plan:** Phase 10 in `docs/DEVELOPMENT_PLAN.md`

## Contract

1. `ToolContext` gains `source_hash` (SHA-256 of the currently open PDF, "" when
   none) and `controller_profile` (the newest `ControllerProfile` in the active
   vault bound to that hash, else `None`). `MainWindow._tool_context()` fills
   both; `KnowledgeVault.controller_profiles_for(source_hash)` scans
   `records/components/**/profile.json` envelopes.
2. The Flyback tool prefills a **new** dialog instance from the profile:
   `frequency_khz`, `current_limit_a`, `switch_voltage_limit_v`, `duty_max`,
   `ovp_threshold_v`, `switch_type`, `ic_id = part_number`. A banner shows
   controller identity + profile version + review status. Accepted
   (reviewed/verified) values are preferred; when only `extracted` values
   exist the banner explicitly says «بررسی‌نشده». Missing/partial profiles
   list the unknown required fields instead of failing.
3. **No silent mutation:** handoff only prefills new dialogs; saved
   `.flyback.json` files and open designs are never rewritten when the
   workspace PDF changes (tested byte-for-byte).
4. Without an open PDF the Flyback Designer still opens with manual defaults
   (regression-tested).

## Acceptance tests — `tests/unit/test_flyback_handoff.py`

Identity/revision handoff (hash + profile found), prefill of spin values +
banner, unknown-required listing, no-PDF manual open, PDF-change isolation
of a saved design.
