# DipTrace XML — PCB Layout Reference

Dialect of the **PCB Layout** program. Full field‑by‑field spec: `DipTraceXML_Pcb_En.pdf`
(section numbers below refer to it). Read `02_diptrace_xml_conventions.md` first.

## Top‑level structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Source Type="DipTrace-PCB" Version="4.3.0.x" Units="mm">
  <Library Type="DipTrace-ComponentLibrary" …>              <!-- §3  design‑cache component library -->
    <Library Type="DipTrace-PatternLibrary" …>…</Library>   <!-- §3.1 footprints, keyed by PatternStyle -->
    <Categories>…</Categories>
    <Components>…</Components>
  </Library>
  <Board>                                                    <!-- §4  the editable project -->
    …
  </Board>
</Source>
```

Plug‑in data node: **`/Source/Board`**. The single `<Library>` is a full CompEdit‑format
component library (the project's *design cache*) that **nests** the pattern library **inside
it** (files 30 and 40) — it is not a second sibling library. Each footprint gets a unique
`PatternStyle` that placed components reference. *(Verified against a real exported PCB file:
the nested block really is `Type="DipTrace-PatternLibrary"`; the PDF's §3.1 example mislabels
it `DipTrace-ComponentLibrary`, and lists §3/§3.1 as if they were siblings.)*

## `<Board>` object catalog (§4)

Settings/infrastructure, then the geometry lists a plug‑in usually cares about.

| Element | §  | What it is |
|---|---|---|
| `<BoardOutline>` + `<Points>` | 4.1 | Closed board edge with straight and three-point circular-arc segments (`Locked`, `Selected`). |
| `<Panel>` | 4.2 | Panelization (V‑scoring / tab routing). |
| `<SheetSettings>` | 4.3 | Drawing sheet, margins, zones, and 6 title blocks (`BottomRightBlock`, `BottomLeftBlock`, `TopRightBlock`, `TopLeftBlock`, `ExtTopLeftBlock`, `ExtBottomLeftBlock`) with `<Field>` lists. |
| `<Settings>` | 4.4 | Global project settings — part **markings** (fonts + per‑field show/align), assembly variants, grid, origin, add‑to‑assembly, layer display, **line widths**, routing defaults, mask/paste swell/shrink, layer panel, related schematic, locks, jumper layer, project dir. |
| `<ProjectLibs>` | 4.5 | Library folders/files (`<Path>`/`<Var>`). |
| `<CopperLayers>` → `<Lay>` | 4.6 | Signal/plane layers. **`Id` here is what every `Lay`/`LayId` reference points to.** (`NetId` points at a *net*, never a layer — a plane `<Lay>` itself carries a `NetId` naming the net it belongs to.) |
| `<NonSignals>` → `<NonSignal>` | 4.7 | Custom non‑signal layers. |
| `<LayerStackName>`, `<LayerStackItems>` | 4.8–4.9 | Stack‑up + materials. |
| `<HierarchySheets>` | 4.10 | Hierarchy blocks. |
| `<ViaStyles>` → `<ViaStyle>` | 4.11 | Via styles (`Id`, `Size`, `HoleSize`, `Lay1`,`Lay2`, and a `<Name>` child; through‑vs‑blind is derived from `Lay1`/`Lay2`). The `Id` **equals the element's position**, and a `ViaStyle="N"` reference binds **by position** — the reader ignores the stored `Id` and uses list order (`-1` = none). Never reorder the list. |
| `<NetClasses>` → `<NetClass>` | 4.12 | Net‑class rules, per‑layer widths/clearances, autorouting. |
| `<ClassToClass>` | 4.13 | Class‑to‑class clearances. |
| `<DRC>` | 4.14 | DRC rule set + per‑layer clearances/sizes. |
| `<ConnectivityCheck>` | 4.15 | Net‑connectivity check flags. |
| `<MainLengthRule>`, `<LengthRules>` | 4.16–4.17 | Length‑matching rules. |
| `<Components>` → `<Component>` | 4.18 | Placed components. |
| `<Ratlines>` → `<Ratline>` | 4.19 | Unrouted connections. |
| `<Nets>` → `<Net>` | 4.20 | Nets, with pads, teardrops, and **traces**. |
| `<DifferentialPairs>`, `<RemovedDifferentialPairs>` | 4.21–4.22 | Diff pairs + segment/center‑point geometry. |
| `<CopperPours>` → `<CopperPour>` | 4.23 | Copper pours / planes. |
| `<Shapes>` → `<Shape>` | 4.24 | Free graphics & text (the most common plug‑in target). |
| `<DesignErrors>` → `<DesignError>` | 4.25 | DRC results. |
| `<Tables>` → `<Table>` | 4.26 | BOM / pick‑and‑place / free tables. |
| `<Dimensions>` → `<Dimension>` | 4.27 | Dimensions & pointers. |
| `<Groups>` → `<Group>` | 4.28 | Group registry (`Id`, `Selected`). |

### Board outline arcs and cutouts

`<BoardOutline><Points><Point .../></Points></BoardOutline>` is not always a straight polygon.
It may also be completely absent on an in-progress PCB that already contains placed components.
Treat "absent" separately from "present but malformed": a malformed serialized outline remains an
error, while a plug-in that does not edit the board edge may use a documented **virtual** working
boundary. For a component-text placer, one conservative fallback is the rectangle around all
enabled non-via component bounds, inflated on every side by:

```text
largest visible full-cell text extent
+ maximum owner-search gap
+ board-edge safety margin
+ explicit synthetic-boundary allowance
```

This rectangle is an analysis limit only; do not return it as a new `<BoardOutline>`. If neither a
valid outline nor any bounded component exists, placement has no defensible working area and should
fail without writing.

For a point with `Arc="Y"`, the three consecutive vertices are:

```text
previous point = arc start
Arc="Y" point  = a point on the circular arc
next point     = arc end
```

The arc-marked middle point consumes the next point; that next point is not also the start of
an ordinary straight edge. The previous point may wrap from the end of the closed outline when
the arc marker is at index 0. Reconstruct the circle through all three points and follow the
sweep that passes through the middle point. Chord-only containment is unsafe, especially for
inward/concave arcs. Either tessellate at a documented conservative tolerance or fail closed.

Board interior is the outline **minus** enabled `<Shape Layer="Board Cutout">` regions. A
placement-inside-board test must handle both the curved outer boundary and all cutouts; testing
only the outline bounding box is insufficient.

## Key objects for plug‑ins

### `<Shape>` (§4.24.1) — free graphics & text

```xml
<Shape Id="0" Type="Polyline" AllLayers="N" Layer="Top Assy" LayId="0" LineWidth="0.2"
       Angle="0" HorzAlign="Left" VertAlign="Top" TextAlign="Left" Inverted="N"
       FontVector="Y" FontSize="10" FontWidth="-2" FontScale="1" LineSpacing="1.2"
       Group="-1" NetId="-1" PanelExclude="N" Locked="N" Selected="N">
  <Points><Point X="86.995" Y="21.59"/> … </Points>   <!-- geometry -->
  <FontName>Tahoma</FontName>                          <!-- if TrueType -->
  <TextLines><TextLine>Power</TextLine></TextLines>    <!-- if Type="Text" -->
