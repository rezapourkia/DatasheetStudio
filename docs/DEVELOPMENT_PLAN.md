# Datasheet Studio — Staged Development Plan

**Status:** Active execution plan

**Created:** 2026-09-15

**Authoritative product scope:** `docs/PRODUCT_VISION.md`

## 1. Why This Plan Exists

Development must remain safe to interrupt and easy to redirect. No phase is
allowed to spread unfinished assumptions across the whole application. Each
phase below produces one coherent, testable result and ends at an owner review
gate before the next phase begins.

The plan is repository-owned. Chat history is not a requirement source and a
future developer or AI agent must continue by reading this file, the product
vision, current status, architecture, decisions, and the active module contract.

## 2. Git and Review Protocol

Development uses the branch:

```text
feature/datasheet-to-design-v2
```

For every phase:

1. Mark only that phase as `IN PROGRESS` in this document.
2. Confirm the phase's allowed scope and acceptance criteria.
3. Implement the smallest complete vertical or infrastructure slice.
4. Run the listed automated checks and relevant regression tests.
5. Perform and record manual checks for visible desktop behavior.
6. Update the module contract and `docs/CURRENT_STATUS.md` with facts only;
   append `docs/WORK_LOG.md` and refresh `docs/HANDOFF.md`.
7. Inspect the complete diff and exclude secrets, databases, downloaded PDFs,
   caches, generated builds, test output, and unrelated working-tree changes.
8. Create one focused commit and push the branch to `origin`.
9. Report the commit hash, tests, limitations, and owner-visible behavior.
10. Stop at the review gate. Owner corrections are applied before the next
    phase; they do not accumulate until the end.

`main` is not changed during these phases. Merging to `main` is a separate,
explicit owner decision after a reviewable milestone. A phase may use more than
one commit only when a test/fix follow-up is required; all commits are pushed.

## 3. Status Vocabulary

| Status | Meaning |
|---|---|
| `PLANNED` | Scope documented; no implementation claim |
| `IN PROGRESS` | The only phase currently being changed |
| `REVIEW` | Implemented and pushed; waiting for owner review |
| `ACCEPTED` | Owner accepted the phase or explicitly allowed continuation |
| `BLOCKED` | Cannot continue safely; reason recorded |

Only one phase may be `IN PROGRESS`. Later phases remain `PLANNED` even if
prototype code happens to exist.

## 3.1 Multi-AI Contributor and Handoff Protocol

Different phases, fixes, or reviews may be performed by different AI systems.
Git's configured author name is not sufficient evidence of which system did
the work. Every contributor, human or AI, must use all three records below:

1. **Commit trailer:** every commit includes the applicable trailers:

   ```text
   Phase: 02
   AI-Agent: OpenAI Codex
   AI-Role: implementation-and-test
   Human-Owner: Reza
   ```

   `AI-Agent` and `AI-Role` are omitted for fully human work. The agent records
   only an identity it actually knows; model/version is not guessed. Multiple
   agents are listed with repeated `AI-Agent`/`AI-Role` trailers or explained in
   the work log.

2. **Append-only work log:** `docs/WORK_LOG.md` records date, phase, contributor,
   requested scope, files/areas changed, checks actually run, unverified claims,
   and the resulting commit reference (`this commit` is allowed in the entry
   committed with the work). Existing entries are never rewritten to transfer
   credit; corrections are new entries.

3. **Current handoff:** `docs/HANDOFF.md` is the small mutable resume point. At
   every pause, quota boundary, provider change, blocked state, or review gate,
   it records branch, active phase/status, last completed result, working-tree
   state, known problems, exact next permitted action, and required reading.

Before changing files, a new AI contributor must:

- read `AGENTS.md`, `docs/HANDOFF.md`, this plan, the product vision,
  architecture, current status, decisions, and the active module contract;
- inspect Git branch/status/log and preserve any uncommitted user or prior-agent
  work;
- verify important prior claims from repository evidence and tests instead of
  trusting chat summaries;
- identify itself in a new work-log entry and commit trailers;
- update the handoff before it stops, even when stopping because of quota or a
  failed external service.

Chat transcripts, provider memory, and proprietary task state are never the
only location of a requirement, decision, test result, or unfinished action.

## 4. Global Non-Negotiable Rules

- Preserve the native PySide6 desktop application and Persian RTL workflow.
- Normal user operation must never require CLI commands.
- Requirements, module contracts, decisions, and handoff remain Markdown-first.
- JSON is used for typed/versioned engineering data; SQLite is a rebuildable
  search and transaction index, not the sole copy of irreplaceable knowledge.
