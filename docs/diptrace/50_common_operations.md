# 50 — Common operations (cookbook)

Ready‑made recipes for the most frequent plug‑in tasks. Every recipe operates on the
**exchange XML** you were handed as `argv[1]` and writes the result back to the **same file**
(see [`01_plugin_architecture.md`](01_plugin_architecture.md) for the lifecycle,
[`02_diptrace_xml_conventions.md`](02_diptrace_xml_conventions.md) for units/references, and the
dialect file [`10`](10_pcb_xml_reference.md)/[`20`](20_schematic_xml_reference.md)/[`30`](30_compedit_xml_reference.md)/[`40`](40_pattedit_xml_reference.md) for element details).

## Object hierarchy (PCB) — orientation map

```
Board
├── Settings            (units, grid, layer stack — do NOT change units)
├── CopperLayers → Lay  (Id here is what LayId/every layer ref points to)
├── Nets → Net
│   ├── Pads → Item(Comp,Pad)      reference list (component Id + pad Id)
│   └── Traces → Trace → Points → Point   geometry (per‑segment attrs on 2nd point)
├── Components → Component
│   ├── Pads → Pad(Id, NetId, InternalConnection)
│   └── RefDes / Name / Value / …Marking
├── CopperPours → CopperPour → Points → Point
├── Shapes → Shape → Points → Point       free graphics & text
├── Dimensions → Dimension                (can attach to a Component / Net / Shape / CopperPour)
├── DifferentialPairs → DifferentialPair
├── Groups → Group                         (objects reference a group by its Id)
└── Tables / DesignErrors / …
```

Schematic mirrors this with `Sheets`, `Parts`, `Nets → Wires → Points`, `Buses`, `Shapes`.
The general shape: **containers are plural (`<Nets>`), members are singular (`<Net>`);
geometry point lists are `<Points><Point/></Points>`; reference lists are `<…><Item/></…>`**
(by convention — readers are name‑agnostic about the child tag, and the footprint pad‑mask
segment lists use `<Item>`; still, write `<Point>` for geometry).

---

## Delete an object

**Rule:** mark it `Enabled="N"` and **leave the node in the file**. Do **not** remove the XML
node — the importer deletes objects it reads with `Enabled="N"`, and dropping the node instead
just leaves the original untouched.

```xml
<Shape Id="7" Enabled="N" … />          <!-- was Enabled absent/Y; now removed on import -->
```

Wires (Schematic) have no `Enabled` flag — remove a wire by dropping it from its net's
`<Wires>` list; remove the whole net with `Enabled="N"` on the `<Net>`.

## Add a new object

**Rule:** append a new element to the right container, set `Selected="Y"`, and normally
**don't invent an Id** — the app assigns it. Explicit exceptions are a new `Group` and the
complete-namespace PCB net recipe below. To make several added objects one
selectable/grouped unit, give them a shared `Group`.

```xml
<Shapes>
  … existing shapes …
  <Shape Type="Polygon" Layer="Top Silk" Selected="Y">
    <Points><Point X="10.0" Y="5.0"/><Point X="12.0" Y="5.0"/><Point X="12.0" Y="7.0"/></Points>
  </Shape>
</Shapes>
```

## Modify an existing object

**Rule:** **keep its existing `Id`**, change the attributes/children you need, set `Selected="Y"`.
Never renumber Ids of objects you edit — other objects reference them.

```xml
<Shape Id="7" Type="Polygon" … Selected="Y"> … </Shape>   <!-- Polyline → Polygon, same Id -->
```

## Replace an object (change something Id‑stable can't express)

**Rule:** `Enabled="N"` the original **and** append the replacement(s) as new objects
(`Selected="Y"`, optionally a shared `Group`). This is exactly what the shipped `DashDotLine`
example does — one polyline → many dash segments.

```xml
<Shape Id="7" Enabled="N" … />                              <!-- kill original -->
<Shape Type="Line" Selected="Y" Group="42"> … </Shape>      <!-- append replacements -->
<Shape Type="Line" Selected="Y" Group="42"> … </Shape>
```

## Create or delete a group

A `<Group>` (in `<Groups>`) ties objects together; each member sets `Group="<group Id>"`.
It is one of the two documented assigned-`Id` cases; the other is the complete-namespace PCB
new-net recipe below:

- **Create:** append `<Group Id="n" Selected="Y"/>` to `<Groups>` (create `<Groups>` if the file
  has none), where `n` = max existing `<Group>` `Id` + 1 over the **complete** list; then set
  `Group="n"` on each member. (On plug‑in/edit import DipTrace re‑maps your group `Id`, so it only
  has to be internally consistent — every member must use the same number.)
