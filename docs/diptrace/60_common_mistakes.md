# 60 — Common mistakes (and how to avoid them)

The errors an AI most often makes with DipTrace XML. Each is a *wrong → right* pair. If you
remember nothing else from this pack, remember these.

## Geometry vs reference elements

> **Wrong:** `<Points><Item X="1" Y="2"/></Points>`
> **Right:** `<Points><Point X="1" Y="2"/></Points>`

Write `<Point>` for geometry point lists — it's what the canonical serializer emits; `<Item …/>`
is the *reference*-list element (a net's `<Pads>`/`<Pins>`). Nuance so you can read real files:
this split is a naming convention, **not reader‑enforced** — the importer takes coordinates from
any child of a point/segment container, and the footprint pad‑mask `<TopSegments>`/`<BotSegments>`
lists are themselves written as `<Item X1 Y1 X2 Y2>`. Emit `<Point>`, accept either.

## Angle units

> **Wrong:** `Angle="90"` (degrees)
> **Right:** `Angle="1.5708"` — **radians, CCW.**

## The `Layer` attribute is a name; `Lay` is a number

> **Wrong:** `Layer="0"`
> **Right:** `Layer="Top Silk"` (text enum) **plus** `LayId="0"` when a copper/non‑signal layer
> is meant. `Layer` is the string; `LayId` is the integer that points at a `<CopperLayers>`/`<Lay>` `Id`.

This applies to the string `Layer` attribute (Shape, Dimension, Table). By contrast, a trace
point's `Lay` and a CopperPour's `Lay` **are numeric** copper‑layer `Id`s — that's correct, don't
"fix" them into strings. And spell layer names as single literal tokens (`Top Courtyard`,
`Bottom Courtyard` — never a combined `Top/Bottom Courtyard`).

## `Enabled="N"` means *delete on import*, not *hidden*

> **Wrong:** to remove an object, delete its XML node.
> **Right:** set `Enabled="N"` and **leave the node in the file** — the importer removes it.
> Absent `Enabled` = enabled. (Wires have no `Enabled`; drop them from the `<Wires>` list instead.)

## Don't invent or renumber Ids

> **Wrong:** assign your own `Id` to a new object, or renumber Ids while editing.
> **Right:** **new** objects → omit `Id` (the app assigns) + `Selected="Y"`; **edited** objects →
> **keep the existing `Id`** (other objects reference it). Change an Id and every reference to it breaks.

Explicit exceptions: a new `Group` needs an internally consistent assigned `Id`; the verified
same-exchange PCB new-net recipe assigns a free net `Id` only after `Net=All` exposes the
complete net namespace and `Comp=All` exposes the pads that must reference it. Never generalize
either exception to an incomplete `Partial` subset.

## Decimal separator is always a dot

> **Wrong:** `X="1,27"` (locale comma)
> **Right:** `X="1.27"` — a dot, regardless of the machine's regional settings.

## References must point at Ids that exist

> **Wrong:** `NetId="99"` when there is no net `Id="99"`.
> **Right:** reference only Ids present in the file. Use each dialect file's **Cross‑reference**
> table (`LayId → CopperLayers`, `NetId → Nets`, `ViaStyle → ViaStyles`, `Group → Groups`, …).

## Connectivity is *declared*, not *drawn* (PCB)

> **Wrong:** route a trace so it visually touches a pad and expect them connected.
> **Right:** give the trace a paired **endpoint** — `Connected1="Pad" Object1="<Component Id>"
> SubObject1="<Pad Id>"` (and `Connected2/Object2/SubObject2/Point2` for the other end; the pad
> `Id` goes in `SubObjectN`, there is no `Pad=` attribute on a trace). A pad's net comes from the
> pad's own **`NetId`** (the authoritative carrier — the net's `<Pads>` list is just a derived
> mirror), not from geometry.