- AI-extracted or imported data is not automatically verified.
- Deterministic, unit-tested engines own engineering calculations.
- Every accepted numerical fact retains source, revision, page/table,
  conditions, unit, uncertainty/review state, and parser version where relevant.
- Existing PDFs, notes, library data, and projects must not be deleted or
  silently rewritten during upgrades.
- Optional network/AI/provider failures must not break PDF reading or saved
  offline calculations.
- Do not commit user PDFs, local databases, API keys, logs, build folders, or
  generated application packages.

## 5. Phase Map

| Phase | Name | Status | Reviewable result |
|---:|---|---|---|
| 0 | Product contract and staged plan | `ACCEPTED` | Product vision, architecture direction, and this execution plan pushed |
| 1 | Stabilize and preserve current baseline | `ACCEPTED` | Existing native Flyback v1/tool registry changes tested and pushed separately |
| 2 | Knowledge-base domain and schema | `ACCEPTED` | Versioned records, hashes, provenance, revisions, and validation without UI migration |
| 3 | Rebuildable SQLite/FTS index | `REVIEW` | Fast metadata/full-text index that can be deleted and rebuilt safely |
| 4 | Safe Library v1 → v2 desktop upgrade | `PLANNED` | Preview, backup, import, rollback, and no-delete migration UI |
| 5 | Bottom search strip UX shell | `PLANNED` | Collapsible bottom search using mock/local adapter data for UX approval |
| 6 | Online source adapter framework | `PLANNED` | Provider-independent search, normalized results, safe download, first official adapter |
| 7 | Complete document text/OCR coverage | `PLANNED` | Page coverage ledger and pluggable OCR boundary |
| 8 | Controller profile and evidence schema | `PLANNED` | Strict reusable IC profile with field-level citations and review states |
| 9 | AI extraction artifacts and review UI | `PLANNED` | Versioned MD prompt, validated response, diff/review/accept flow |
| 10 | Current-datasheet handoff to Flyback | `PLANNED` | Open PDF/profile becomes explicit Flyback project context |
| 11 | Flyback domain v2 outputs and scenarios | `PLANNED` | Unbounded domain outputs, isolation groups, load/tolerance scenario matrix |
| 12 | Real magnetics catalogue foundation | `PLANNED` | Exact core/material/bobbin records, source packs, cache/update UI |
| 13 | Transformer feasibility and alternatives | `PLANNED` | Physical constraints and deterministic nearby-core ranking |
| 14 | Per-output rectifier/capacitor analysis | `PLANNED` | Ripple, RMS, ESR, diode stress/loss for every rail and scenario |
| 15 | Transformer, switch, clamp, and thermal loss | `PLANNED` | Corner-case loss budget and thermal iteration with explicit unknowns |
| 16 | Multi-output cross-regulation model | `PLANNED` | Asymmetric isolated-output load cases and regulation report |
| 17 | Feedback and optocoupler topology model | `PLANNED` | Controller-bound PSR/single/multiple/series/parallel feedback analysis |
| 18 | Contextual Flyback AI chat | `PLANNED` | Datasheet/calculation-aware chat with cited proposals and accepted diffs |
| 19 | Reports, usability, packaging, and release gate | `PLANNED` | Reproducible report, backup, RTL UX pass, packaged-app verification |

## 6. Phase Contracts

### Phase 0 — Product Contract and Staged Plan

**Scope**

- Record the corrected end-to-end product definition.
- Record knowledge-base, online-search, and AI engineering contracts.
- Record architectural decisions and the staged delivery plan.
- Do not implement application behavior.

**Acceptance**

- Planned and implemented behavior are clearly separated.
- The database recommendation, AI/engine boundary, Git protocol, and every
  requested flyback capability have a durable Markdown home.
- Markdown links resolve and `git diff --check` passes.
- The documentation-only commit is pushed to the feature branch.

**Review gate**

The owner reviews phase order, database direction, and AI responsibility before
baseline code is committed or new infrastructure is implemented.

### Phase 1 — Stabilize and Preserve Current Baseline

**Scope**

- Review the currently uncommitted native Tool Registry and Flyback Designer v1
  changes already present in the workspace.
- Exclude crash reports, packages, user data, and unrelated artifacts.
- Run the full regression suite, syntax/compile checks, and application startup.
- Update documentation to describe only verified current behavior.
- Commit and push the baseline independently from Phase 0.