</Shape>
```

- **`Type`**: `Line` · `Arc` · `Rectangle` · `FillRect` · `Obround` · `FillObround` · `Text` ·
  `Picture` · `Polyline` · `Polygon`. A vector QR shape is serialized as the literal numeric
  token `Type="10"` because it lies beyond the public board-shape name table.
  Point counts: Line/Rectangle/Obround = 2; Arc = 3 (start, mid, end);
  Text/Picture/QR = exactly 1 anchor; Polyline/Polygon = n.
- **`Layer`** (text enum): `Top Assy`, `Top Silk`, `Route Keepout`, `Signal/Plane`,
  `Bottom Silk`, `Bottom Assy`, `Top Mask`, `Top Paste`, `Bottom Paste`, `Bottom Mask`,
  `Board Cutout`, `Placement Keepout`, `None`, `Top Dimension`, `Bottom Dimension`,
  `Non-Signal`, `Top Courtyard`, `Bottom Courtyard`, `Top Outline`, `Bottom Outline`,
  `Top Terminals`, `Bottom Terminals`. **Each value is one literal token** — there is no
  `Top/Bottom X` combined form; an unrecognized string resolves to *no layer*.
  For `Signal/Plane` use `LayId` → copper‑layer `Id`; for `Non-Signal` use `LayId` →
  non‑signal‑layer `Id`. `AllLayers="Y"` puts a signal shape on all copper layers.
- **`LineWidth`** applies to non‑filled, non‑text shapes only. If it is absent, resolve the
  effective common width for that layer when the corresponding project default is exported;
  do not assume zero. Mask and Board Cutout defaults are not present in every exchange file, so
  collision/clearance tools must use a documented conservative fallback (or fail closed) when
  the exact width cannot be recovered.
- **`Angle`** (text/picture/QR) is radians CCW. Points are in board units. Text rectangles use
  one anchor point plus `TextWidth`/`TextHeight`; Picture and QR rectangles use one anchor point
  plus `PictureWidth`/`PictureHeight`. Do not map Picture/QR to the Text size attributes merely
  because they reuse the same angle/alignment fields internally. `TextWidth`/`TextHeight`
  describe the resolved layout/font cell, not a universal tight box around visible glyph strokes.
  Reconstruct the center with the **full** cell before rotation/placement; do not trim first.
  See [`12_pcb_text_geometry.md`](12_pcb_text_geometry.md).
- `<Points>` children are `<Point X= Y=/>` — the **same** `<Point>` element used by trace and
  board‑outline geometry. **Write `<Point>` for geometry** — it is what the canonical
  serializer emits. Reference lists (a net's `<Pads>`, §4.20.1) use `<Item …/>`. This is a
  *naming convention, not reader‑enforced*: the importer reads coordinates from any child of a
  point/segment container (so `<Item>` inside `<Points>` is tolerated, and the footprint
  pad‑mask `<TopSegments>`/`<BotSegments>` lists are the one place the serializer itself
  writes geometry as `<Item X1 Y1 X2 Y2>`).

> Removing/replacing a shape from a plug‑in: set `Enabled="N"` on the original and append new
> `<Shape>`s with `Selected="Y"` (+ a shared `Group`). See `01_plugin_architecture.md` §6.
> **`Enabled` is a real serialized `<Shape>` attribute** that the importer honors even though
> the PDF's §4.24.1.1 attribute table doesn't list it — the shipped `DashDotLine` example
> depends on it.

For conservative collision bounds:

- `Rectangle`/`FillRect`/`Obround`/`FillObround` store two opposite corners of an
  axis-aligned box in the shape's local frame. Reconstruct all four corners **before** a
  component placement rotation; transforming only the two serialized corners can underbound
  or even collapse the AABB.
- `Arc` is start/middle/end on one circle. Exact bounds include cardinal-angle extrema that
  lie on the selected sweep. A full-circle bound is conservative; a box over only the three
  serialized points is not.
- Open line/arc/rectangle/obround obstacles include half the effective line width. Filled
  shapes use their filled interior.
- Footprint non-text shapes have no independent placement angle: their points already encode
  local geometry, then the component transform in file 02 rotates the result.

### `<Component>` (§4.18.1) — placed component

```xml
<Component Id="0" UpdateId="-1" PatternStyle="PatType0" X="15.24" Y="22.86" Angle="0"
           Side="Top" Flip="N" HorzFlip="N" Group="-1" Locked="N" Selected="N">
  <RefDes>C1</RefDes> <Name>10SVP10M</Name> <Value>47</Value>
  <AddFields>
    <AddField Type="Text"><Name>Assembly Variant</Name><Text>Prototype</Text></AddField>
  </AddFields>
  <Pads> <Pad Id="1" NetId="-1" InternalConnection="-1"> … </Pad> … </Pads>
  <RefDesMarking>…</RefDesMarking>  <!-- + Name/Value/Pattern/Manufacturer/Datasheet markings -->