A pad's net membership is its **`NetId`** — read straight from each `<Pad>`, preserved on import,
with ratlines built automatically (a pad keeps its net even unrouted). Set the pad's `NetId` to move
it between nets; don't rely on `<Pads>` alone. Traces connect via **declared endpoints**, not visual touching,
and **connecting pads from different nets merges those nets** (easy to do by accident). See
[`10_pcb_xml_reference.md`](10_pcb_xml_reference.md) → *How DipTrace resolves connectivity on import*.

## Including `<Traces>`/`<Wires>` replaces the whole list

> **Wrong:** append one `<Trace>` under an existing `<Net>` and expect it *added* to the routing.
> **Right:** these nested lists have no per‑member `Id` — when present they **replace** the net's
> entire list. Re‑list all current traces/wires plus your new one, or omit the container entirely
> to leave routing untouched.

## `Selected` is not always an attribute of the parent object

> **Wrong:** expect `<Net Selected="Y">`, or assume every `Selected` filter uses the same
> top-level flag.
> **Right:** simple objects use their own `Selected="Y"`, but aggregate selection is derived
> from child geometry. In both PCB and Schematic, a `TNet` is selected when any `TNet.line` is
> selected (`<Trace>` in PCB, `<Wire>` in Schematic). A Schematic bus is selected when any
> `TBus.line` is selected; a Schematic differential pair is selected when either member net
> contains a selected wire.

That rule selects the **parent object**, not every child line. Once the parent qualifies, the
exporter includes its whole trace/wire list. For custom per-line or per-segment processing,
inspect `Trace@Selected` / `Wire@Selected` and PCB `Point@Selected` individually. PCB
`Net=Selected` tests the trace flag, not the point flag directly.

Extra Schematic trap: `Net=Selected` / `Bus=Selected` combined with `ImpMode=Edit` imports only
the incoming wires marked `Selected="Y"` when rebuilding the nested `<Wires>` list. That can
discard unselected wires. If selection is only the plug-in's processing scope, export `Net=All`
or `Bus=All`, test child `Wire@Selected` yourself, return only changed parents, and omit
`<Wires>` when geometry is not being changed.

## Coordinate scaling / Y sign is internal — don't "fix" it

The file's numbers are already in board units with the app's own scaling; don't rescale or flip Y
to "correct" them. Read and write them as‑is.

## Don't apply one transform to every component-related object

> **Wrong:** independently apply `Side`, `Flip`, and `HorzFlip` to the embedded footprint and
> then apply the same mirror to component marking coordinates.
>
> **Right:** the exported `PatternStyle` already contains user flip variants. Mirror its local
> X once only for `Side="Bottom"`, then rotate/translate. Marking `X/Y/Angle` uses the separate
> `Settings/Markings/CompRotate` law and is never mirrored by those flags. Pad `MaskPaste`
> `Top*`/`Bot*` states are pad-local near/far faces: resolve the pad's own physical side from the
> component side and footprint-local `Pad@Side`, then select the matching face.

See file 02 §4.1–4.3. A single generic transform helper is a design error here.

## Don't return a sparse PCB component

> **Wrong:** return only `<Component Id="17"><RefDesMarking>...</RefDesMarking></Component>`.
>
> **Right:** return a complete clone of the exported component, change only the intended
> marking leaf, preserve `/Source/Library`, and omit all unchanged components from the returned
> `<Components>` list.

`PatternStyle` loading resets instance fields, bottom-side geometry is applied after reading,
and component child containers have special rebuild rules. Sparse records can silently alter
pads, flags, markings, or side geometry.

## A nested `Id` does not guarantee nested merge

> **Wrong:** return one `<Pad Id="...">` and expect it to merge into a PCB component's pad list.
>
> **Right:** `<Component><Pads>` and `<AddFields>` are rebuilt when present. For component edits,
> preserve the complete exported containers.

## Two serialized corners are not a rotated rectangle bound

