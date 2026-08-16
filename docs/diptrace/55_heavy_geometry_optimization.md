# Heavy Geometry: Exactness, Performance, and Memory

Use this chapter for placement, collision, clearance, outline, copper, mask, routing, or other
plug-ins that evaluate many geometric candidates. It does not replace the geometry contracts in
[`02_diptrace_xml_conventions.md`](02_diptrace_xml_conventions.md) and the program-specific
reference.

The governing rule is:

> First make a small reference implementation correct and deterministic. Then optimize while
> proving the same decisions in the same order.

## 1. Separate exact optimizations from product heuristics

The following changes can preserve exact behavior when implemented correctly:

- parsing XML once and resolving each style/reference once;
- precomputing transforms, sine/cosine pairs, primitive bounds, outline edges, and cutouts;
- precomputing immutable primitive invariants such as convex axes/projections and capsule data;
- using a spatial index whose query returns every possible collider;
- reusing a complete local neighborhood and indexing it only when measurements justify the cost;
- caching text metrics by the complete semantic key;
- caching phase-pure geometry results with complete scene-version/signature keys;
- checking cheap necessary conditions before expensive exact predicates;
- replacing allocation-heavy query sets with generation/stamp arrays;
- storing hot geometry in compact records instead of XML nodes or dictionaries;
- detaching analysis-only XML subtrees after compact data has been extracted;
- emitting only complete changed top-level records.

The following can change results and must be explicit product decisions:

- limiting the number/radius of placement candidates;
- coarsening candidate coordinates or rotations;
- rasterizing/vectorizing at a larger tolerance;
- using only bounding boxes as the final collision test;
- dropping narrow cutouts or small obstacles;
- returning the first result from a non-deterministic index;
- parallel evaluation that changes tie ordering.

Label the second group as heuristics, document the trade-off, and add acceptance fixtures. Never
hide a changed search space under the word “optimization”.

## 2. Build a staged pipeline

A scalable geometry plug-in normally has these stages:

```text
XML parse and validation
  -> style/reference maps
  -> compact physical geometry
  -> broad-phase spatial index
  -> deterministic candidate generation
  -> exact collision and containment
  -> edit plan
  -> narrow XML result and atomic replace
```

Instrument each stage separately. Total runtime alone cannot distinguish packager start-up, XML
parsing, geometry construction, candidate search, or serialization.

## 3. Parse and resolve once

Build maps such as `PatternStyle name -> record`, `PadStyle name -> record`, component `Id ->
record`, and via-style position -> record once. Resolve common/default values once, with the same
fail-closed rules as the unoptimized implementation.

For every placed instance, cache:

- component placement and inverse placement transforms;
- footprint-side transform and physical-layer mapping;
- sine/cosine for every reused angle;
- the chosen pattern and pad styles;
- compact pad, mask, paste, hole, silk, and text primitives.

Do not walk the full XML tree for each marking or candidate.

For immutable convex primitives, also cache AABBs, edge normals, and projection ranges. A
four-vertex polygon may use a rectangle/parallelogram fast path only after opposite-edge
parallelism is proved; otherwise retain every distinct separating axis. Cache circle/capsule
radii and segment data in their native forms rather than rebuilding polygon proxies.

## 4. Prepare outlines and curves once

Decode the outer outline and every enabled board cutout once. Validate point counts and reconstruct
three-point arcs before the search starts.

If curves are tessellated, choose and document a geometric tolerance. The approximation must be
conservative for the predicate being used. Include the possible approximation error in required
clearance/inside margins; merely drawing a visually smooth polyline is not a containment proof.
Cache:

- flattened points;
- edges with their AABBs;
- region bounds;
- any acceleration structure used by point-in-region or segment-distance tests.

For critical cases, retain an exact arc predicate or fail closed when a conservative bound cannot
be established. Do not flatten the same arc for every candidate.

## 5. Use broad phase without losing colliders

A uniform grid is effective when most obstacle AABBs cover a modest number of cells. A single
long diagonal, large arc, board cutout, or outline-wide box can otherwise be inserted into an
enormous number of cells and consume most time and memory.

Use a two-tier index:

1. ordinary obstacles go into every overlapped cell;
2. obstacles whose AABB would cover more than a configured cell budget go into a separate
   `large` list;
3. every ordinary query examines its grid cells **and** the complete `large` list;
4. estimate a query's cell count **before** enumerating cells; if it exceeds a query budget, use
   an exact AABB scan of all obstacles (ordinary plus `large`) or a proven higher-level index.

