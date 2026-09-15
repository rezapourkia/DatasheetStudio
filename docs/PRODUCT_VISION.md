# Datasheet Studio — Product Vision and Owner Workflow

**Status:** Authoritative product direction

**Owner correction recorded:** 2026-09-15

**Audience:** maintainers, AI coding agents, reviewers, and test authors

Implementation order and Git review gates are defined in
`docs/DEVELOPMENT_PLAN.md`.

## 1. Product Definition

Datasheet Studio is not only a PDF reader and Flyback Designer is not a
stand-alone calculator. The product is a persistent engineering workspace that
turns a real component datasheet into a traceable power-supply design.

The primary workflow is:

```text
find/open PDF → understand and archive it → build a reviewed component profile
→ open an engineering tool with that profile → enter design intent
→ run deterministic calculations and scenario analysis
→ use AI for extraction, explanation, and guided alternatives
→ save a reproducible design and report
```

The application is expected to be used every day. Simplicity, a calm Persian
RTL interface, low click count, beauty, local ownership of data, and long-term
extensibility are product requirements rather than later polish.

## 2. Canonical Flyback User Journey

1. The user opens a controller datasheet such as DK124, DK125, or TMG0656.
2. Normal Datasheet Studio work remains available: reading, bookmarks, selected
   pages, notes, library storage, and datasheet chat.
3. The user opens **Flyback Designer**. The tool receives the identity and
   revision of the currently open datasheet; the user does not reselect or
   manually copy it.
4. On explicit request, AI reads the complete document (including OCR when
   required) and extracts a controller profile. Every extracted value includes
   unit, min/typ/max where applicable, operating/test conditions, page/table
   evidence, and confidence. AI extraction is never automatically verified.
5. The user reviews and accepts or corrects the profile. A reviewed profile is
   reusable without calling AI again.
6. The user adds as many output rails as the design needs. Each rail records
   voltage, current, isolation group, rectifier/capacitor choices, load range,
   priority, and feedback participation. The domain model must not impose the
   current UI limit of eight outputs.
7. The user selects an exact manufacturer core/core-set, material, gap option,
   and compatible bobbin, for example an exact EE19/17 ordering code rather
   than a generic name.
8. The numerical engine checks whether the transformer is feasible in that
   exact magnetic assembly. If not, it explains the binding constraints and
   ranks nearby real alternatives.
9. The engine evaluates minimum, nominal, and maximum input/load/temperature
   cases, plus user-defined cross-load scenarios for isolated multi-output
   supplies.
10. Transformer copper/core loss, switch/controller loss, rectifier loss,
    clamp/snubber stress and loss, input/output capacitor ripple/RMS/ESR loss,
    and thermal margins are calculated where the required verified inputs
    exist. Missing data produces an explicit unknown result, never an invented
    zero.
11. The feedback network is modeled explicitly: primary-side regulation,
    single regulated rail, weighted/multiple optocouplers, and supported series
    or parallel primary-side optocoupler arrangements. A topology is accepted
    only when the selected controller profile exposes the necessary feedback
    pin model and limits.
12. Controller-specific restrictions, startup/bias behavior, OVP/OCP behavior,
    frequency/mode changes, required auxiliary winding behavior, and unusual
    application-circuit requirements are displayed as prominent design rules.
13. A contextual AI chat remains inside the Flyback Designer. It can cite the
    datasheet and calculation run, explain warnings, prepare alternatives, and
    propose edits. It cannot silently replace accepted inputs or numerical
    results.
14. The complete design can be reopened and reproduced later without the
    original conversation or a particular AI provider.

## 3. Responsibility Boundary

### Deterministic engine owns

- equations, units, rounding, tolerances, corner cases, and pass/fail rules;
- transformer feasibility and candidate ranking;
- loss, ripple, stress, cross-regulation, and thermal scenario calculations;
- validation and engineering warnings;
- reproducible calculation results and regression fixtures.

### AI owns

- full-datasheet extraction into a strict schema;
- page-aware evidence gathering and contradiction detection;
- natural-language explanations and controller-specific reminders;
- preparation of alternative design proposals for user review;
- contextual chat over the PDF, accepted component profile, and calculation
  artifacts.

AI is an assistant around the engine, not an untestable replacement for it.
The same saved design must calculate without AI or network access.

## 4. Local Knowledge Base

All datasheets belong to one user-selected, portable knowledge-base folder,
but they must not be dumped into one flat directory. The target is:

- immutable original PDFs deduplicated by SHA-256;
- human-readable records grouped by manufacturer, part number, document type,
  and revision;
- a rebuildable SQLite/FTS index for fast full-library search;
- Markdown sidecars for summaries, review notes, evidence, and handoff;
- typed JSON for machine-validated engineering profiles and calculation input;
- explicit links between PDF revision, component profile, project, core data,
  prompts, AI responses, and reports.