> **Wrong:** transform only the two points of a footprint rectangle/obround and take their AABB.
>
> **Right:** reconstruct all four local corners, transform all four, then bound them. Include
> half the effective stroke width for open outlines.

## A board-outline arc is not a chord

> **Wrong:** treat every outline point as a polygon vertex and connect it to the next by a line.
>
> **Right:** `Point@Arc="Y"` is the middle/control point of a circular arc from the previous
> point to the next, and it consumes that next point. Reconstruct/tessellate the true sweep or
> fail closed.

## Ordinary shape arcs can encode circles or importer fallbacks

> **Wrong:** reject every `Shape Type="Arc"` whose three points are not distinct and
> non-collinear.
>
> **Right:** keep the board-outline rule above strict, but recognize the ordinary-shape dialect:
> equal first/last points encode a full circle, while imported collinear or zero-length stroked
> arcs follow the DipTrace core's segment/stroke-cap fallback. Validate finite coordinates and
> preserve a conservative obstacle instead of aborting an otherwise usable board.

## `TextWidth`/`TextHeight` are not generic marking metrics

> **Wrong:** copy extents from another shape because its `TextShow` or placeholder text matches.
>
> **Right:** reuse them only for the same resolved text and full font tuple. Generated component
> markings have no serialized computed rectangle; use matching font metrics or a conservative
> envelope. `FontSizeFloat` and positive `FontWidth` are internal font scalars, not project-unit
> lengths.

## `TextWidth`/`TextHeight` are not tight visible-glyph bounds

> **Wrong:** treat the orange/layout text rectangle as exact ink, then move every pair whose cells
> overlap.
>
> **Right:** keep the full cell for anchors, pads/mask/body checks, broad phase, and board
> containment. A calibrated visible envelope may be used only for its validated font/string/angle
> class. For ordinary orthogonal uppercase/digit vector RefDes, verified padding is perpendicular
> to the baseline; do not trim the leading/trailing ends. See
> [`12_pcb_text_geometry.md`](12_pcb_text_geometry.md).

## One generic text-shrink factor is unsafe

> **Wrong:** shrink width and height by the same percentage for every vector/TrueType, multiline,
> Unicode, and rotated string.
>
> **Right:** gate calibration by exact eligibility and keep full bounds otherwise. Text/text
> parallel, text/text perpendicular, and text/via acceptance can require different cross-axis
> envelopes. Store them as named policy profiles rather than a universal helper.

## Picture and QR do not use Text extents

> **Wrong:** read `TextWidth`/`TextHeight` for every angled, aligned board object.
>
> **Right:** ordinary Text uses those attributes. Picture and QR (`Type="10"`) use
> `PictureWidth`/`PictureHeight`, normally with exactly one anchor point.

## Bound footprint text is not a generated component marking

> **Wrong:** move `<RefDesMarking>/<Silk>` and assume every visible RefDes moves.
>
> **Right:** first detect a regular footprint `<Shape Type="Text" TextShow="RefDes">`. It
> suppresses the generated marking on that layer and is shared through `PatternStyle`; a
> component marking edit does not relocate it per instance.

## `Any Text` is not a wildcard

> **Wrong:** let `TextShow="Any Text"` suppress or borrow metrics from RefDes, Pattern, or a user
> field.
>
> **Right:** `Any Text` is decorative literal text. Pattern is serialized as `"7"` and user field
> index `n` as `"20+n"`. Cache metrics by the resolved text and complete font/context key.

## Polygon terminal points are real geometry

> **Wrong:** bound every terminal from `Width`/`Height` and ignore `<Points>`.
>
> **Right:** for `Shape="Polygon"`, use terminal-local `<Points>`, then apply terminal angle,
> pad offset/angle, component placement, and include the result with the main stack.

## `By Paste` is not ordinary solder-mask swell