The cell size, insertion threshold, and query budget are workload parameters, not SDK constants.
Derive them from representative obstacle/query sizes and benchmark several values. Assert in tests
that ordinary and giant-query paths are supersets of the brute-force AABB query.

Bound the matrix dimensions. For a fixed cell size, map insertion and query through the same
clamped `geti/getj` indices so coordinate outliers land in boundary cells instead of allocating an
enormous field or disappearing. Keep the exact AABB check after retrieval. For a variable cell
size, the alternative used by `TInteractiveMatrix` is to increase the cell size until the normal
field fits the axis-cell budget. Differentially test remote queries in every direction and at
corners.

Avoid allocating a new `set` for every query. A stamp array is deterministic and allocation-light:

```python
stamp += 1
for index in candidate_indices:
    if seen[index] == stamp:
        continue
    seen[index] = stamp
    yield obstacles[index]
```

Handle stamp overflow by clearing the array and restarting the generation. Preserve stable
insertion/index order if it affects first-fit placement.

## 6. Order tests by cost

For each candidate:

1. reject invalid numbers, side, or orientation;
2. use the spatial index to find possible obstacle intersections;
3. run exact collision tests on that small set;
4. only then perform the more expensive curved-outline and cutout containment checks;
5. accept and insert the new geometry into the same physical-side index.

This order is safe when every early rejection is a necessary condition and the broad phase has no
false negatives. Measure rejection counts per stage; the best order depends on the real workload.

Keep independent indices for physical top and physical bottom when the rules are side-specific.
Do not confuse footprint-local layer names with pad-local `MaskPaste` near/far faces. Resolve the
pad's own physical side before choosing its `Top*` or `Bot*` state; see file 02, section 4.3.

### 6.1 Index point-in-polygon edges along one axis

Flatten an outline once, then index every segment by the Y cells crossed by its endpoint range,
with a small tolerance at cell boundaries. A horizontal-ray `inpoly(point)` reads only the point's
Y cell. A box/segment near-edge test reads only the cells crossed by its Y range and de-duplicates
edge indices.

This preserves even/odd intersection logic without scanning every tessellated arc segment for every
candidate. Keep the unindexed reference predicate and differential-test indexed versus reference
results around vertices, horizontal edges, arc extrema, and cell boundaries.

### 6.2 Prefer forbidden intervals to a point lattice

When a candidate center moves along a finite line, do not uniformly probe that line. Query nearby
geometry once, calculate the exact one-dimensional collision interval contributed by each
primitive, append intervals to the affected track, sort once, merge once, and subtract the union.

Keep primitive types:

- convex polygons use swept separating-axis intervals;
- circles remain center/radius and use analytic line-versus-rounded-rectangle roots;
- stroked lines remain endpoint/radius capsules;
- concave geometry is decomposed, conservatively proxied plus exact-checked, or rejected.

If one obstacle class has a fixed clearance for the entire run, consider baking that clearance
into its compact primitives once instead of adding it inside every narrow-phase predicate. Increase
circle/capsule radii analytically; offset convex polygons with straight boundaries; decompose a
valid concave polygon into convex pieces before offsetting it. Keep a conservative fail-closed
fallback for malformed geometry. This optimization is valid only when the stored expanded shape
is then queried with zero additional copy of the same clearance; differential-test it against the
reference predicates before removing the old path.

For a small per-edge interval count, a final list sort and linear merge is normally cheaper than
another matrix/tree. Measure it separately before adding an interval index. Reusable primitive,
clearance, and physical-side rules are in
[`56_shape_geometry_foundations.md`](56_shape_geometry_foundations.md).

### 6.3 Reuse complete local neighborhoods safely

When many related evaluations share a known bounded region, query the global index once for that
whole region, de-duplicate once, and transform the returned primitives into the local evaluation
frame once. If many small poses still scan a large local list, a temporary local grid keyed by
primitive AABBs can reduce pair tests. Keep a small-list linear path: building and querying another
index can cost more than scanning ten nearby primitives.

Separate immutable physical geometry from dynamic accepted/movable geometry. A cached result that
depends on the latter must include a scene generation or exact dynamic-obstacle signature and must
be invalidated after insertion, removal, or replacement. Do not reuse a physically correct result
from a stale scene. Differential-test cached and uncached paths before and after scene mutation.