</Component>
```

- `PatternStyle` → a footprint in the embedded pattern `<Library>`. `Side`=`Top`/`Bottom`,
  `Angle` radians. The embedded footprint is an exchange-time instance variant. Map its
  geometry with the exact formula in file 02 §4.1; do not apply `Flip` or `HorzFlip` again.
- Each `<Pad Id=…>`'s `Id` is what nets, ratlines, and diff pairs reference (with the
  component `Id`).
- User-defined component fields live in `<AddFields>/<AddField Type="Text">` with `<Name>` and
  `<Text>` children. Field index `n` is its zero-based order and binds footprint text through the
  numeric token `TextShow=str(20+n)`. Standard `RefDes`/`Name`/`Value` remain direct component
  children; Pattern/Manufacturer/Datasheet are resolved from the referenced embedded pattern.
- The referenced footprint can also contain `<Holes><Hole X Y Diam HoleDiam …/></Holes>`.
  `Diam` is the mechanical/keepout diameter and `HoleDiam` is the drilled diameter. A
  surface-obstacle tool should conservatively use the larger diameter, transform the local
  `X/Y` through the footprint placement, and block both board sides.
- `Pad@Side="Bottom"` carries a footprint-local side swap. Resolve physical SMD copper with the
  component-side truth table in file 02 §4.3; Through copper belongs to both surfaces.
  `TopMask`/`TopPaste` and their segment lists describe the pad's own (near) face;
  `BotMask`/`BotPaste` describe its opposite (far) face. First resolve the pad's own physical side
  from `Component@Side` and footprint-local `Pad@Side`; select `Top*` on that physical side and
  `Bot*` on the other. The names are not absolute board Top/Bottom.

#### Component markings and bound footprint text

Each standard marking block (`RefDesMarking`, `NameMarking`, `ValueMarking`,
`PatternMarking`, `ManufacturerMarking`, `DatasheetMarking`, plus additional fields) can contain
`<Silk>` and `<Assy>` leaves:

```xml
<RefDesMarking>
  <Silk Show="Show" Align="Position" Horz="Center" Vert="Center"
        X="1.2" Y="-0.8" Angle="0"/>
  <Assy Show="Common" Align="Common"/>
