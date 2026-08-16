# Independent Review for Complex Plug-ins

A complex plug-in must receive an independent skeptic pass after the author tests it. This is a
release gate for geometry, transforms, connectivity, generated markings, style/default resolution,
large-tree processing, and edits that replace or rebuild XML containers.

The skeptic is not asked to “review generally.” Give it the contract, source, `settings.xml`,
fixtures, tests, build instructions, and distributable executable, then divide the review into
two explicit attacks.

## 1. Protocol, lifecycle, and merge skeptic

Use this prompt:

```text
Act as a hostile release reviewer for a DipTrace plug-in. Assume the algorithm's happy path
looks plausible and try to prove the integration unsafe.

Check:
- settings.xml program type, export scopes, ExpMode/ImpMode, and required input families;
- argv[1] handling, exact-path replacement, no-op behavior, atomic write, and cleanup;
- malformed/unsupported input behavior and whether the original remains untouched;
- Edit merge granularity: complete changed records, subtree replacement, omitted objects;
- unknown attributes/children preservation and accidental Version/Units/Id changes;
- process exit on every path, hidden/chained dialogs, log fallback, and Program Files writes;
- source versus freshly rebuilt distributable EXE parity and stale deployment risk;
- final-success UI/log ordering versus the actual atomic exchange-file commit;
- effective marking alignment (local `Common` through global settings), Auto field sequencing,
  and `CompRotate=Y/N` against independently derived host-render positions;
- dynamic obstacle identity across retries and explicit activation of every stage prerequisite;
- tests that mutate or assert the wrong fixture object;
- whether tests prove real host behavior or only a self-consistent model.

Report each finding with a fixture or code path, severity, consequence, and smallest safe fix.
Separate static evidence from DipTrace GUI/runtime evidence that still must be obtained.
```

Minimum evidence:

- original-file hash before and after abort/no-op;
- normalized XML diff and changed top-level IDs for success;
- source/EXE parity on identical fixture copies, with an explicit wait for GUI/`--noconsole` EXEs;
- one real DipTrace smoke test on a disposable project;
- one forced log-path failure showing `%TEMP%` fallback;
- one launched UI run proving that the user can close the plug-in and return to DipTrace.

## 2. Geometry, correctness, and performance skeptic

Use this prompt:

```text
Act as a hostile geometry and performance reviewer. Build adversarial fixtures rather than
restating the implementation.

Check:
- units, radians, coordinate signs, top/bottom physical-side mapping, flips, inverse transforms;
- line width, four-corner rectangles, polygon terminals, three-point arcs, cutouts;
- pad/via/mask/paste defaults and overrides, mounting holes, QR/Picture/Text extents;
- generated markings versus shared bound PatternStyle text and exact TextShow tokens;
- full font-cell versus visible-glyph geometry, anchor-before-trim order, calibration eligibility,
  baseline ends, and full-cell fallback classes;
- missing IDs/references, None/not-present states versus unknown enums, zero/malformed extents;
- existing, accepted, failed/unmoved, and uneditable objects remaining collision obstacles;
- deterministic candidate order, nearest-owner policy, allowed rotations, side/font preservation;
- final visual-conflict validation, consistent propagation of every user option, deterministic
  repair limits, and the declared no-write/partial-result policy when conflicts remain;
- spatial-index false negatives, giant AABBs, allocation churn, repeated XML walks/transforms;
- cached primitive invariants that assume an unproved rectangle/parallelogram;
- cache keys/invalidation after movable geometry is inserted, removed, rotated, or replaced;
- local-index construction cost versus repeated linear scans of the same neighborhood;
- XML retention/deep copies, source/EXE timing, cold/warm start, and peak memory;
- whether every claimed exact optimization is differentially equivalent to a simple reference.

Use hand-derived and real exported fixtures. Do not calculate expected values with the same
helpers as the implementation. Report correctness and performance findings separately.
```

Minimum adversarial matrix:

| Dimension | Required cases |
|---|---|
| Placement | top, top `Flip=Y`, top `HorzFlip=Y`, ordinary bottom, rotated bottom, `CompRotate=Y/N`, local `Common` resolving to global `Position`/`Auto` |
| Geometry | long line, rotated rectangle, polygon, arc crossing a cardinal extremum, cutout |
| Pads | built-in/custom style, polygon terminal, common/custom mask, segmented paste, `By Paste` |
| Text | generated RefDes/Name, bound footprint text, user field, shown-empty/hidden/suppressed Auto sequence cases, every non-center anchor, parallel/perpendicular threshold cases, baseline-end collision, TrueType/multiline/lowercase/Unicode fallback, 0/90/180/270/free angle |
| Other obstacles | routed/static via, mounting hole, existing silk, Picture, QR |
| Failure | missing style/ref/Id, unknown enum, malformed point count, invalid number, no free spot |
| Scale | tiny brute-force fixture, randomized fixtures, giant obstacle AABB, giant query AABB, real large board |

Randomized tests that reuse production point-in-polygon, intersection, or transform helpers prove
only equivalence between two call paths, not geometric truth. Anchor them with hand-computed edge
cases or an independent library/reference oracle.

## 3. Findings that must become permanent tests

The following failures were found while developing and independently reviewing a silkscreen text
auto-placer. They are general release lessons, not private implementation history.

### Launch, packaging, and user feedback

- **The deployed EXE can be stale while reviewed source is correct.** A successful source test or
  matching timestamp is insufficient. Rebuild deliberately and run source/EXE parity on copies of
  the same XML.
- **A GUI/`--noconsole` EXE was checked without waiting for its process.** Direct shell launch can
  return early and leave an empty/stale exit code. Wait for the process handle, then compare output
  and artifact hashes.
- **Sequential modal dialogs can look like a frozen host.** A dialog may be behind DipTrace; after
  acknowledging it, another appears, and the user cannot return to the board until the plug-in
  process exits. Use one window or a diagnostic log, never a post-run chain.
- **A traceback in the install directory can disappear.** `Program Files` is commonly unwritable.
  Try `%LOCALAPPDATA%`, catch directory and write failures, then try `%TEMP%`.
- **Writing the exchange file in place can leave a parseable partial result.** Build and validate
  in memory, write a sibling temporary file, and atomically replace only on success.
- **Success was shown/logged before a deferred commit.** Keep the state pending until atomic
  replacement succeeds; preserve the computed result diagnostics if commit fails.

### XML and merge behavior

- **A visually unchanged marking can still be modified.** Writing `Align="Position"` freezes an
  `Auto`/`Common` marking even when position and angle did not change. Treat mode changes as
  semantic edits and leave a true no-op untouched.
- **Local `Align="Common"` was classified without the global setting.** Effective Position was
  rewritten as if automatic, destroying user coordinates. Resolve effective alignment for
  geometry/preservation while retaining the original local attribute on a no-op.
- **A sparse child fragment can erase siblings.** Some present containers are rebuilt during
  `Edit`; return a complete exported top-level record and preserve its full child containers.
- **Analysis scope and result scope were confused.** A plug-in may need all components, nets, and
  styles to decide safely, but should normally return only complete changed records.
- **ElementTree preservation was mistaken for byte preservation.** Retained unknown nodes survive
  semantically, but serialization formatting may change. Abort/no-op paths must avoid writing.

### Text mechanisms and extents

- **Generated component markings and footprint text were conflated.** A bound
  `PatternStyle` text shape is shared and may suppress the generated silk marking; changing
  `<RefDesMarking>/<Silk>` does not move the shared shape per instance.
- **`TextShow="Any Text"` was treated as a wildcard.** It is decorative literal text.
  Pattern is serialized as `"7"` and user field index `n` as `"20+n"`.
- **Metrics were cached by placeholder instead of displayed text and font.** Cache by resolved
  text and the complete font tuple. Otherwise different fields/components reuse wrong extents.
- **QR/Picture were read through Text dimensions.** Board Text uses
  `TextWidth`/`TextHeight`; Picture and QR use `PictureWidth`/`PictureHeight`, with one anchor plus
  angle/alignment.
- **Missing, zero, or malformed extents became empty obstacles.** Resolve a proven conservative
  bound or abort; do not silently ignore them.
- **The layout/font cell was treated as tight visible ink.** DipTrace's displayed text rectangle
  has cross-axis padding, so already readable labels were moved unnecessarily and could lose their
  component association. Preserve the full cell, but use a separately calibrated visual predicate
  for eligible text/text or soft-via decisions.
