# Shape Geometry Foundations for PCB Plug-ins

Use this chapter when a PCB plug-in must reason about pads, holes, mask openings, silkscreen,
component text, outlines, or other geometric obstacles. It documents reusable implementation and
optimization foundations, not a complete placement, routing, or repair strategy. Product-specific
classification, candidate construction, scoring, pass order, conflict recovery, and tuning remain
application design decisions.

Read files 02, 10, 12, 50, and 55 first.

## 1. Normalize semantic and physical identity

Keep XML ownership separate from geometric type. A compact scene record normally needs:

- primitive type: circle, stroked segment/capsule, or polygon;
- semantic class: component bound, copper, hole, mask, silk, text, keepout, or other;
- owning component `Id`, if any;
- physical side: Top, Bottom, or both;
- exact geometry plus an axis-aligned broad-phase bound;
- collision policy data such as a clearance class or hard/soft flag.

Do not overload one integer with both ownership and primitive meaning. Ownership supports policies
that distinguish an object's own geometry from foreign geometry; primitive type selects the exact
intersection predicate. Keep policy outside the primitive math so the same geometry kernel can be
tested independently.

Resolve footprint-local side before inserting a primitive:

| Component side | Footprint `Pad@Side` | Physical copper side |
|---|---|---|
| Top | Top or missing | Top |
| Top | Bottom | Bottom |
| Bottom | Top or missing | Bottom |
| Bottom | Bottom | Top |

Through pads and enabled through holes are physical on both sides. Keep separate Top and Bottom
indices so a surface feature on one side cannot block an unrelated object on the other.

## 2. Preserve native primitive types

Use the cheapest exact representation supported by the XML geometry:

- circle: center and radius;
- stroked line: endpoints and half-width, forming a capsule;
- filled convex polygon: transformed vertices;
- concave polygon: exact record plus decomposition, a proven conservative proxy followed by an
  exact check, or a fail-closed unsupported result.

Do not turn every circle or stroked line into a many-point polygon merely to share one predicate.
That increases construction, indexing, projection, and allocation costs and introduces a new
approximation tolerance. Split genuinely complex shapes into simple native or convex pieces when
the decomposition is exact or conservatively validated.

Pad copper is not only `MainStack`: include enabled terminals. Apply the pad transform, terminal
offset, terminal angle, component placement, and physical-side mapping exactly once. Resolve mask
state and effective swell before creating the physical mask-opening primitive.

## 3. Precompute immutable primitive invariants

Build immutable scene primitives once, then cache the data reused by exact predicates:

- AABB and center;
- transformed vertices and edges;
- normalized separating axes and projection ranges for a convex polygon;
- sine/cosine pairs and local-to-board transforms;
- squared radii and segment direction/length data for circles and capsules.

A four-vertex polygon is not automatically a rectangle. Prove that opposite edges are parallel
before using a rectangle/parallelogram fast path or dropping duplicate separating axes. An
arbitrary convex quadrilateral needs every distinct edge normal; concave geometry needs the
declared exact/conservative handling from section 2.

Keep hot data in compact records or parallel arrays. Avoid reconstructing tuples, lists, XML
lookups, or transformed polygons inside the innermost pair predicate. In Python, `dataclass` records
with `slots=True`, tuples, or numeric arrays reduce allocation and attribute-dictionary overhead;
in Delphi, compact records and contiguous arrays provide the analogous layout.

## 4. Use a broad phase with no false negatives

A uniform sparse grid is effective for local PCB queries when most obstacle bounds cover a small
number of cells. Store object indices in cells and keep the exact primitive in one central array.
Use a generation/stamp array to return an object only once when it spans several queried cells.

Important invariants:

- insertion and query use the same coordinate-to-cell function;
- cell coordinates are clamped to the allocated field in the same way for both operations;
- a remote coordinate outlier is stored in the corresponding boundary cell, not dropped;
- an exact AABB test follows cell retrieval;
- very large primitives use an always-queried list or a proven fallback scan rather than millions
  of cell insertions;
- the cell size is benchmarked against representative object and query sizes; it is not copied
  from the routing grid.

The grid is only a candidate generator. A cell hit is never the final collision answer. Verify
that every indexed query is a superset of a brute-force AABB query, including remote coordinates
and giant query bounds.

## 5. Assign clearance exactly once

Define which object owns each physical clearance. One useful record design stores:

```text
exact primitive geometry
physical_clearance
index_aabb = primitive_aabb inflated by physical_clearance
```

The broad-phase bound includes the clearance, while the exact predicate uses the original circle,
capsule, or polygon plus that clearance. Do not also inflate the moving/query object by the same
configured clearance unless doubled separation is intentional.

When a clearance class is fixed for an entire run, it may be baked into immutable primitives once:
increase circle/capsule radii analytically and offset convex polygons with straight boundaries.
Decompose valid concave polygons before offsetting them. Query the baked representation with zero
additional copy of that clearance and differentially test it against the unbaked reference path.

Keep independent classes when the UI exposes independent rules, for example copper pad/via
clearance and solder-mask/fiducial clearance. A via may require the union of its copper and mask
constraints; for concentric circles this can be represented by the larger effective radius rather
than two double-counted obstacles. Mask geometry already includes resolved common/custom swell;
an additional user clearance is outside that opening. A fiducial exclusion starts at its documented
external keepout diameter.

## 6. Use exact narrow-phase predicates

For a candidate polygon:

- circle: point-in-polygon or minimum center-to-edge distance versus radius plus clearance;
- capsule: endpoint containment or minimum segment-to-polygon-edge distance versus capsule radius
  plus clearance;
- convex polygon: separating-axis or convex clipping;
- general polygon: exact edge intersections plus containment, with a minimum edge distance test
  when a positive outside clearance applies.

