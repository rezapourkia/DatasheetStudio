# Datasheet Studio — Flyback Domain v2 Outputs and Scenarios (Phase 11)

**Status:** Active module contract — **Plan:** Phase 11 in `docs/DEVELOPMENT_PLAN.md`

## Contract

1. **64-output-capable (not unbounded — review correction):** the old 1–8
   output cap is removed; the domain and UI accept up to 64 outputs (a clear
   error above that), the engine validates ≥ 1. Missing rail/scenario
   EDITORS (isolation group, load range, priority, rectifier/capacitor
   references, feedback participation, per-scenario editing) are domain
   fields today but NOT yet user-editable desktop inputs — an explicitly
   open item before the multi-output workflow is claimed usable.
2. **Extended `OutputSpec`** (all defaulted, so v1 projects keep loading):
   `output_id`, `isolation_group` (default `"main"`), `priority`,
   `load_min_a`/`load_max_a` (load range), `rectifier_id`,
   `capacitor_id`, `feedback` (participation in regulation).
   Validation: non-empty groups, `load_min ≤ load_max`, non-negative
   priority.
3. **Scenarios:** `ScenarioSpec(name, bus_v, load_fraction, ambient_c)`;
   projects default to min/nom/max-bus scenarios at full load.
4. **Power accounting:** pure `power_summary(project, scenarios)` returns
   per-scenario rows with per-output power (`V × I × load_fraction`),
   per-isolation-group sums, and totals — deterministic and unit-tested.
5. **Persistence:** envelope `schema_version` stays 1 with tolerant
   defaults; v1 files load unchanged (upgrade without data loss, tested),
   v2 fields round-trip.
6. UI keeps the editable four-column table for name/voltage/current/drop;
   extended fields and scenario editing arrive with the Phase 11/14 UI
   refinement; the large-list behavior is scrollable + capped at 64.

## Acceptance tests — `tests/unit/test_flyback_domain_v2.py`

v1 upgrade round-trip, 64-output acceptance, >64 rejection, group/load
validation, per-scenario/isolation power accounting correctness.