- **Delete:** set `Enabled="N"` on the `<Group>`. Its members are **not** deleted — they are
  automatically **ungrouped** (their `Group` becomes `-1`) on import.
- **Empty group:** a group with no members persists in the file; remove it with `Enabled="N"`.

## Create a net / attach pads (PCB)

**A net's `<Pads>` list alone moves nothing** — membership is carried by each pad's own
`NetId`, and DipTrace rebuilds the `<Pads>` mirror itself. A `<Net>` whose only content is a
`<Pads>` list imports as an *empty* net. The working recipe needs the pads in the exchange:

**Rule:** manifest with `Net=All` (so the whole net list is visible) **and** `Comp=All` (so the
pads are editable). Then: (1) pick a genuinely free net `Id` = max `Id` over the **complete**
`<Nets>` list + 1; (2) append the `<Net>` with that `Id`; (3) set `NetId="<that Id>"` on each
member `<Pad>` of the components. Ratlines are then generated automatically.

```xml
<Net Id="57" Selected="Y">          <!-- 57 = max existing net Id + 1, list was complete -->
  <Name>MY_NET</Name>
</Net>
…
<Component Id="1" …> <Pads> <Pad Id="3" NetId="57" …>…</Pad> … </Pads> </Component>
<Component Id="4" …> <Pads> <Pad Id="1" NetId="57" …>…</Pad> … </Pads> </Component>
```

(The max‑Id computation is safe **only** because `Net=All` put the complete list in the file —
never compute it over a `Partial` subset. This is the one non‑Group case where you assign an
Id yourself, because the pads must reference the net in the same exchange.)

## Link one object to another (references)

**Rule:** most references are **by Id** (`NetId`, `LayId`, `Group`, dimension attach), but a few
bind **by position** in an in‑order list (`ViaStyle` → `<ViaStyles>`, `NetClass` →
`<NetClasses>`) — those elements do carry an `Id`, but it just equals their index and is not used
for lookup, so **never reorder those lists**. `<Item …/>` = a
reference list (net pads/pins); a bare attribute value = a single reference. See the
**Cross‑reference** table at the end of each dialect file for the full "X → points to Y" map.
Point references at targets that exist in the file; don't fabricate them.

## Place PCB component markings around their own component

This is the reference workflow for a geometry-heavy silkscreen placer. It deliberately
separates broad analysis input from narrow `Edit` output.

1. Use `ExpMode=Partial`, `ImpMode=Edit`, with `Comp=All`, `Net=All`, `Shape=All`,
   `Board=All`; set unrelated families to `None`. `Comp=All` is required both for placed
   components and for the embedded `PatternStyle`/`PadStyle` library.
2. Parse root `Units`, project marking/font defaults, common layer line widths,
   solder-mask/paste defaults, via styles, the board outline, and board cutouts. Build a
   physical-top and physical-bottom obstacle index. A placed-component PCB may have no
   `<BoardOutline>` yet. If the product does not edit the board edge, use a documented virtual
   rectangle around enabled non-via component bounds, inflated by the largest visible full-cell
   text extent, maximum owner-search gap, board margin, and an explicit allowance. Do not serialize
   that analysis rectangle as a real outline. A present but malformed outline still fails closed.
3. Add obstacles from every object family in the product contract: free mask/cutout shapes,
   routed/static vias when selected, and every placed
   component's pad copper/terminal/mask geometry. Include footprint mounting holes (use the
   larger of `Diam` and `HoleDiam` on both sides) and every mask/silkscreen shape inside the
   component's referenced `PatternStyle`, transformed to board coordinates and mapped to the
   physical side. Add static silkscreen graphics only if the placement contract requires
   silk-versus-silk avoidance. A component without an editable `Id` still contributes all
   required obstacles;
   defer the “can return an edit” check until after obstacle extraction. Include board
   Picture/QR bounds using `PictureWidth`/`PictureHeight`; ordinary Text alone uses
   `TextWidth`/`TextHeight`. Use:
   - file 02 §4.1 for footprint geometry;
   - file 02 §4.3 for physical layer mapping and pad-local near/far `MaskPaste` faces;
   - file 40 for polygon terminals, custom swell/shrink, segmented paste, and `By Paste`;
   - file 10 for true arcs, four-corner boxes, line-width inflation (including a conservative
     fallback when a mask/cutout width is not serialized), outline, and cutouts.
   Known shape states `None` and legacy `-1` contribute no geometry. An unknown shape token is not
   equivalent to empty, and a box over its serialized points is not proven conservative: fail
   closed until the type is defined.