> **Wrong:** create a mask opening by swelling the copper pad when `TopMask/BotMask="By Paste"`.
>
> **Right:** resolve the corresponding paste state, custom shrink, and segmented apertures.
> `By Paste` delegates mask geometry to paste geometry. If that dependency is unavailable,
> fail closed.

## Known empty and unknown shape types are different

> **Wrong:** skip every unrecognized `Type`, or bound it by whatever points happen to be present.
>
> **Right:** `None` and legacy `-1` are defined no-geometry states. A different unknown future
> token may have curved, sized, or generated geometry not represented by a point AABB; fail closed
> for obstacle/clearance work.

## An uneditable component is still physical

> **Wrong:** skip a component immediately because it has no usable `Id`.
>
> **Right:** it may not be returnable as an `Edit` record, but its pads, holes, mask/paste,
> footprint silk, Picture/QR, and existing markings still block placement. Extract obstacles
> before deciding whether its own marking can be changed.

## Standard component fields are not all `<AddFields>`

> **Wrong:** search only `<AddFields>` for `Pattern`, `Manufacturer`, or `Datasheet`.
>
> **Right:** read `RefDes`/`Name`/`Value` from direct `<Component>` children; resolve
> `Pattern`/`Manufacturer`/`Datasheet` from the embedded pattern selected by
> `Component@PatternStyle`; keep user-defined component `<AddFields>` separate. Preserve all
> of them when returning a complete component.

## Self-consistent geometry tests can prove the same bug twice

> **Wrong:** compute both implementation output and expected output with the same transform,
> arc, or mask helper.
>
> **Right:** use hand-derived fixtures and real exported XML, including top/bottom, flip,
> horizontal flip, component rotation, polygon terminals, arcs, and `By Paste`. Confirm that
> the fixture actually modifies the intended component/object before accepting the test.

## A visible no-op can still freeze an automatic marking

> **Wrong:** always write an accepted marking as `Align="Position"` even when its board pose did
> not change.
>
> **Right:** changing `Auto`/`Common` to `Position` is a semantic product change. Preserve the
> alignment and leave the component out of the result for a true geometric no-op unless freezing
> is explicitly requested.

## Raw local `Common` is not the effective marking alignment

> **Wrong:** treat every local `Align="Common"` marking as Auto, or preserve only a literal local
> `Position` marking.
>
> **Right:** resolve the corresponding global alignment first. Local `Common` plus global
> `Position` uses its stored user pose; local `Common` plus global `Auto` enters the Auto state
> machine. Use effective alignment for geometry and preservation, but retain the original local
> attribute on a true no-op.

## Auto marking fields are not independent

> **Wrong:** resolve only non-empty visible strings and place each Auto field independently.
>
> **Right:** reproduce the host's non-Auto pass followed by Auto pass and its fixed field order. A
> shown empty field still advances the sequence; hidden or author-suppressed fields do not. Test a
> later Auto field after each of those three cases.

## `Pattern Width/Height` is not exact `CompRotate=N` Auto geometry

> **Wrong:** rotate the unrotated pattern bounding rectangle and use that AABB as DipTrace's
> `contw/conth`.
>
> **Right:** the host constructs angle-aware, origin-seeded component bounds from its component
> geometry, fiducial policy, non-text shapes/arcs, and enabled holes. Reconstruct equivalent bounds
> from the exchange when exact render parity is required; otherwise document the conservative
> drift and keep it out of exact-position assertions.

## Reviewed source is not the installed executable

> **Wrong:** assume that a successful package command, timestamp, or old EXE proves delivery.
>
> **Right:** rebuild deliberately, run source and packaged EXE on independent copies of one input,
> compare normalized XML/decisions/counters, record the hash/version, then verify the installed
> artifact hash and exact `settings.xml@ExeFile`.

For a Windows-subsystem/`--noconsole` EXE, use `Start-Process -Wait -PassThru` (or an equivalent
process API) before reading `ExitCode` and comparing output. A direct PowerShell launch can return
before the GUI process finishes, leaving `$LASTEXITCODE` empty or stale.

