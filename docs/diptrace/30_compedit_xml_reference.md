# DipTrace XML — Component Editor (CompEdit) Reference

Dialect of the **Component Editor** and its component libraries. Binary libraries are `.eli`;
the XML equivalent is `.elixml` (same content, interchangeable via Save/Open As). Full spec:
`DipTraceXML_CompEdit_En.pdf` (section numbers below). Read
`02_diptrace_xml_conventions.md` first.

A DipTrace **component** = a schematic **symbol** (one or more *parts/sections*) **plus** an
attached **footprint** (pattern). This file describes the symbol side; the attached footprint
is a nested pattern library (see file 40).

## Top‑level structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Library Type="DipTrace-ComponentLibrary" Name="Audio Buzzers" Hint="Audio - Buzzers"
         Version="5.3.0.0" UID32="699252860" Units="inch">
  <Library Type="DipTrace-PatternLibrary" …>…</Library>   <!-- §3 attached footprints, keyed by PatternStyle -->
  <Categories> … </Categories>                             <!-- §4 category/type/subtype tree -->
  <Components>                                              <!-- §5 the components -->
    <Component Id="0"> … </Component>
  </Components>
</Library>
```

Plug‑in data node: **`/Library/Components`** (and, for a single component/part export, the
current `<Component>`/`<Part>` within it — governed by the CompEdit `ExpMode`, e.g.
`Part Partial`). The nested pattern `<Library>` (§3) uses the PattEdit dialect (file 40); a
part links to a footprint there by `PatternStyle`.

## `<Component>` → `<Part>` (§5.1)

```xml
<Component Id="0">
  <Part Id="0" RefDes="LS" PartType="Normal" ShowNumbers="Common" Type="Free"
        Int1="0" Int2="0" Width="0.2" Height="0.3" LockTypeChange="Y" SubFolderIndex="0">
    <Name>AI-1223-TWT-12V-R</Name>          <!-- first part only -->
    <PartName>Part 1</PartName>
    <Value>47k</Value>
    <Origin X="0" Y="0"/>
    <Datasheet>http://…</Datasheet>          <!-- first part only -->
    <SpiceModel Type="Diode"> <Model>…</Model> <Details>…</Details> </SpiceModel>
    <Manufacturer>ROHM Semiconductor</Manufacturer>   <!-- first part only -->
    <Category Index="1"> … </Category>                 <!-- first part only -->
    <Suppliers> … </Suppliers>                         <!-- first part only -->
    <Pins> <Pin …>…</Pin> … </Pins>
    <Shapes> <Shape …>…</Shape> … </Shapes>
    <Groups> <Group Id="0" X="…" Y="…"/> … </Groups>
    <AddFields> <AddField …>…</AddField> … </AddFields> <!-- first part only -->
    <Pattern Style="PatType0"/>                        <!-- first part only -->
    <InternalConnections> <IntCon X="1" Y="8"/> … </InternalConnections>  <!-- first part only -->
  </Part>
  <!-- more <Part> elements for a multi‑part component -->
</Component>
```

- A component is **one `<Component>` holding one or more `<Part>` sections** (gates/units).
  Several component‑wide fields — `Name`, `Datasheet`, `Manufacturer`, `Category`,
  `Suppliers`, `AddFields`, `<Pattern>`, `InternalConnections` — are **written on the first
  part only**; other parts inherit them.
- `<Part>` main attrs: `RefDes` (first part only), `PartType` = `Normal`/`Power`/`Net Port`,
  `ShowNumbers` = `Common`/`Show`/`Hide`, `Type` = symbol template
  `Free`/`2 Sides`/`IC-2 Sides`/`IC-4 Sides` with `Int1`/`Int2` meaning per template,
  `Width`/`Height` (symbol size), `LockTypeChange`. `SubFolderIndex` is unused (0).
- `<Origin X Y>` = offset from the symbol center `(0,0)` to the origin.

### `<Pin>` (§5.1.1.11.1)

```xml
<Pin Id="0" X="0.088" Y="0.1" Locked="N" Type="Default" ElectricType="Undefined"
     Orientation="90" PadId="1" Length="0.15" ShowName="N"
     NumXShift="…" NumYShift="…" NameXShift="0" NameYShift="0" SignalDelay="0"
     NumOrientation="0" NameOrientation="0" Group="-1">
  <SpiceSignal>NE</SpiceSignal>
  <Name>PLUS</Name>
  <PadNumber>1</PadNumber>
  <NameFont Size="5" FontSizeFloat="5" Width="-2" Scale="1" FontMono="N"/>