</RefDesMarking>
```

- `Show=Common|Show|Hide`; `Common` resolves through the corresponding global field under
  `/Source/Board/Settings/Markings`.
- `Align=Common|Center|Top|Bottom|Left|Right|Corner|Auto|Position`. Resolve an **effective**
  alignment first: local `Common` inherits the corresponding global `SilkAlign`/`AssyAlign`.
  Only effective `Position` guarantees that stored `X/Y/Angle` are the chosen custom pose;
  effective `Auto` is recomputed by the host. `Horz=Center|Right|Left` and
  `Vert=Center|Bottom|Top` define the stored anchor.
- The `<Silk>` leaf follows the component's side automatically. It is not a free shape whose
  `Layer` can be changed.
- Resolve displayed values by these exact paths:

  | Marking / bound value | XML source |
  |---|---|
  | `RefDes` | changed component's direct child `<RefDes>` |
  | `Name` | changed component's direct child `<Name>` |
  | `Value` | changed component's direct child `<Value>` |
  | `Pattern` | `<Name>` of the embedded pattern whose `PatternStyle` matches `Component@PatternStyle` |
  | `Manufacturer` | that embedded pattern's `<Manufacturer>` |
  | `Datasheet` | that embedded pattern's `<Datasheet>` |
  | `Unique Name` | that embedded pattern's `<Name_Unique>` |
  | additional/user field | the placed component's matching `<AddFields>` entry |

  PCB `<Component>` does **not** directly serialize `Pattern`, `Manufacturer`, or `Datasheet`
  value children. Locate them under the nested `DipTrace-PatternLibrary` in `/Source/Library`;
  do not search `<AddFields>` as a fallback. If the referenced pattern or requested standard
  value cannot be resolved, skip/fail closed for that marking rather than measuring the wrong
  text.
- Font settings come from `/Settings/Markings`. A component `CustomMarkingFont="Y"` overrides
  the size with `MarkingFontSizeFloat` (fallback `MarkingFontSize`); the marking leaf has no
  independent font size or computed `TextWidth`/`TextHeight`. Preserve those settings/attributes
  to preserve the font. File 12 defines the source-independent full-cell/visible-ink strategy and
  the conservative fallback for uncalibrated text.
- Marking coordinates obey `CompRotate`, not the footprint-side transform. Use file 02 §4.2
  for forward/inverse formulas and the exact Auto sequencing/bounds caveats. In particular, do
  not drop a shown empty field from an Auto resolver and do not approximate `CompRotate=N`
  `contw/conth` by rotating `Pattern Width/Height` as one rectangle when render parity is required.

A regular footprint `<Shape Type="Text" TextShow="RefDes|Name|...">` is a **different
mechanism**. An author-owned match on footprint-local `Layer="Top Silk"` dynamically substitutes
component data and suppresses generation of the corresponding component marking; DipTrace scans
matching shapes from the highest index. Bottom Silk and assembly text do not suppress the silk
marking. Changing `<Component>/<...Marking>/<Silk>` does not move that shared footprint shape.
Classify the text mechanism first; per-instance movement of a shared `PatternStyle` text shape is
not expressible by editing only a component marking, and the rendered footprint text must still
be treated as an obstacle.

The serialized suppression token must match exactly. `Pattern` is literal `TextShow="7"` and
user/additional field index `n` is literal `TextShow=str(20+n)`. These values fall outside the
named enum table and therefore remain numeric strings. `TextShow="Any Text"` is unbound
decorative text and suppresses no generated marking.

For `ImpMode=Edit`, return a **complete clone** of every changed component, not a sparse
`<Component Id>` fragment. Keep `/Source/Library` unchanged and return only the complete
components that changed. See file 01 §6 and the PCB cookbook in file 50.

### Vias: routed and static

PCB exchange has two via representations:

- A routed via is a trace `<Point X Y ViaStyle="n" ...>`. Its size, hole, and layer span come
  from `<ViaStyles>`; segment attributes live on the second point.
- A static/free via is `<Component Type="Via" ViaStyle="n" ...>` and can carry
  `<Pads><Pad><MaskPaste .../></Pad></Pads>` overrides.

`ViaStyle` resolves by list position. Surface relevance follows the style's `Lay1`/`Lay2`
span; a conservative “avoid vias” implementation may block the full via diameter on both
surfaces. Account for the static-via mask overrides when mask openings are obstacles.

### `<Net>` (§4.20.1) with `<Trace>` and trace `<Point>`

```xml
<Net Id="0" NetClass="0" RouteMode="Ratlines" Locked="N">
  <Name>AP-WAKE-BT</Name>
  <Pads><Item Comp="1" Pad="1"/> … </Pads>          <!-- component Id + pad Id -->
  <Traces>
    <Trace Id="0" Connected1="Pad" Object1="1" SubObject1="1" Point1="-1"
                  Connected2="Pad" Object2="0" SubObject2="1" Point2="0"
                  Group="1" Selected="N">
      <Points>
        <Point Id="0" X="20.955" Y="12.7" Lay="0" Width="0.33" Jumper="0"
               Arc="N" ViaStyle="-1" Meander="0" MeanderAngle="0" Selected="N"/>
        …
      </Points>
    </Trace>
  </Traces>
