# DipTrace Plugin & XML — AI Context Pack

This folder is a **public, source-independent context pack for an AI coding assistant** that is
helping write a DipTrace plug-in or read/generate DipTrace XML. The user/model does not need
access to DipTrace implementation source.

Drop the whole folder into or next to the plug-in project. It explains:

- how a DipTrace plug-in is discovered, launched, and exchanges data with the host;
- the four DipTrace XML dialects and their shared coordinate/reference laws;
- merge-safe operations, production packaging, calibrated PCB text geometry, heavy-geometry
  optimization, typed shape-geometry foundations, and release review.

DipTrace consists of **PCB Layout**, **Schematic Capture**, **Component Editor (CompEdit)**, and
**Pattern Editor (PattEdit)**. Each has its own XML dialect, and one plug-in manifest belongs to
exactly one program.

## Files

| File | Read it when… |
|---|---|
| [`01_plugin_architecture.md`](01_plugin_architecture.md) | Writing a plug-in: folder/manifest, lifecycle, exchange contract, merge laws, language skeletons. **Start here for plug-ins.** |
| [`02_diptrace_xml_conventions.md`](02_diptrace_xml_conventions.md) | Working with any DipTrace XML: units, coordinates, angles, IDs/references, transforms, fonts. **Start here for XML.** |
| [`05_production_plugin_workflow.md`](05_production_plugin_workflow.md) | Turning a request into a reproducible release: contract sheet, real exchange fixtures, builds, source/EXE parity, deployment, smoke test. |
| [`10_pcb_xml_reference.md`](10_pcb_xml_reference.md) | **PCB Layout** (`<Source Type="DipTrace-PCB">` … `<Board>`). |
| [`12_pcb_text_geometry.md`](12_pcb_text_geometry.md) | PCB text metric cells versus visible glyphs, calibrated collision profiles, orientation/ownership rules, and final conflict repair. |
| [`20_schematic_xml_reference.md`](20_schematic_xml_reference.md) | **Schematic** (`<Source Type="DipTrace-Schematic">` … `<Schematic>`). |
| [`30_compedit_xml_reference.md`](30_compedit_xml_reference.md) | **Component Editor** library (`<Library Type="DipTrace-ComponentLibrary">`). |
| [`40_pattedit_xml_reference.md`](40_pattedit_xml_reference.md) | **Pattern Editor** library (`<Library Type="DipTrace-PatternLibrary">`). |
| [`50_common_operations.md`](50_common_operations.md) | Merge-safe cookbook for add/delete/modify/replace/create-net/link and silkscreen placement. |
| [`55_heavy_geometry_optimization.md`](55_heavy_geometry_optimization.md) | Exact-result performance/memory guidance for placement, collision, outlines, masks, routing, and other heavy geometry. |
| [`56_shape_geometry_foundations.md`](56_shape_geometry_foundations.md) | Reusable typed shape geometry, physical sides, clearances, spatial/local indexing, exact predicates, and cache-invalidation rules. |
| [`60_common_mistakes.md`](60_common_mistakes.md) | Wrong→right errors and the **Never do** list. Skim before generating XML. |
| [`70_complex_plugin_review.md`](70_complex_plugin_review.md) | Mandatory skeptic protocol, adversarial matrix, and reusable lessons from a real geometry plug-in. |
| [`templates/`](templates/) | Complete per-program manifests, production-safe Python starter/build script, and real-exchange capture helper. |

## Quick start for an external model

1. Read files 01, 02, and 05.
2. Fill the contract sheet in file 05 before choosing export/import scopes.
3. Copy the matching complete manifest from `templates/`; do not omit settings children.
4. Capture a real plug-in exchange and keep its original immutable.
5. Read the matching dialect file plus files 50 and 60. For PCB text measurement or placement,
   also read files 12 and 56.
6. For complex geometry, also read 55 and run both skeptic attacks in 70.
7. Ship source, reproducible build, the exact tested executable, tests/fixtures, log instructions,
   and evidence from a disposable-project DipTrace smoke test.

When the pack does not define a required field or runtime behavior, do not guess. Consult the
matching official PDF/real exchange, or declare the case unsupported and leave the exchange file
untouched.

## SDK boundary

This pack documents DipTrace contracts and reusable engineering foundations. It intentionally does
not provide a complete commercial placement/router/optimizer: package classification, candidate
construction, scoring coefficients, pass sequence, rip-up/recovery policy, and product tuning must
be designed and validated by the plug-in author. File 56 is sufficient to build correct typed
shape geometry, no-false-negative global/local neighbor indices, and safe geometry caches without
exposing one product's algorithm.

## Source of truth

The official specifications ship in the DipTrace `Docs` folder, normally
`C:\Program Files\DipTrace\Docs`:

- `DipTrace_Plugins.pdf` — plug-in mechanism and `settings.xml`;
- `DipTraceXML_Pcb_En.pdf`, `DipTraceXML_Schematic_En.pdf`,
  `DipTraceXML_CompEdit_En.pdf`, and `DipTraceXML_PattEdit_En.pdf` — exhaustive field catalogs.

This pack is self-contained for the contracts and operations it explicitly covers, but it does
not reproduce every specification table. The PDFs alone are also insufficient for complex
plug-ins: merge behavior, exchange-time styles, generated markings, effective mask/paste geometry,
and some default-resolution rules are runtime contracts. Those independently verified contracts
are documented here so a public author does not need product source. If an attribute/enum is absent
from the pack, consult the PDF; if a geometry/merge rule is absent, fail closed until verified.

Working sample source also ships under `…\DipTrace\Plugins\`:

- `Plugins\Pcb\DashDotLine\SourceCodeC#`;
- `Plugins\Pcb\OpenMaskForSelectedTraceSegments\SourceCodeDelphi`.

Treat them as protocol demonstrations, not production templates. File 01 documents the blocking
`Console.ReadLine()` and locale-parse traps; the templates in this pack add no-op, atomic-save,
logging, packaging, and stale-executable protections.

## Verification and compatibility

**Pack version: 2026.08.06-r7; contract date: 2026-08-06.** Statements beyond the PDFs—import merge
semantics, `Enabled`, connectivity, generated markings, footprint/marking/mask transforms, outline
arcs, pad/terminal, mask/paste, via, and component-`Edit` behavior—were checked against matching
DipTrace product implementation during SDK preparation. Schematic narrow net-name editing and the
complex silkscreen workflow were also exercised through compiled plug-in artifacts. Its calibrated
font-cell/visible-ink profile is in file 12; reusable release evidence and limits are in file 70.

The r7 review adds source-verified effective marking alignment, exact Auto field sequencing,
`CompRotate=N` bounds limitations, dynamic-obstacle retry lifecycle, explicit deferred-geometry
activation, commit/UI ordering, and reliable waiting for Windows-subsystem executables. These are
general integration and geometry contracts; the commercial placement algorithm and its tuning
remain outside the public pack.

This is not a guarantee for every older or future DipTrace build. Preserve unknown data, capture
an exchange from the target version, run source/EXE parity, and finish with a live smoke test on a
project copy. Static or fixture verification must not be reported as successful GUI import.

The format carries its own root `Version` (for example `4.3.0.x` for PCB/Schematic projects and
`5.x` for libraries). Validate root `Type`, `Version`, and `Units` against tested fixtures. A newer
unknown version is not permission to drop or reinterpret fields; preserve them and fail closed for
behavior the plug-in cannot establish.