4. Classify text before moving it. A generated component marking is controlled by
   `<...Marking>/<Silk>`; a regular bound footprint `Shape Type="Text" TextShow="...">` is
   shared through `PatternStyle` and cannot be relocated per instance by changing that leaf.
   A matching author-owned Top Silk shape suppresses the generated marking and remains a
   physical silkscreen obstacle. Match serialization tokens exactly: Pattern is `"7"`, user
   field index `n` is `"20+n"`, and `"Any Text"` is decorative rather than a wildcard.
5. Resolve visibility and **effective alignment** (`Show=Common` and `Align=Common` through project
   globals), actual displayed text, the full font tuple, and `CompRotate`. Effective `Position`
   uses the stored anchor even when it came from local `Common`; effective `Auto` requires the
   ordered state machine in file 02 §4.2. Do not remove shown-empty fields from that sequence, and
   do not rotate one `Pattern Width/Height` box as a substitute for exact `CompRotate=N`
   `contw/conth` when host-render parity is required. Compute the **full layout/font cell** in board
   space. Serialized
   `TextWidth`/`TextHeight` are reusable only for the exact matching shape/text/font; generated
   markings need matching font measurement or a proven conservative envelope. Keep any calibrated
   visible-glyph box as separate geometry: use the full cell for anchor reconstruction and
   board-outline containment. Decide explicitly whether pad/mask/body collision uses the full
   manufacturing cell or a calibrated visible-stroke envelope. Use a visible profile only for
   the exact text/font/angle class it validated; do not call a screenshot-derived profile exact.
   [`12_pcb_text_geometry.md`](12_pcb_text_geometry.md) defines the verified uppercase/digit
   vector profile and full-cell fallback.
6. Convert the resolved board into typed circles, stroked segments/capsules, and polygons with
   separate ownership, semantic class, physical side, and clearance data. Use the no-false-negative
   spatial index and exact predicates from
   [`56_shape_geometry_foundations.md`](56_shape_geometry_foundations.md). Choose and document the
   product-specific candidate/search strategy separately; the SDK does not prescribe it.
7. Freeze the dense-board fallback contract: owner-association limit, obstacle hardness, behavior
   when no legal candidate exists, deterministic tie order, and final invariant. Insert every
   accepted same-side text immediately and validate the final result against the complete declared
   obstacle classes. Do not describe a least-conflict fallback as hard obstacle avoidance.
8. Convert the accepted board pose back with file 02 §4.2. Change only the selected marking
   leaf's `Align="Position"`, `Horz`, `Vert`, `X`, `Y`, and `Angle`. Do not change the text's
   side/layer or any global/component font setting. If no candidate is accepted and the marking
   stays in place, retain its current box as physical text; otherwise a later marking can overlap
   the failed one.
   If the accepted board pose equals the current pose, preserve the original local alignment and do
   not return that component unless the product explicitly intends to freeze it at
   `Align="Position"`. In particular, local `Common` plus global `Position` is already an effective
   custom pose, while local `Common` plus global `Auto` must remain automatic on a true no-op.
9. Preserve `/Source/Library` unchanged. Under `/Source/Board/Components`, return only the
   changed components, but each must be a **complete clone** of its exported `<Component>`
   record. Remove analysis-only top-level lists from the returned `<Board>`.
10. Validate all styles, transforms, point counts, references, and output numbers, then atomically
   replace the exchange file once. On any unsupported case, leave the original untouched and
   report the component/object identifier.

For large boards, use [`55_heavy_geometry_optimization.md`](55_heavy_geometry_optimization.md):
prepare curves/outlines once, query a no-false-negative two-tier spatial index, cache complete
metrics/transforms, preserve deterministic candidate order, and prove optimized/source/EXE
equivalence. Define obstacle clearance in one place; inflating both a stored obstacle and a
candidate by `c` creates `2c` separation and must be an intentional policy.

Minimum transform fixtures are: top/no flips; top `Flip=Y`; top `HorzFlip=Y`; ordinary bottom
(`Side=Bottom`, commonly also `Flip=Y`); and rotated bottom. Do not trust tests that generate
their expected coordinates with the same helper used by the implementation.

Fail closed for an unknown unit/enum, missing `PatternStyle` or `PadStyle`, malformed point
count, unresolved three-point arc, `By Paste` without resolvable paste geometry, or text whose
conservative bounds cannot be established.

### Narrow PCB component result

