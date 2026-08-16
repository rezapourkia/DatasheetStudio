# DipTrace XML — Pattern Editor (PattEdit) Reference

Dialect of the **Pattern Editor** and its footprint libraries (`.lib`). The same structure
appears **nested** inside PCB files and inside component libraries (the "attached patterns"
section). Full spec: `DipTraceXML_PattEdit_En.pdf` (section numbers below). Read
`02_diptrace_xml_conventions.md` first.

A **pattern** = a footprint: a set of pads (each referencing a shared **pad style**), plus
silkscreen/assembly shapes, mounting holes, dimensions, and an optional 3D model.

## Top‑level structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Library Type="DipTrace-PatternLibrary" Name="BGA Pitch 0.35mm" Hint="…"
         Version="5.3.0.0" UID32="1906685151" Units="inch">
  <PadStyles> <PadStyle …>…</PadStyle> … </PadStyles>   <!-- §3 reusable pad stacks -->
  <Categories> … </Categories>                           <!-- §4 category tree -->
  <Patterns>                                             <!-- §5 the footprints -->
    <Pattern …> … </Pattern>
  </Patterns>
</Library>
```

Plug‑in data node: **`/Library/Patterns`** (and, per `ExpMode`, the current `<Pattern>`).
When this appears nested (in a PCB or component file), each pattern additionally carries a
unique **`PatternStyle`** used by the outer file to reference it.

## `<PadStyle>` (§3.1) — reusable pad stack

```xml
<PadStyle Name="PadT3" Type="Through" HoleType="Round" Hole="0.0354">
  <MainStack Shape="Obround" Width="0.0591" Height="0.0591" XOff="0" YOff="0"/>
  <Terminals> <Terminal Shape="Rectangle" X="0" Y="0" Angle="0" Width="0.8" Height="0.4"
              Corner="0"/> … </Terminals>              <!-- optional, max 4 -->
  <MaskPaste TopMask="Tented" BotMask="Open" TopPaste="Solder" BotPaste="Segments" …/>
</PadStyle>
```

- `Name` is what pads reference (`<Pad Style="PadT3">`). `Type` = `Surface` / `Through`;
  `HoleType` = `Round` / `Obround`; `Hole` = hole size (also keepout diameter for a Fiducial).
- **`<MainStack>`** is the copper shape: `Shape` = `Ellipse` / `Obround` / `Rectangle` /
  `Polygon` / `D-shape` / `Fiducial`; `Width`/`Height`; `XOff`/`YOff` (shape offset from the
  hole center on a through pad); `Corner` = corner rounding % (0 = square, 0..50 = roundrect).
  A `Polygon` stack carries a `<Points>` list relative to the stack/pad center. `XOff`/`YOff`
  and the polygon rotate with the placed pad's `Angle`.
- **`<Terminals>`** (≤ 4) are optional secondary copper shapes on the pad. A terminal supports
  `Ellipse` / `Obround` / `Rectangle` / `Polygon` / `D-shape`. Its `X/Y` is pad-local, its
  `Angle` adds to the pad angle, and polygon `<Points>` are terminal-local. Use `<Points>` when
  present even if `Width`/`Height` are zero or stale. A collision envelope is the union of the
  main stack and every terminal.

### Exact `<MaskPaste>` behavior

Missing state attributes mean `Common`.

| Attribute | Values | Effective geometry |
|---|---|---|
| `TopMask` / `BotMask` | `Common`, `Open`, `Tented`, `By Paste` | `Tented` has no opening. `Open` uses the pad geometry plus effective solder-mask swell. `Common` uses project/via defaults. `By Paste` delegates to the corresponding paste geometry. |
| `TopPaste` / `BotPaste` | `Common`, `Solder`, `No Solder`, `Segments` | `No Solder` has no paste. `Solder` uses the pad geometry inset by effective paste shrink. `Common` uses project/via defaults. `Segments` uses the matching segment list. |

When this pattern is nested in a PCB exchange, `CustomSwell` overrides
`/Source/Board/Settings/SolderMaskSwell`; absent means use the board project value. It may be
negative. `CustomShrink` similarly overrides the board's `PasteMaskShrink`; paste shrink is
applied inward. In a standalone PattEdit library there is no `/Source/Board`, so preserve
`Common`/override state and defer final physical mask/paste geometry until placement in a PCB
project. Never serialize an internal sentinel as a value.

`<TopSegments>`/`<BotSegments>` contain `<Item X1 Y1 X2 Y2/>` rectangles in pad-local
coordinates. They are paste apertures, not generic solder-mask shapes. Under `By Paste` they
also determine the mask opening. Transform them by pad angle plus component placement. For a
PCB exchange, `Top*` state and segment lists belong to the pad's own (near) face and `Bot*` to its
opposite (far) face. Resolve the own physical side from component side plus footprint-local pad
side as specified in file 02 §4.3. If a `By Paste` dependency or required segment list cannot be
resolved, fail closed rather than substituting the copper pad.

## `<Pattern>` (§5.1.1) — a footprint

```xml
<Pattern Id="0" RefDes="RD" Mounting="Chassis" Width="250" Height="400" Orientation="0"
         LockTypeChange="N" Type="Free" Float1="0" Float2="0" Float3="0" Int1="0" Int2="0">
  <Name>BGA16CP80_4X4_300X300X90B32M</Name>
  <Name_Description>…</Name_Description> <Name_Unique>ROHM_BGA016W030</Name_Unique>
  <Value/> <Manufacturer>…</Manufacturer> <Datasheet>…</Datasheet>
  <PossibleNames> <PossibleName>CSBGA25</PossibleName> … </PossibleNames>
  <Category Index="0"> … </Category>
  <Origin X="-1.95" Y="0.35" Cross="Y" Circle="Y" Common="Hide" Courtyard="Show"/>
  <RecoveryCode Generator="Y" Model="Y">[…]</RecoveryCode>
  <Groups> <Group Id="0" X="…" Y="…"/> … </Groups>
  <AddFields> … </AddFields>
  <Suppliers> … </Suppliers>
  <DefPad Style="PadT7"/>
  <Pads> <Pad …>…</Pad> … </Pads>
  <Shapes> <Shape …>…</Shape> … </Shapes>
  <Holes> <Hole …/> … </Holes>
  <Dimensions> <Dimension …/> … </Dimensions>
  <Model3D …> … </Model3D>