SQLite is an index and transaction layer, not the only copy of irreplaceable
knowledge. A future reindex operation must be able to rebuild it from the
portable files and sidecars. See `docs/modules/ENGINEERING_KNOWLEDGE_BASE.md`.

## 5. Online Datasheet Search

The main window includes a small collapsible search strip at the bottom. It is
not a second general-purpose browser. It provides:

- a part-number query box and source filters;
- compact results with manufacturer, exact part number, description, document
  revision/date when available, source, and PDF availability;
- **Preview/Open**, **Save to Library**, and **Copy Link** actions;
- visible source and download status;
- a normal-browser fallback when a source cannot be integrated directly.

Search adapters use official APIs, manufacturer catalogues, or explicitly
permitted links. Search, download, validation, and indexing are separate steps.
Saving never marks a document or extracted value as verified.

## 6. Real Magnetic Component Data

A usable magnetic bank joins four different records:

1. **Core geometry:** exact shape/order code, `Ae`, `Aw`, `le`, `Ve`, dimensions,
   mating set, gap options, tolerances, and thermal data when published.
2. **Material:** manufacturer material code, frequency/temperature range,
   saturation information, permeability, and loss curves or coefficients with
   their valid domains.
3. **Bobbin:** exact compatible part, usable winding width/height/area, pins,
   creepage/clearance geometry, and mechanical drawing.
4. **Provenance:** source URL/file hash, document revision, page/table, import
   date, parser version, and review state per field.

The bank is downloaded as versioned source packs and cached locally. Generic
names such as `EE19` are search aliases; calculations use an exact selected
record. Official manufacturer catalogues and design data are preferred. For
example, TDK publishes ferrite catalogues and a magnetic design tool containing
digitized material data and loss coefficients; such data remains source-bound
and is not silently combined with another manufacturer's geometry.

Current official integration references include the
[TDK ferrites product catalogue](https://www.tdk-electronics.tdk.com/en/1190522/products/product-catalog/ferrites-and-accessories)
and [TDK Ferrite Magnetic Design Tool](https://www.tdk-electronics.tdk.com/en/180490/design-support/design-tools/ferrite-magnetic-design-tool).

## 7. Required Analysis Scenarios

Every calculation run contains an explicit scenario matrix instead of one
implicit “full load” point:

- minimum/nominal/maximum rectified bus;
- startup, no-load, light-load, nominal-load, and overload where supported;
- minimum/nominal/maximum ambient or core temperature;
- each output at minimum and maximum load;
- cross-load cases, including one isolated output at full load while another
  is lightly loaded;
- component tolerance corners for current limit, frequency, feedback threshold,
  turns, inductance, ESR, forward voltage, and leakage assumptions.

The report distinguishes calculated, estimated, user-assumed, extracted,
reviewed, and unavailable values.

## 8. Markdown-First Development and AI Protocol

The product must never depend on chat history for requirements or handoff.

- Product behavior is specified in versioned Markdown under `docs/` before
  implementation.
- Every engineering module has a Markdown contract with inputs, outputs,
  equations/references, exclusions, failure states, and acceptance tests.
- AI prompt templates are versioned `.md` files and reference a versioned JSON
  response schema.
- Each consequential AI run can be exported as `request.md`, `response.md`,
  validated structured data, source hashes, provider/model metadata, and user
  acceptance state.
- `docs/CURRENT_STATUS.md` states what is implemented and tested; planned
  behavior is never presented as working.
- A new developer or AI agent must be able to continue from the repository and
  saved knowledge-base artifacts without reading any previous conversation.

Markdown is the canonical human contract. JSON and SQLite remain appropriate
for typed validation, calculations, indexing, and transactions; generated
machine data must link back to its Markdown contract and source evidence.

## 9. Product Acceptance Outcomes

The target product is reached only when a user can:

- open a real controller PDF, extract and review its profile, and begin a
  design without re-entering the controller data;
- add arbitrary output rails and isolation groups;
- choose an exact sourced core/material/bobbin combination;
- receive a reproducible feasibility result and useful nearby alternatives;
- inspect all required losses, ripple, stress, thermal, feedback, and cross-load
  scenarios with traceable assumptions;
- discuss the active datasheet and calculation with AI inside the same tool;
- search online from the bottom strip, preview a PDF, and save it into the local
  library;
- search the entire local collection by part, manufacturer, tag, full text,
  extracted parameter, and project usage;
- reopen the project later with no CLI and no dependency on old chat history.

## 10. Explicit Current Gap

The current native Flyback Designer is version 1 only. It is a preliminary DCM
calculator with illustrative core data, a UI cap of eight outputs, simplified
losses, first-output-only capacitor analysis, and no complete controller-profile,
core-catalog, cross-regulation, or feedback-topology system. The existing online
search is a separate browser dialog and the library uses a JSON manifest rather
than the target searchable engineering knowledge base.

These limitations are retained visibly until replaced and verified phase by
phase.