</Net>
```

- Trace endpoints connect to `Pad` / `Trace` / `Segment` / `Separate Trace` / `Free` via the
  `Connected/Object/SubObject/Point` quads.
- **Per‑segment attributes are on the segment's second point** (`Lay` → copper layer `Id`,
  `Width`, `ViaStyle` → via‑style `Id` or `-1`, `Jumper` 0/1/2, `Arc`, meander fields). The
  first point's non‑geometry attributes are ignored. Point `Id`/`X`/`Y` always matter.
- Nets also hold `<TeardropParams>` and a `<Teardrops>` polygon list.

#### How DipTrace resolves connectivity on import

Electrical membership lives on the **pad**: a pad's net is its own **`NetId`** (the pad attribute),
and that is the **authoritative** carrier — it is read straight from each `<Pad>` and preserved
across import. The net's `<Pads>` list is a **derived mirror** (DipTrace rebuilds it on import), so
**set the pad's `NetId` to move a pad between nets — don't rely on editing `<Pads>` alone.** From the
pad `NetId`s DipTrace **auto‑generates the ratlines** (unrouted connections), so you don't hand‑build
them and a pad **keeps its net even when unrouted**.

Traces are the *routed* connections. What matters for a trace is its **declared endpoints** —
the paired attributes `Connected1/Object1/SubObject1/Point1` and
`Connected2/Object2/SubObject2/Point2` (one set per end, as in the example above). For a pad
connection: `ConnectedN="Pad"`, `ObjectN` = component `Id`, `SubObjectN` = pad `Id` (there is
no `Pad=` attribute on a trace). **Not** where the trace visually sits — a trace drawn over a
pad without an endpoint declaring it is not connected.

Consequences when a plug‑in changes connections:
- **Connecting pads that belong to different nets merges those nets into one; removing the last
  connection between two groups of pads splits a net in two.** DipTrace derives the final
  connectivity from the connections plus the pad assignments — so a trace endpoint you put on a pad
  places that pad in the trace's net. Connect **deliberately**: it's easy to merge two nets by
  accident.
- **Bad endpoint refs are safe:** an endpoint whose `ObjectN`/`SubObjectN` doesn't exist becomes a
  **free end** on import (no crash, no wrong connection).
- **Merge (Edit mode):** a `<Net>` with a **new `Id`** is added as a new net; a `<Net>` with an
  **existing `Id`** overwrites that net in place. **Traces are NOT merged individually** — a
  `<Trace>` has no `Id` merge key: if your `<Net>` contains a `<Traces>` element, DipTrace
  **replaces the net's entire trace list** with exactly the traces you list (any trace you omit is
  lost). To add one trace, re‑list all the net's current traces plus the new one; to leave routing
  untouched, omit `<Traces>` entirely.
- **The net's `<Pads>` list alone moves nothing.** Membership is carried by each pad's own
  `NetId` (see above); a new `<Net>` whose only content is a `<Pads>` list — with no pad `NetId`
  updates and no traces — imports as an empty net and the listed pads stay where they were. To
  *create* a net and populate it, give the new `<Net>` an explicit unused `Id` **and** set that
  `Id` as `NetId` on each member `<Pad>` (which requires the components to be in the exchange —
  `Comp=All`, and `Net=All` so the whole net list is visible for choosing a genuinely free `Id`).

#### What "selected net" means

`<Net>` has no parent-level `Selected` attribute. For PCB plug-in export, `Net=Selected` means
that at least one routed `<Trace>` in the net has `Selected="Y"` (`TNet.line.selected`). The
test does not inspect trace `<Point Selected="Y">` directly. Once a net qualifies, DipTrace
exports the **whole net with all its traces**, not only the selected traces.

Use this parent-level test when the operation applies to the whole net. For custom work on
individual routes or segments, inspect each `Trace@Selected` and, where relevant,
`Point@Selected` yourself. If you return `<Traces>`, remember that the complete nested list is
replaced; omit it when changing only a scalar net property.

### `<CopperPour>` (§4.23.1)

```xml
<CopperPour Id="0" NetId="-1" Lay="0" Priority="0" Poured="Y" Type="Solid"
            Clearance="0.33" LineWidth="0.1" LineSpacing="0.1" Spoke="Direct"
            SpokeWidth="0.33" Group="-1" Locked="N" Selected="N">
  <Points><Point X="20.79" Y="11.42"/> … </Points>   <!-- outline polygon -->