</Pattern>
```

- Main attrs: `Id` (position in the library — keep dense/in‑order when generating a full
  file); `RefDes`; `Mounting` = `Through`/`SMD`/`Chassis`/`Mixed` (no `None` value);
  `Width`/`Height` (extent of objects); `Orientation` = `0|90|180|270` **metadata only — it
  does not rotate the stored geometry**; `Type` + `Float1..3`/`Int1..2` = creation‑template
  parameters (`Free`, `Circle`, `Lines`, `Square`, `Matrix`, `Rectangle`, `Zig-Zag`,
  `IPC-7351`, plus the legacy values `Right Angle`, `Left Angle`, `T` still accepted from old
  files).
- `<Origin>` offset (from pattern center) with cross/circle target + show flags (`Cross`,
  `Circle`, `Common`, `Courtyard`) — it has **no** angle attribute. `<RecoveryCode>` is the
  IPC‑7351 generator string (empty for hand‑drawn patterns).
- `<DefPad Style="…"/>` = default pad style for new pads.

### `<Pad>` (§5.1.16.1.1)

```xml
<Pad Id="1" Style="PadT7" X="-0.7849" Y="5.2299" Angle="0" Locked="N" Side="Top" Group="0">
  <Number>A1</Number>
  <Note/>
</Pad>
```

- `Style` → a `<PadStyle Name>` in `<PadStyles>` (§3). `X`/`Y` are offsets from the pattern
  center; `Angle` radians CCW; `Side` = `Top`/`Bottom`.
- **`<Number>` is the pad's number** — the value a component symbol pin binds to via its
  `PadNumber` (see file 30). `Id` is the pad's internal identifier within the pattern.

### `<Shape>` (§5.1.17.1) — silkscreen / assembly graphics & text

```xml
<Shape Id="1" Type="Text" Locked="N" Layer="Top Silk" FontVector="Y" FontMono="N"
       FontName="Tahoma" FontSize="8" FontSizeFloat="8.88" FontScale="1" FontWidth="-2"
       TextShow="Any Text" HorzAlign="Left" VertAlign="Top" TextAlign="Left"
       LineSpacing="1.2" TextWidth="…" TextHeight="…" Angle="0" AllLayers="N" Group="1">
  <TextLines/> <Points><Point X="-1.35" Y="-1.5"/></Points>