Use an inflated AABB only to reject impossible pairs cheaply. Never accept or reject the final
pair from AABB overlap alone unless the product contract explicitly defines rectangular geometry.
Keep an unoptimized reference predicate for every fast path and test tangency, nearly parallel
edges, zero-length segments, and values adjacent to the serialization precision.

## 7. Reuse a neighborhood without making it stale

If many related evaluations share a bounded area, query the global spatial index once for that
complete area and de-duplicate the returned primitive indices once. Transform those primitives to
the evaluation's local frame once rather than reprojecting them for every test.

If that local set is still large and many small cells or poses are evaluated, build a temporary
local grid from primitive AABBs. Each cell then checks only its local bucket plus the local
large-object list. The local grid is useful only when its construction cost is lower than repeated
linear scans; measure both paths and keep a small-list threshold.

Cache only phase-pure results:

- immutable physical geometry may use a cache keyed by query geometry, side, and clearance policy;
- results affected by movable or newly accepted geometry need a scene generation or an exact
  dynamic-obstacle signature in the key;
- insertion, removal, or replacement of a dynamic primitive invalidates every cache that could
  have observed the old scene.

A cache that is geometrically exact but keyed to a stale scene creates false negatives. Treat cache
keys and invalidation as part of the correctness proof, not as a performance detail.

## 8. Reduce dimensionality only when the query permits it

When an object center is constrained to a finite line or curve parameter, it may be cheaper to
convert each nearby obstacle into a forbidden parameter interval than to probe a uniform point
lattice:

```text
candidate_center(t) = origin + t * direction
```

For convex polygons, swept separating axes can produce the collision interval. Circles and
capsules can use analytic rounded-region intersection while remaining native primitives. Append
the intervals, sort once, merge once, and subtract their union from the finite allowed range.

This is a reusable geometric operation only. The SDK does not prescribe which paths to construct,
which free interval to choose, how far an object may move, or how conflicts between movable
objects are resolved. Profile interval construction separately from sorting/merging: for small
local lists, exact primitive projections and roots commonly cost more than the final linear merge.

## 9. Prepare board containment once

Prepare the board outline once. Reconstruct three-point arcs according to the PCB XML convention.
If arcs are flattened, declare a chord-error tolerance and include it conservatively in the
containment predicate.

Do not assume every ordinary `Shape Type="Arc"` contains three distinct non-collinear points.
DipTrace represents a full-circle arc with equal first and last points and the middle point at the
opposite end of the diameter. Importers can also preserve collinear or zero-length stroked arcs;
the core treats a non-closed collinear arc as straight segment(s). Keep board-outline validation
strict, but mirror the core's ordinary-shape fallback or conservatively preserve the stroke cap so
one harmless imported primitive cannot abort the whole board.

For repeated point-in-polygon tests, index outline segments along one axis by the cells crossed by
their coordinate range. Query only the relevant buckets, de-duplicate segment indices, and retain
an unindexed reference predicate for differential tests near vertices, horizontal edges, arc
extrema, and bucket boundaries.

If a product supports an unfinished board with no `BoardOutline`, it may create an analysis-only
working bound from enabled component/geometry extents plus explicit search and full-text margins.
Do not serialize that synthetic rectangle as a real outline. A present but malformed outline should
still fail closed.

## 10. Text uses two different rectangles

The serialized font/layout cell and a calibrated visible-glyph envelope serve different purposes.
Keep both:

- full cell for anchor reconstruction, board containment, and fail-closed fallback;
- calibrated visible envelope only for text classes/font modes proved by fixtures.

Ordinary board or footprint Silk Text is a static same-side text obstacle. Component markings that
are outside the chosen processing scope must also remain static obstacles; do not omit them merely
because the plug-in will not edit them.

See file 12 for the verified DipTrace vector-text contracts and required fallback classes.

## 11. Inspect broadly and edit narrowly

A plug-in may need all components, pattern geometry, board shapes, vias, and the outline for
analysis even when the user selected only a few components. Keep the manifest broad enough to
export those obstacles, then filter editable targets inside the executable by
`Component@Selected="Y"`.

Return only complete changed component records under the proven `Edit` merge contract. Unselected
objects remain unchanged in DipTrace and must remain present in the analysis scene as immutable
obstacles. If the chosen scope contains no editable text, preserve the exchange file byte for byte.

## 12. Determinism, profiling, and language ports

Keep a stable total order for objects, candidates, and tie-breaking. Time-based termination makes
output depend on CPU speed, antivirus state, and packaging extraction; use explicit pass/attempt
limits when a bounded algorithm is required.

Minimum differential tests include:

- every component-side/pad-side combination and Through geometry;
- pad terminals, common/custom mask swell, tented mask, holes, and fiducials;
- native circle/capsule/polygon predicates near tangency;
- configured clearance applied exactly once;
- Top/Bottom independence;
- matrix duplicate suppression, giant objects, and remote boundary cells;
- cached versus uncached results before and after dynamic-scene mutations;
- straight/curved outlines and no-outline policy;
- full-cell versus calibrated visible text bounds;
- whole-board versus selected-component scope, including immutable out-of-scope text;
- source Python versus packaged executable output parity on the same immutable fixture.

Freeze the reference output before porting to another language. Compare ordered decisions, changed
IDs, summary counters, and normalized or byte-identical output as required by the product contract.
Python `float` and Delphi `Double` are both binary64 in the usual x64 builds, but evaluation order,
library functions, tolerances, and formatting can still change threshold decisions. Preserve
operation order and total tie-breaks, and test values on both sides of every geometric tolerance.

The SDK provides the XML and geometry foundations; quality of a placement/search policy still
requires independent algorithm design and board-level acceptance fixtures.