**Acceptance**

- Tool Registry and Flyback v1 tests pass.
- Full project regression passes.
- The desktop application starts with the registered tools.
- No illustrative component/core is marked verified.
- The commit contains no generated executable, PDF, database, or secret.

**Review gate**

The owner can install/run the preserved baseline and request UI corrections
before Knowledge Base v2 work begins.

### Phase 2 — Knowledge-Base Domain and Schema

**Scope**

- Add domain types for immutable source objects, document revisions, aliases,
  provenance/evidence, component profiles, review states, and library identity.
- Add canonical serialization and validation.
- Add SHA-256 streaming hash service and duplicate identity rules.
- Do not change the current library UI or move user files.

**Acceptance**

- Round-trip, invalid-schema, hash, duplicate, path-safety, and upgrade-version
  unit tests pass.
- Unknown fields are preserved or rejected according to a documented rule.
- No network or Qt dependency exists in domain tests.

**Review gate**

Owner reviews example records for DK124 and one EE19/17 core before storage is
built around the schema. Examples stay explicitly unverified.

### Phase 3 — Rebuildable SQLite/FTS Index

**Scope**

- Create the rebuildable SQLite index adapter and FTS tables.
- Index metadata, aliases, tags, summaries, page text, normalized parameters,
  magnetics fields, and project references.
- Provide atomic rebuild and corruption recovery services.
- Keep Markdown/JSON/files as the durable source of truth.

**Acceptance**

- Index create/update/delete/rebuild and transaction rollback tests pass.
- Deleting the index and rebuilding produces equivalent search results.
- Search returns matching document/page/field context.
- A large synthetic library performance test has a recorded result and does not
  freeze the UI thread in integration design.

**Review gate**

Owner reviews search syntax and result ordering using representative part/core
queries before migration UI begins.

### Phase 4 — Safe Library v1 → v2 Desktop Upgrade

**Scope**

- Detect a `library.json` library and show a migration preview.
- Create a recoverable backup; copy/hash/import without deleting originals.
- Report duplicates, ambiguous records, skipped files, and failures.
- Allow cancel and rollback from the desktop UI.

**Acceptance**

- Migration tests cover success, interruption, invalid PDF, duplicate files,
  permission failure, and rollback.
- The old library remains usable until explicit final acceptance.
- No CLI step is required.

**Review gate**

Owner tests a copy of a real library. Migration is not offered to all users
until that review is accepted.

### Phase 5 — Bottom Search Strip UX Shell

**Scope**

- Add a Persian RTL, collapsible bottom search strip to the main window.
- Use deterministic mock/local results only.
- Implement query, source filter, compact result rows, loading/empty/error
  states, Preview/Open, Save, and Copy Link affordances.
- Preserve the existing browser dialog as fallback.

**Acceptance**

- UI tests cover state changes and actions.
- Manual review confirms splitter behavior, keyboard focus, scaling, RTL order,
  and that the strip does not obscure normal PDF work.
- No real provider or credential is required.

**Review gate**

Owner approves layout and interaction before network adapters are connected.

### Phase 6 — Online Source Adapter Framework

**Scope**

- Define provider capabilities and normalized search-result records.
- Add concurrent cancellation-safe search coordination outside the UI thread.
- Add URL/content/PDF-signature/size/hash validation and preview-before-save.
- Implement one official or explicitly permitted source adapter first; retain
  browser fallback for unsupported sources.

**Acceptance**

- Mocked network tests cover timeout, malformed result, rate limit, duplicate,
  bad content, redirect, cancellation, and partial provider failure.
- A real integration is marked tested only if manually exercised with valid
  configuration; otherwise documentation says untested.
- One provider failure does not hide other results.

**Review gate**

Owner reviews real result usefulness and chooses the next provider adapter.

### Phase 7 — Complete Document Text/OCR Coverage

**Scope**

- Record page-by-page extraction status and normalized page markers.
- Detect text-poor/scanned pages.
- Add a replaceable OCR adapter boundary and background progress/cancellation.
- Store extracted artifacts by source hash.

**Acceptance**

- Mixed searchable/scanned/failed page fixtures produce a correct coverage
  ledger.
- “Complete document” cannot be claimed while a page is unaccounted for.
- Reopening a previously extracted source reuses compatible cached artifacts.

**Review gate**

Owner reviews extraction from representative DK124/DK125/TMG0656 documents.