</Shape>
```

- `Type`: `Line` · `Rectangle` · `Obround` · `FillRect` · `FillObround` · `Arc` · `Text` ·
  `Polyline` · `Polygon`. `None` and legacy literal `-1` are known empty/no-geometry states;
  skip them. Do not treat another unknown future token as empty—an obstacle/clearance plug-in
  must fail closed until its geometry is defined.
- **`Layer`** (text enum): `Top Silk`, `Top Assy`, `Top Mask`, `Top Paste`, `Bottom Paste`,
  `Bottom Mask`, `Bottom Assy`, `Bottom Silk`, `Top`, `Top Keepout`, `Bottom Keepout`,
  `Bottom`, `Board Cutout`, `Top Dimension`, `Bottom Dimension`, `Non-Signal`,
  `Top Courtyard`, `Bottom Courtyard`, `Top Outline`, `Bottom Outline`, `Top Terminals`,
  `Bottom Terminals`. **Each value is one literal token** — there is no `Top/Bottom X`
  combined form; an unrecognized string resolves to *no layer*.
- `TextShow` for a text object: `Any Text` · `Name` · `RefDes` · `Value` · `Manufacturer` ·
  `Unique Name` · `Datasheet`. `Angle` radians CCW. `LineWidth` (custom stroke width) is
  present only when "use common line width for layer" is off. `AllLayers="Y"` places a signal
  shape on all signal layers. Points are offsets from the pattern center.
  Point counts: Line/Rectangle/Obround = 2; Arc = 3; Text = exactly 1 anchor;
  Polyline/Polygon = n.
  When a PCB footprint shape is bound to fields beyond this public name table, the serializer
  preserves numeric literals: `7` means Pattern and `20+n` means user/additional field index
  `n`. `Any Text` is literal decorative text and is not a wildcard for those fields.
- `Rectangle`/`FillRect`/`Obround`/`FillObround` use two opposite corners. Reconstruct all four
  before applying a component rotation. `Arc` uses start/middle/end on one circle and its bounds
  include cardinal extrema on the sweep. Stroke obstacles include half the effective layer line
  width.
- `TextWidth`/`TextHeight` are coordinate-space metrics for that exact shape's resolved text and
  complete font tuple. Do not reuse them for another `TextShow` value, component, or generated
  marking. Positive `FontWidth` and `FontSizeFloat` are internal font scalars, not root-unit
  lengths; see file 02 §2 and §8.
- A regular bound `TextShow` shape can suppress the corresponding generated component marking.
  It is shared through `PatternStyle`; moving a `<Component>` marking leaf will not relocate it.

### `<Hole>` (§5.1.18.1) — mounting hole

```xml
<Hole Id="1" Locked="Y" X="-7.1982" Y="1.3482" Diam="2" HoleDiam="1" Group="0"/>
```

`Diam` = keepout diameter, `HoleDiam` = drilled hole diameter; `X`/`Y` offset from center.

### `<Dimension>` (§5.1.19.1.1) and `<Model3D>` (§5.1.20)

- `<Dimension>` mirrors the PCB dimension (type, two points, dimension‑line origin, font),
  but its connection targets are footprint objects: `Connected1/2` = `None`/`Pad`/`Shape`/
  `Hole`/`Terminal`.
- `<Model3D>` describes the attached 3D model: `<Filename>`(`<Path>`/`<Var>`), `<Rotate>`
  (degrees), `<Offset>`, `<Zoom>`, plus `Type` = `File`/`IPC-7351`/`Outline`, model `Units`,
  and IPC offset/mirror flags.

## Cross‑reference cheat‑sheet

| Attribute / element | Points to |
|---|---|
| `<Pad Style>` | `<PadStyles>`→`<PadStyle Name>` (§3) |
| `<Pad>` `<Number>` | component symbol pin `<PadNumber>` (binds pad↔pin, file 30) |
| dimension `Connected*` | footprint `Pad`/`Shape`/`Hole`/`Terminal` |
| `Group` (pad/shape/hole) | pattern `<Groups>`→`<Group Id>` |
| `<Category Index>` | `<Categories>`→`<Category>` (§4) |
| `PatternStyle` (when nested) | the outer PCB/component file's reference to this footprint |

For any attribute/enum not shown, consult `DipTraceXML_PattEdit_En.pdf`.