Give every dynamic obstacle a stable identity or removable handle. In a retry/stabilization pass,
deactivate the object's old/original obstacle before evaluating its new pose, then insert exactly
one obstacle for the accepted pose—or restore exactly one current/original obstacle when placement
fails. Merely de-duplicating active insertions does not remove a stale obstacle left at the previous
pose. Make insert/deactivate/replace idempotent and assert that one logical object contributes at
most one active dynamic obstacle per physical side.

Likewise, activate deferred physical classes explicitly at the stage that requires them. A final
validator or diagnostic recount must not see pads, holes, masks, or other physical geometry only
because an optional earlier recovery pass happened to activate them. Stage prerequisites belong in
the stage entry contract, and activating an already active class must be a no-op.

## 7. Cache text metrics with a complete key

Text bounds depend on more than a `TextShow` placeholder. A cache key must include at least:

- resolved displayed text, including line breaks;
- the owning pattern/component context when field resolution depends on it;
- `TextShow`;
- vector/TrueType mode, font name, mono mode;
- size, width, scale, line spacing, and any effective common stroke;
- the measurement method/version.

Board Text uses `TextWidth`/`TextHeight`; Picture and QR use
`PictureWidth`/`PictureHeight`. Do not share cache entries between these object types. A missing,
zero, malformed, or context-mismatched extent is not a cheap empty obstacle; resolve it
conservatively or fail closed.

## 8. Keep full-cell and visible text geometry separate

The layout/font cell and a calibrated visible-glyph envelope answer different questions. Store
both; do not recompute or mutate one into the other inside candidate loops.

- Use the full placed-cell AABB as a no-false-negative text broad phase.
- Use the full cell for hard pad/mask/body predicates and board containment.
- Invoke the calibrated visual predicate only after both text classes and angles pass its
  eligibility gate.
- Keep the complete baseline length when the calibration found padding only across the baseline.
- Fall back to the full cell for TrueType, multiline, lowercase, punctuation/markup, Unicode,
  non-orthogonal angles, or missing/substituted font context.

Conflict repair is a product algorithm, not an XML rule. Keep it bounded, deterministic, and
explicitly tested. Avoid a state machine that moves one object, recomputes every conflict, and
regenerates the full search after every change; that shape becomes deceptively quadratic on dense
boards. A repair candidate must be validated against the complete current same-side scene, not
only the pair that triggered it, and the algorithm must stop on a documented pass/attempt limit or
a repeated state.

Do not give every conflicted object the full retry limit unconditionally. After the initial
deterministic pass, count the objects that actually need repair and distribute a deterministic
board-level attempt budget over that set. Sparse conflicts should retain the established per-object
hard limit; conflict-saturated input should still guarantee a small minimum number of attempts per
object while preventing long blocker chains from multiplying that limit across most of the board.
Cap the workload used to derive the board-level budget at the largest representative release
fixture, and keep an independent absolute per-object cap. This is a performance policy, so freeze
the sparse-conflict output and measure quality deltas on dense fixtures before changing it.

Use attempt/pass counts rather than elapsed-time cutoffs. Wall-clock deadlines make output depend
on CPU speed, antivirus state, and one-file extraction time. File 12 defines text geometry and
validation predicates; it deliberately does not prescribe a commercial placement policy.

## 9. Control XML memory

Large exchanges can have analysis-only trees, especially nets and traces, that are needed while
building obstacles but must not be returned in a narrow `Edit` result.

After extracting compact records:

1. prove that omitting the analysis-only family preserves live data in the chosen import mode,
   then remove that top-level subtree from the output tree;
2. clear the detached subtree if no later phase needs it;
3. drop every local variable, list, closure, or index that still references its descendants.

With ElementTree, removing a parent from the document does not free descendants while Python
references still point to them. Avoid deep-copying the whole document or every unchanged
component. Keep complete XML only for records that may be returned; keep geometry in compact
records, preferably `dataclass(slots=True)`, tuples, or arrays.

Never remove resolver infrastructure that changed records need. In particular, PCB component
`PatternStyle` references require the preserved `/Source/Library` described in file 01.

Write only after all edits are planned. Narrow output reduces both serialization time and the
amount of data DipTrace must merge.

## 10. Prove equivalence

Before optimizing, freeze:

- deterministic candidate order and tie-breaking;
- accepted/rejected decision sequence;
- changed top-level IDs;
- normalized output XML;
- summary counters.

Then compare the reference and optimized implementations on:

- every hand-derived transform/geometry fixture;
- randomized small boards checked against brute force;
- giant-AABB obstacles;
- arcs and cutouts;
- both physical sides;
- no-placement and malformed cases;
- the real large fixture.