## A retry can leave its old obstacle alive

> **Wrong:** de-duplicate new dynamic insertions and assume a moved/retried object cannot leave a
> phantom at its original position.
>
> **Right:** remove/deactivate the exact previous handle before retry, insert exactly one accepted
> current pose, and restore exactly one obstacle on failure. Rebuild the scene independently in a
> regression test and compare active identities and collisions.

## Deferred geometry must not depend on an optional pass

> **Wrong:** let the final recount see pads/holes/masks only because an optional recovery stage
> happened to activate them earlier.
>
> **Right:** every stage explicitly activates its required physical classes. Activation is
> idempotent, and disabling unrelated stages must not change final-validator obstacle completeness.

## Success is not final before the atomic replace

> **Wrong:** close the last progress/result window or write a success log while the result is still
> pending in memory.
>
> **Right:** keep the run visibly pending, atomically replace the exchange file, then publish final
> success and close. On commit failure, preserve the computed diagnostics with the traceback and
> leave the original exchange untouched.

## A spatial grid can explode on one giant AABB

> **Wrong:** insert every long line, large arc, cutout, or board-wide box into every fine-grid cell
> it overlaps.
>
> **Right:** estimate cell count first; put oversized boxes in a separate always-queried list.
> Also preflight query cell count: a giant query must fall back to an exact all-obstacle scan or a
> proven higher-level index rather than enumerate millions of cells. Differentially verify both
> ordinary and giant queries against brute force. False positives cost time; false negatives
> corrupt results.

## A capped matrix must not drop coordinate outliers

> **Wrong:** cap the normal matrix envelope, reject any obstacle outside it, or scan one global
> outlier list on every ordinary query.
>
> **Right:** use the same clamped `geti/getj` mapping for insertion and query. Remote geometry and
> a remote query meet in a boundary cell; exact AABB filtering removes unrelated false positives.
> Keep a separate always-queried list only for primitives whose own AABB exceeds the per-object
> cell budget.

## Four points do not prove a parallelogram

> **Wrong:** for every four-vertex custom pad polygon, test only the first two SAT axes because
> opposite rectangle edges are assumed parallel.
>
> **Right:** prove the quadrilateral is a parallelogram before removing duplicate axes. An
> arbitrary convex four-point pad needs axes from all four edges; a concave or unproven polygon
> needs exact decomposition or a conservative fallback.

## A cache key must describe the scene it observed

> **Wrong:** cache a collision/coverage result only by candidate position and reuse it after a
> movable text or other dynamic obstacle was inserted, removed, rotated, or replaced.
>
> **Right:** separate immutable physical geometry from dynamic geometry. Include a scene generation
> or exact dynamic-obstacle signature in every dependent key, and invalidate affected caches on
> every scene mutation. Differentially compare cached and uncached results before and after changes.

## A second spatial index is not automatically faster

> **Wrong:** build a temporary matrix/tree for every query even when the neighborhood contains only
> a few primitives, or compare every local cell against the complete local shape list.
>
> **Right:** query and de-duplicate the complete bounded neighborhood once. Use a measured small-list
> linear path; only bucket primitives into a reusable local grid when repeated pair-test savings
> exceed construction and query overhead.

## Do not tessellate native circles just to build tunnel intervals

> **Wrong:** turn every circle and stroked line into a many-point polygon, then repeatedly project
> those proxy vertices for every text.
>
> **Right:** keep circles as center/radius and stroked lines as endpoint/radius capsules. Compute
> the moving-text collision interval analytically. Query the matrix once for the complete tunnel,
> pass the deduplicated figures once, append intervals, then sort and merge once per edge.

## Do not optimize interval merging before measuring interval construction