- **A generic shrink trimmed the baseline ends.** RefDes strokes nearly fill the cell along the
  reading direction. Keep the complete baseline length; apply only the validated cross-axis
  allowance, and keep full bounds for uncalibrated text.
- **Visible trimming happened before anchor reconstruction.** For non-center alignment this moves
  the reconstructed center. Compute the center from the full cell first, then derive any visual
  envelope around that center.
- **A RefDes calibration leaked into unsafe strings.** TrueType, multiline, lowercase,
  punctuation/markup, Unicode, non-orthogonal, and missing/substituted-font cases must use the full
  cell unless their own profile was validated.
- **Shown empty fields were dropped from Auto sequencing.** DipTrace advances its marking sequence
  for a shown, non-suppressed empty field; hidden and author-suppressed fields do not advance it.
  An independent later-field fixture must distinguish all three cases.

The complete cell/visible geometry contract is in
[`12_pcb_text_geometry.md`](12_pcb_text_geometry.md).

### Geometry and transforms

- **Pad mask and paste faces were treated as absolute board sides.** Footprint-local layers require
  the component side transform, while `MaskPaste` `Top*`/`Bot*` values are the pad's own/opposite
  faces. Resolve the pad's own physical side from component side plus footprint-local `Pad@Side`.
- **PatternStyle geometry and marking coordinates used the same transform.** They follow different
  laws. Use the footprint transform for pads/shapes/holes and `CompRotate` for marking coordinates.
- **`CompRotate=N` Auto bounds came from a rotated `Pattern Width/Height` AABB.** DipTrace uses its
  angle-aware, origin-seeded `contw/conth`; the shortcut drifts for asymmetric, offset, or
  non-orthogonal footprints. Test against a host-derived pose, not the same resolver under review.
- **Only two corners of rotated rectangles were transformed.** Reconstruct and transform all four
  corners before bounding.
- **Three-point arcs were reduced to endpoint chords.** Include the real sweep and cardinal
  extrema; for outline containment, tessellate conservatively or fail closed.
- **Unknown shapes were bounded only by their serialized points.** That is not proven conservative
  for an unknown type. Distinguish known absence (`None`, `-1`, disabled) from an unknown token;
  skip the former when specified and fail closed for the latter.
- **`By Paste` was handled as ordinary mask swell.** It delegates to resolved paste geometry,
  including custom shrink and segments. Fail closed if that dependency is unavailable.

### Obstacle completeness

- **Mounting holes, existing silk, and failed/unmoved markings were omitted.** All remain physical
  obstacles. Insert an accepted marking immediately; if placement fails, insert its current box.
- **A component without an editable `Id` was skipped before extracting obstacles.** It may be
  impossible to return as an edit, but its physical pads/shapes/holes still block placement.
- **A test changed the first matching pad, not the intended bottom component.** Every mutation
  helper must assert the target's component/object identity and the intended precondition.

### Placement optimization and final validation

- **Soft overlap cost was mistaken for a guarantee.** A higher via, movement, orientation, or
  owner-distance term can still leave text/text overlap in the lowest-energy selection. Run a
  final visual-conflict validator.
- **A local conflict change disturbed already valid labels.** Sequential re-optimization can make
  results order-dependent. Keep stable objects locked unless a documented multi-object decision is
  being evaluated.
- **Repair cleared only the triggering pair.** The new position could collide with a third label
  and oscillate. Validate every accepted change against the complete current same-side scene.
- **A successful stabilization retry left the original immutable text obstacle active.** Every
  logical dynamic object needs a removable identity and exactly one current-pose obstacle after
  fail/succeed/move transitions.
- **A final recount depended on an optional earlier pass to activate physical geometry.** Each
  validator/diagnostic stage must explicitly and idempotently activate its required obstacle
  classes.
- **A later pass forgot a user option.** A candidate can be legal in one phase and illegal in
  another if via, clearance, scope, or body-placement policy is not carried through all phases.
- **An original self-hit was subtracted using mismatched boxes.** Comparing a visual candidate
  against the original full cell can subtract a neighboring label's hit. Subtract only the exact
  label's original visual box.
- **A stable sort key was not total.** Duplicate fields/components with the same semantic label
  retained XML collection order. Add center, angle, dimensions, and a stable serialization
  discriminator, then test reversed input order.
- **Unresolved conflicts were still serialized.** If the declared final invariant remains false,
  apply the documented abort/unchanged/safe-partial policy before XML update; do not return the
  optimizer's last state merely because its budget expired.