```xml
<Source Type="DipTrace-PCB" ...>
  <Library Type="DipTrace-ComponentLibrary" ...>
    <!-- preserve unchanged, including nested PatternLibrary -->
  </Library>
  <Board>
    <Components>
      <!-- complete clone of a changed exported component -->
      <Component Id="17" PatternStyle="PatType3" ...>
        ...all original attributes and children...
        <RefDesMarking>
          <Silk Show="Show" Align="Position" Horz="Center" Vert="Center"
                X="..." Y="..." Angle="..."/>
          <Assy ...unchanged.../>
        </RefDesMarking>
      </Component>
    </Components>
  </Board>
</Source>
```

## Inspect broadly, edit narrowly (Schematic)

Sometimes the plug-in needs more data to make a decision than it should send back for import.
For example, renaming nets from connected net ports requires `Comp=All` to inspect placed parts
and their library types, plus `Net=All` to see all candidate nets and wire selection flags. It
does **not** require re-importing every component or replacing any wire list.

With `ImpMode=Edit`, narrow the successful result before the final save:

1. Remove `/Source/Schematic/Components` from the returned document when components were used
   only for analysis. An absent top-level block is not edited.
2. Under `/Source/Schematic/Nets`, remove every `<Net>` you did not change.
3. On each changed net, keep its existing `Id` and original attributes, modify `<Name>` (or
   another intended scalar property), and omit `<Pins>` / `<Wires>` unless you intentionally
   want to replace connectivity or geometry.
4. Preserve the rest of the exchange document and all unknown attributes/elements.

Minimal returned Schematic data for a net-name edit:

```xml
<Schematic>
  … unchanged project metadata …
  <!-- no Components block: analysis-only input -->
  <Nets>
    <Net Id="3" NetClass="0" Locked="N" Enabled="Y">
      <Name>GND</Name>
      <!-- no Pins/Wires: retain the existing nested lists -->
    </Net>
  </Nets>
</Schematic>
```

For a runtime "selected nets only" option, still set `Net=All` in `settings.xml` and treat a
net as selected when any of its `<Wires><Wire>` children has `Selected="Y"`. Avoid
`Net=Selected` with Schematic `Edit`: the importer filters a returned `<Wires>` list down to
selected wires before rebuilding it. This test selects the **parent net** for a net-wide
operation; for custom per-wire work, inspect each `Wire@Selected` separately. PCB uses the same
parent-scope idea for `TNet`: any selected `<Trace>` qualifies the net, after which the whole
net is exported; use `Trace@Selected` / `Point@Selected` for trace- or segment-level work.

## Validate before you save

A quick pre‑save pass rules out the silent‑corruption classes above:

- Every **new or changed** reference points at a valid target. Validate against the original
  broad exchange before narrowing the result. A preserved reference inside a complete returned
  object may legitimately target a live-project object whose analysis-only list is omitted
  from the narrow `Edit` payload.
- You did **not reorder** a positional list (`<ViaStyles>`, `<NetClasses>`), and — if you authored a
  whole file — every top‑level array is dense and in `Id` order.
- Objects you **added** carry `Selected="Y"` (mandatory under a `Selected` filter, else dropped).
- You didn't include a nested `<Traces>`/`<Wires>` that silently drops members you meant to keep.
- Coordinates are in the file's `Units` with a **dot** decimal; angles in radians.
- PCB component records are complete clones and their `PatternStyle` resolves in the preserved
  `/Source/Library`.
- Arc/mask/text geometry was resolved conservatively; unsupported cases abort before output.
- On any error, **don't save** — leave the original file untouched (see `01_plugin_architecture.md` §8.1).

## Edit‑merge modes (whole‑list vs single object)

When your exchange uses import modes: `All` replaces the whole list; `Edit` matches **top-level**
objects by `Id`. For simple object kinds, `Selected` + `Edit` processes only members carrying
`Selected="Y"`; aggregate nets/buses/differential pairs use child-geometry selection rules
instead (see `01_plugin_architecture.md` §3). Pick the narrowest safe mode for the object kind
so you don't clobber objects you didn't touch.

| Level | Merge behavior |
|---|---|
| Top‑level object (net, component, shape, …) | Matched by `Id`; new/absent `Id` ⇒ added |
| Nested list with member `Id`s | **Importer-specific; member `Id` does not imply merge.** PCB component `<Pads>` and `<AddFields>` are rebuilt when present, so return the complete exported component. |
| Nested list **without** member `Id`s (net `<Traces>`, net/bus `<Wires>`, point lists) | **Subtree‑replaced** when present — omit the container to keep it, or re‑list everything |
| Delete | `Enabled="N"` on the object (wires: omit from the re‑listed `<Wires>`) |