> **Wrong:** add a tree or incremental ordered insertion because interval processing looks
> expensive from the algorithm diagram.
>
> **Right:** time analytic circle/capsule roots, polygon projections, interval construction, sort,
> and merge separately. With small local lists, a plain append, one sort, and one linear merge is
> commonly cheaper than maintaining another index.

## A mathematically free micro-interval may not survive XML rounding

> **Wrong:** choose a free-interval endpoint that rounds back onto a forbidden boundary.
>
> **Right:** reserve an inward serialization nudge derived from output precision. If the interval
> is too narrow to hold both nudges, do not classify it as a serializable free interval. Test mm,
> inch, and mil separately.

## Removing an XML parent does not release live descendants

> **Wrong:** call `remove(<Nets>)` and assume memory is freed while lists/closures still reference
> trace nodes.
>
> **Right:** only after the last proven use, extract compact data, detach and clear the
> analysis-only subtree, and drop all descendant references. Never remove resolver infrastructure
> required by returned records, such as PCB `/Source/Library` for component `PatternStyle`.

## Clearance inflated twice is twice the requested clearance

> **Wrong:** inflate every stored obstacle by `c` and every candidate/query by another `c` without
> defining that policy.
>
> **Right:** assign clearance to stored geometry, query geometry, or an explicit split and test the
> final separation. Double inflation is acceptable only when `2c` is intentional.

## A soft overlap penalty is not a final invariant

> **Wrong:** assume a large text-overlap cost guarantees an overlap-free result.
>
> **Right:** another larger term (via avoidance, owner distance, movement, or orientation) can
> still make an overlap the cheapest weighted solution. Validate the final selected geometry,
> repair conflicts against every same-side label, and abort without writing if the declared
> no-conflict invariant remains unsatisfied.

## When you *generate a whole file* (not a plug‑in edit): keep arrays dense and in Id order

> **Wrong:** write top‑level objects (nets, components, shapes, …) out of order or with gaps in Ids.
> **Right:** each top‑level array must be **dense, ascending from Id 0, position == Id**.
> On a full‑file open the reader binds references **positionally**, so gaps/reordering silently
> re‑bind references to the wrong object. (This does **not** apply to the normal plug‑in exchange
> flow, where you keep the existing structure and the importer is Id‑keyed — it only bites when you
> author a whole board file from scratch.)

## Parse defensively

> **Wrong:** assume every attribute the PDF lists is present, or that no other attributes exist.
> **Right:** treat missing attributes as defaults; **preserve** attributes/elements you don't
> recognize instead of dropping them (newer builds add fields the PDF doesn't document — e.g.
> `Enabled`, the `FontSizeFloat`/`FontMono` font family, `ShieldGroup`).

---

## Deleting a pad without fixing its internal connections (CompEdit)

> **Wrong:** remove or renumber a footprint pad and leave an `<IntCon X Y/>` referencing its old `Id`.
> **Right:** first remove or update every `<IntCon>` whose `X`/`Y` referenced that pad's `Id`.

Internal‑connection `X`/`Y` are **pad `Id` references**; an unresolved one indexes **past the pad
array → a delayed access‑violation crash**. Every `X`/`Y` must reference a pad that still exists
after the edit. See [`30_compedit_xml_reference.md`](30_compedit_xml_reference.md) → *InternalConnections*.

## Never do

- **Never change `Version`** of the document.
- **Never change `Units`** / the coordinate scaling.
- **Never rewrite or rename elements/attributes you don't understand** — pass them through.
- **Never delete unknown attributes or child elements** — you'll strip data the app needs.
- **Never reorder objects** unless the task requires it (see the dense/in‑order note above).
- **Never delete an XML node to remove an object** — use `Enabled="N"`.
- **Never create a new exchange file** — overwrite the exact `plugin_exchange.xml` path you were
  given as `argv[1]`.
- **Never ship a complex geometry/merge plug-in after only an author pass.** Run the independent
  skeptic workflow in [`70_complex_plugin_review.md`](70_complex_plugin_review.md).