</CopperPour>
```

`Lay` → copper‑layer `Id`; `NetId` → net `Id` (or `-1`); `Type` = `Solid` / `Horizontal Lines`
/ `Vertical Lines` / `Cross 45` / `Cross 90`. `Poured` / `RegionsDone` reflect fill state.

In `ImpMode=Edit`, a returned/changed copper pour is invalidated and must be repoured; an omitted,
untouched pour keeps its existing fill. If a changed board outline moves a poured plane that is
snapped to that outline, its fill is likewise invalidated. Keep analysis-only pours out of a
narrow result unless the operation intentionally changes them.

### `<Dimension>` (§4.27) and `<Table>` (§4.26)

`<Dimension>` has `Type` = `Horizontal|Vertical|Free|Radius|Pointer`, two measured points
(`X1/Y1`, `X2/Y2`), a dimension‑line origin (`XD/YD`), a `Layer`, connection quads, and font
attributes. `<Table>` describes BOM / pick‑and‑place / hole‑size / free tables via
`<AutoUpdate>` + `<Columns>` + a `<Cells>` grid; each cell is its own text box.

## Cross‑reference cheat‑sheet

| Attribute | Points to |
|---|---|
| `Lay` / `LayId` (copper) | `<CopperLayers>`→`<Lay Id>` (§4.6) |
| `LayId` (Non‑Signal shape) | `<NonSignals>`→`<NonSignal Id>` (§4.7) |
| `NetId` | `<Nets>`→`<Net Id>` (§4.20), `-1` = none |
| `ViaStyle` | the `<ViaStyles>` list (§4.11) **by position** — the element's `Id` equals its index and is not used for lookup; `-1` = none |
| `NetClass` | the `<NetClasses>` list (§4.12) **by position** — the `Id` equals the index; reordering the list silently reassigns rules |
| net `<Item Comp Pad>` | `<Component Id>` + that component's `<Pad Id>` (§4.18) |
| `Group` | `<Groups>`→`<Group Id>` (§4.28), `-1` = none |
| `PatternStyle` | footprint in the embedded pattern `<Library>` |
| `UpdateId` | link back to the source schematic part |

For any object or attribute not shown here, consult the corresponding section of
`DipTraceXML_Pcb_En.pdf`.