</Pin>
```

- `X`/`Y` are offsets from the symbol center; `Orientation` is a text enum `0|90|180|270`.
- **`<PadNumber>` is the pin↔pad link.** To bind a symbol pin to a footprint pad, the pin's
  `PadNumber` must **equal** the pattern pad's `Number`. (`PadId` is an internal index into the
  pattern pad array; keep it consistent with `PadNumber`.)
- `Type` = pin visual type (`Default`, `Polarity In/Out`, `Open`, `Clock`, `3 State`, …);
  `ElectricType` = ERC type (`Undefined`, `Passive`, `Input`, `Output`, `Bidirectional`,
  `Power`, …). `ShowName` shows the pin name; `NameFont` styles it.

### `<Shape>` (§5.1.1.12.1) — symbol graphics & text

```xml
<Shape Id="0" Type="Line" LineWidth="0.01" Locked="N"
       FontVector="N" FontMono="N" FontSize="6" FontSizeFloat="6.3" FontColor="8388608"
       TextShow="Any Text" FontName="" FontWidth="0" FontScale="0" Angle="1.5708"
       HorzAlign="Left" VertAlign="Top" TextAlign="Left" LineSpacing="1.2"
       TextWidth="8.15" TextHeight="6.53" Group="-1">
  <TextLines><TextLine>Segm</TextLine></TextLines>   <!-- if Type="Text" -->
  <Points><Point X="0.1" Y="0.15"/><Point X="0.1" Y="-0.15"/></Points>
</Shape>
```

- `Type`: `Line` · `Arc` · `Arrow` · `Rectangle` · `FillRect` · `Obround` · `FillObround` ·
  `Polyline` · `Polygon` · `Text`.
- `TextShow` selects what a text object displays: `Any Text` (literal, from `<TextLines>`) ·
  `Name` · `RefDes` · `Value` · `Part Name` · `Manufacturer` · `Datasheet`.
- `Angle` is radians CCW. `FontColor` is an integer color. `TextWidth`/`TextHeight` are
  read‑only (computed) bounds. `FontVector`/`FontMono` pick vector vs TrueType and
  mono/proportional. Points are offsets from the symbol center.

### `<Pattern Style="…"/>` (§5.1.1.15) — attached footprint link

`Style` matches a `PatternStyle` in the nested pattern `<Library>` (§3). This is how the
symbol is bound to its footprint. Set on the first part only.

### `<InternalConnections>` (§5.1.1.16)

`<IntCon X="a" Y="b"/>` declares that the two footprint pads whose **`<Pad Id>` equals `a` and
`b`** are internally shorted inside the component. `X`/`Y` are **pad `Id` references** (the same
values as `<Pad Id="…">`) — **not** net numbers and **not** array positions. Internal connections
are **component‑wide** and written **on the first part only**; a multi‑part component shares this
one list against the single pad array.

> ⚠️ **Editing pins/pads while internal connections exist — get this wrong and you crash
> DipTrace.** On import each `X`/`Y` is resolved to the current pad by matching its `Pad Id`; **if
> no pad has that `Id`, the value is left unresolved and indexes past the pad array — a delayed
> access violation** (the failure surfaces far from the cause). So:
> - **Removing or renumbering a pad:** first remove or update **every** `<IntCon>` whose `X` or `Y`
>   referenced that pad's `Id`. Never leave an `<IntCon>` pointing at a pad you deleted.
> - **Adding a pad:** existing connections are safe (their Ids still resolve). To connect the new
>   pad, append an `<IntCon>` whose `X`/`Y` are two **valid existing** pad `Id`s.
> - **Invariant:** after your edit, every `X` and every `Y` must reference a pad that still exists.

## `<Categories>` (§4) and per‑component `<Category>` (§5.1.1.9)

`<Categories>` is the library's tree of `Category` → `Types` → `SubTypes`, each with an
`Index`/`Number` and `<Name>`. A component references its classification with a
`<Category Index="…"><Name>…</Name><CategoryTypes>…</CategoryTypes></Category>` block (first
part only).

## Cross‑reference cheat‑sheet

| Attribute / element | Points to |
|---|---|
| `<Pattern Style>` | a `PatternStyle` in the nested pattern `<Library>` (§3) |
| pin `<PadNumber>` | pattern pad `<Number>` (binds pin↔pad) |
| `<Pin PadId>` | index into the pattern pad array |
| `Group` (pin/shape) | part `<Groups>`→`<Group Id>` |
| `<Category Index>` | `<Categories>`→`<Category>` (§4) |
| `<IntCon X/Y>` | two `<Pad Id>` values — the pads shorted internally (must stay valid) |

For any attribute/enum not shown, consult `DipTraceXML_CompEdit_En.pdf`. The attached
footprint's structure (pads, pad styles, shapes, holes, 3D model) is in
`40_pattedit_xml_reference.md`.