- **Missing BoardOutline was treated as malformed input.** In-progress PCBs may contain components
  before a board edge is drawn. Distinguish absence from malformed geometry and, when the product
  permits it, use a non-serialized virtual rectangle derived from enabled component bounds plus
  full-cell text/search margins.

### Performance and memory

- **The XML tree was searched repeatedly inside candidate loops.** Parse and resolve styles once,
  then use compact records and cached transforms.
- **Curved outlines were rebuilt for every candidate.** Prepare points, edges, bounds, cutouts,
  and conservative arc approximations once.
- **A fine grid expanded a board-wide or diagonal AABB into huge cell counts.** Put giant boxes in
  a separate always-queried list; tune the threshold from measurements.
- **A new de-duplication set was allocated per query.** A generation/stamp array avoids hot-loop
  allocation while preserving deterministic order.
- **A four-point fast path assumed every quadrilateral was a rectangle.** Cache fewer SAT axes only
  after proving opposite-edge parallelism; otherwise use every distinct convex edge normal or the
  declared concave fallback.
- **A correct cached collision result was reused after the scene changed.** Separate immutable
  physical geometry from dynamic text/movable geometry. Include a generation or exact dynamic
  signature in dependent keys and invalidate after insert/remove/replace.
- **Every small local evaluation scanned the complete neighborhood.** Query and transform the
  complete bounded neighborhood once; where measured worthwhile, bucket it in a temporary local
  grid. Retain a linear path for small lists because building a second index is not free.
- **Outline containment ran before cheap collision rejection.** Query/collide first, then run the
  expensive true-outline predicate.
- **Removing a subtree did not release memory.** Detached descendants remained referenced by
  local lists and XML nodes. Extract compact data, remove/clear the subtree, and drop all local
  references.
- **Deep-copying all unchanged XML dominated memory and serialization.** Keep complete XML only
  for records that may be returned; emit narrow output.
- **Repair recomputed all conflicts after each single move and repeated the full search.** This can
  appear to hang on a realistic dense board. Reuse local data, batch independent work where the
  product algorithm permits it, and bound passes deterministically. Verify both ends of the
  policy: a small conflict set must retain the full established retry depth, while a
  conflict-saturated board receives a bounded shared attempt budget with a documented minimum per
  conflicted object.
- **The interval list was optimized before it was profiled.** On small local lists, sorting and
  merging can be negligible compared with repeated primitive conversion, SAT projections, and
  analytic roots. Measure interval construction separately from merge time.
- **A packaged Python EXE was described as native compiled code.** PyInstaller bundles CPython,
  bytecode, and native dependencies; ordinary Python loops remain interpreted. Compare source,
  packaged Python, and any native port stage by stage on identical fixtures.

The optimization method and equivalence requirements are in
[`55_heavy_geometry_optimization.md`](55_heavy_geometry_optimization.md).

## 4. Triage and closure

Classify findings:

- **BLOCKER:** can corrupt/import the wrong data, hang the host, cross sides/layers, use unproven
  geometry, or ship an executable different from reviewed code.
- **HIGH:** can miss a common obstacle/state, produce non-nearest/non-deterministic results, or
  make realistic boards unusably slow or memory-heavy.
- **MEDIUM:** diagnostics, packaging, compatibility, or fixture gaps that make failures difficult
  to reproduce.
- **LOW:** maintainability or documentation improvements with no demonstrated result risk.

A finding is closed only by:

1. a code or contract change;
2. a regression fixture that failed before the change;
3. source tests;
4. rebuilt-EXE parity when executable behavior is affected;
5. a DipTrace GUI check when the claim concerns launch, merge, visibility, z-order, or imported
   board behavior.

Static inspection must never be reported as a successful GUI/runtime test. Conversely, one GUI
success does not replace fixture, abort, equivalence, or stale-artifact checks.

## 5. Release-evidence boundary

The failures above came from real plug-in development and independent review, including large PCB
fixtures and adversarial side, text, geometry, packaging, and failure-path cases. Keep reusable
lessons in this SDK. Keep a commercial algorithm's candidate construction, scoring, pass sequence,
coefficients, fixture timings, and board-specific outcomes in its private release record. Public
skeptic reports should state evidence, not proprietary implementation.