### Phase 8 — Controller Profile and Evidence Schema

**Scope**

- Define controller identity/revision/package, limits, timing, switch model,
  startup/bias, protection, feedback, operating modes, application constraints,
  equations, and missing/contradictory facts.
- Attach evidence and review state to each field.
- Provide unit/range/condition validation and versioned upgrades.

**Acceptance**

- Complete, partial, contradictory, wrong-unit, wrong-page, and unsupported-mode
  fixtures are tested.
- AI/import cannot create a `verified` field.
- Engine-facing views expose only accepted values and explicit unknowns.

**Review gate**

Owner approves the editable Persian profile form and extracted field set before
AI automation is added.

### Phase 9 — AI Extraction Artifacts and Review UI

**Scope**

- Add versioned Markdown extraction prompt templates and JSON response schemas.
- Send complete page-aware context only after explicit user action/consent.
- Archive request, response, provider/model metadata, validation result, and
  source hashes.
- Show extracted/current values as a reviewable diff with citations.

**Acceptance**

- Mock provider tests cover invalid JSON, missing units, bad citations, token
  truncation, cancellation, retry, and provider failure.
- No field enters the reusable profile without explicit acceptance.
- A saved profile can be reused offline.

**Review gate**

Owner reviews one end-to-end real controller extraction before broadening the
prompt or providers.

### Phase 10 — Current-Datasheet Handoff to Flyback

**Scope**

- Extend `ToolContext` with stable current-document/revision/profile references.
- Open Flyback Designer from an active datasheet without manual re-entry.
- Handle missing, partial, changed, or unreviewed profiles explicitly.

**Acceptance**

- Handoff identity and revision tests pass.
- Opening Flyback without a PDF still works with manual data.
- Changing the open PDF does not silently mutate an existing design.

**Review gate**

Owner verifies the PDF → Tools → Flyback flow and controller identity display.

### Phase 11 — Flyback Domain v2 Outputs and Scenarios

**Scope**

- Replace the UI-only eight-output limit with an unbounded domain collection.
- Add output IDs, names, voltage/current/load range, isolation group, priority,
  rectifier/capacitor references, and feedback participation.
- Add min/nominal/max bus, load, temperature, and tolerance scenarios.
- Upgrade saved projects without losing v1 data.

**Acceptance**

- Project upgrade/round-trip and many-output tests pass.
- Power accounting is correct across scenarios and isolation groups.
- UI remains usable with a realistically large output list.

**Review gate**

Owner builds representative one-output, dual-isolated, and multi-output designs
before magnetics integration.

### Phase 12 — Real Magnetics Catalogue Foundation

**Scope**

- Model exact core halves/sets, material, gap option, compatible bobbin,
  geometry, curves/coefficients, tolerances, and per-field provenance.
- Add versioned downloadable source packs with manifest, hash, signature/version,
  cache, update preview, and rollback.
- Add search/filter/select UI; generic `EE19` remains only an alias.

**Acceptance**

- Catalogue validation rejects missing units, invalid curve domains, incompatible
  bobbins, and mixed-manufacturer assumptions.
- Offline cached data works.
- Imported data is `extracted` or `reviewed`, never silently `verified`.

**Review gate**

Owner checks exact ordering codes and drawings for the first supported core
family before additional packs are added.

### Phase 13 — Transformer Feasibility and Alternatives

**Scope**

- Add layer-aware winding, insulation/margin, pin/bobbin, fill, gap, flux,
  current-density, skin/proximity, leakage-assumption, and thermal constraints.
- Explain every failed constraint.
- Rank nearby real core/material/bobbin candidates deterministically.

**Acceptance**

- Numerical fixtures cover feasible, fill-limited, flux-limited, thermal-limited,
  insulation-limited, and missing-data cases.
- Candidate ranking is reproducible and exposes its score components.
- AI may explain or rerank by user priorities but cannot invent candidates.

**Review gate**

Owner compares several known transformer designs and approves the usefulness of
failure explanations and alternatives.

### Phase 14 — Per-Output Rectifier and Capacitor Analysis

**Scope**

- Calculate diode voltage/current stress, conduction/recovery loss, capacitor
  capacitance, ripple, RMS current, ESR loss, voltage margin, and estimated
  temperature impact for every rail and scenario.
- Add input bulk capacitor ripple/RMS and bus valley calculations.

**Acceptance**

- All outputs are analyzed independently.
- Min/max input and asymmetric load cases are tested.
- Missing ESR/ripple-current/thermal data remains unknown and visible.