Also run repeated-pass lifecycle fixtures: fail then succeed, succeed then move, and fail again.
After each transition, compare the active obstacle identities and collision result with a scene
rebuilt from scratch. Disable optional recovery stages one at a time and require final validation
and diagnostics to observe the same mandatory physical obstacle classes.

For text geometry, include threshold-adjacent parallel/perpendicular overlaps, full-cell fallback
classes, and the declared final invariant. A weighted energy comparison is not enough. For a
whole-run-abort policy, require zero unresolved conflicts or byte-identical input. For the safe
partial policy, merge the narrow result back into a copy of the full input and prove that no
changed marking participates in any final text conflict; all remaining conflicts must be
original-pose/original-pose pairs.

For any product-specific search, freeze the declared search domain, candidate order, total
tie-breaking key, allowed approximation, and no-result policy. A spatial index can validate tested
candidates but does not prove that an untested legal candidate does not exist.

For a prepared outline predicate, a useful differential property is:

```text
prepared_contains(shape, margin) == reference_contains(shape, margin)
```

over randomized shapes near straight edges, arc extrema, vertices, holes, and cutout boundaries.
For a spatial index:

```text
set(index.query(aabb)) is a superset of set(bruteforce_aabb_query(aabb))
```

False positives cost time; false negatives corrupt results.

Also test clearance exactly once. If stored obstacles are already inflated by clearance `c` and
the query/candidate is independently inflated by `c`, the resulting separation is `2c`. That may
be a deliberate conservative policy, but it must not happen accidentally: define whether
inflation belongs to stored geometry, query geometry, or both, and test the resulting distance.

## 11. Measure the distributable artifact

Measure the reviewed source and the exact packaged executable on copies of the same XML:

- cold start and warm start;
- parse/validate, index construction, search, result build, serialization, total;
- candidates generated and tested;
- broad-phase candidates and exact tests;
- accepted, rotated, unchanged, skipped, unsupported;
- peak private working set or another documented memory measure;
- normalized output and decision parity.

One-file executable extraction and antivirus scanning can dominate a cold run even when the
algorithm is fast. Report it separately rather than “optimizing” geometry to hide packaging cost.

PyInstaller packages a CPython interpreter, bytecode, and native dependencies; it does not turn
ordinary Python geometry loops into native machine code. Native-library calls may already be fast,
but Python loop dispatch, boxed numbers, attribute access, and temporary-object allocation remain.
Therefore measure a Delphi/C#/native port as a separate implementation on the same fixtures; do
not apply a universal language multiplier. Keep the Python version as a behavioral oracle when that
is the product workflow.

## 12. Treat measurements as local evidence

Do not publish one development board's grid size, arc tolerance, candidate budget, or stage timing
as an SDK constant. Record them with the fixture, hardware, interpreter/architecture, build mode,
via/mask policy, and exact artifact hash. Re-measure on several real designs and keep the reference
output frozen while tuning.

Profile at least matrix retrieval, local-index construction/query, exact primitive predicates,
interval construction, interval sort/merge when used, outline containment, XML parse/write, and
packaged-process startup separately. Do not assume interval insertion or merging is the bottleneck:
analytic roots, separating-axis projections, or repeated primitive conversion may dominate. A
tempting secondary index may cost more than a linear scan when each local list contains only a few
entries; only measured call counts and time can decide. Preserve the equivalence gates above
whenever a tuning change alters storage, cache keys, query order, or candidate generation.

## 13. Release gate for heavy geometry

Do not ship until all are true:

- unsupported geometry fails closed and preserves the original file;
- broad-phase queries have no false negatives against brute force;
- optimized and reference decisions match on randomized and golden fixtures;
- physical-side transform fixtures are independently derived;
- existing and failed/unmoved objects remain obstacles;
- every moved/retried object has exactly one active current-pose obstacle and no stale original;
- final validation/diagnostics activate mandatory physical classes directly, independent of
  optional earlier passes;
- full-cell hard geometry and calibrated visible-text geometry are not conflated;
- the final result has zero conflicts under its declared visual predicate, or every remaining
  conflict is proven original-pose/original-pose and no changed object participates;
- no visual no-op silently changes an alignment/mode attribute;
- source and packaged executable produce equivalent output;
- cold/warm time and peak memory are reported for the release fixture;
- an independent skeptic has reviewed geometry, lifecycle, merge shape, and stale-artifact risk.

Use the skeptic prompts in [`70_complex_plugin_review.md`](70_complex_plugin_review.md).