**Review gate**

Owner checks results against at least one known supply or external calculation.

### Phase 15 — Transformer, Switch, Clamp, and Thermal Loss

**Scope**

- Expand copper/core loss across frequency, waveform, flux, and temperature.
- Add controller/internal switch or external MOSFET loss as selected by the
  exact profile.
- Add RCD/TVS/clamp/snubber stress, loss, tolerances, and leakage-energy cases.
- Iterate component/core temperature only where thermal data is available.

**Acceptance**

- Corner-case total loss budget reconciles component contributions.
- Curve extrapolation is prohibited or visibly warned.
- Numerical tests compare independent reference fixtures.

**Review gate**

Owner reviews loss breakdown and worst-case identification before regulation
models build on it.

### Phase 16 — Multi-Output Cross-Regulation Model

**Scope**

- Model coupling/leakage and winding resistance inputs needed for static
  cross-regulation estimates.
- Generate asymmetric cross-load cases, including one isolated output at full
  load while another is lightly loaded.
- Report limitations separately from transient loop behavior.

**Acceptance**

- Symmetric and asymmetric multi-output fixtures pass.
- Results state model sensitivity and unavailable coupling data.
- Static estimates are not mislabelled as transient simulation.

**Review gate**

Owner compares a dual-isolated design with measured or trusted reference data.

### Phase 17 — Feedback and Optocoupler Topology Model

**Scope**

- Represent PSR, primary regulation, single regulated output, weighted feedback,
  and multiple optocoupler networks as explicit topologies.
- Support series/parallel primary-side optocoupler arrangements only when the
  controller feedback-pin model and voltage/current headroom permit analysis.
- Include CTR tolerance/aging/temperature, TL431/reference networks, dominance,
  compliance, and fault states.

**Acceptance**

- Topology validation rejects physically incomplete or controller-incompatible
  networks.
- Scenario tests identify which output dominates regulation.
- Series/parallel labels alone are insufficient; the actual connection graph
  and component parameters are required.

**Review gate**

Owner reviews schematics/results for single-opto, dual parallel, dual series,
weighted, and primary-regulated examples.

### Phase 18 — Contextual Flyback AI Chat

**Scope**

- Embed chat in the Flyback form with access to accepted datasheet evidence,
  active project, scenario results, warnings, and candidate list.
- Let AI request deterministic tool runs and propose changes as a visible diff.
- Archive consequential requests/responses as Markdown artifacts.

**Acceptance**

- AI citations open the relevant PDF page or result section.
- Proposed edits require acceptance and are reversible.
- Chat failure never blocks calculation or project open/save.

**Review gate**

Owner evaluates whether the chat reduces work without hiding engineering state.

### Phase 19 — Reports, Usability, Packaging, and Release Gate

**Scope**

- Produce a reproducible design report with sources, assumptions, scenario
  matrix, transformer plan, losses, stresses, warnings, and review states.
- Add library/project backup and restore.
- Complete Persian RTL, keyboard, scaling, performance, accessibility, and
  visual-consistency passes.
- Build and manually test the packaged Windows application.

**Acceptance**

- A fresh packaged installation can open a library and reproduce a saved design
  without CLI or AI.
- Backup/restore and report-open/print workflows are manually verified.
- Known unvalidated engineering/provider behavior is documented honestly.

**Review gate**

Owner performs the final daily-workflow acceptance pass before merge/release.

## 7. Change Control

Owner feedback at a review gate may:

- correct the just-finished phase within the same phase;
- split the next phase into smaller phases;
- reorder future phases when dependencies remain valid;
- defer a provider, solver, or UI variant;
- reject an implementation and restore the previous pushed commit.

When the plan changes, edit this file first, record a decision if architecture
changes, commit the plan correction separately, and push it before continuing.

## 8. Current Action

Phase 2 was accepted by the owner (2026-09-15). Phase 3 (rebuildable
SQLite/FTS index) is implemented, tested, and pushed; it is awaiting the
owner review gate: search syntax and result ordering with representative
part/core queries (see `docs/modules/KNOWLEDGE_INDEX.md` §5–§6). Recorded
verification: full regression **206 passed in 66.20 s** (19 new index tests
including rollback, atomic-rebuild equivalence, corruption recovery, and a
1,500-document performance fixture: build ≈ 0.2 s, queries ≤ 4 ms). Do not
begin Phase 4 until the owner accepts the Phase 3 review.
