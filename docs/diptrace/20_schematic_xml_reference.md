# DipTrace XML — Schematic Reference

Dialect of the **Schematic Capture** program. Full spec: `DipTraceXML_Schematic_En.pdf`
(section numbers below). Read `02_diptrace_xml_conventions.md` first.

## Top‑level structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Source Type="DipTrace-Schematic" Version="4.3.0.x" Units="mm">
  <Library Type="DipTrace-ComponentLibrary" …>…</Library>   <!-- §3 component library, keyed by ComponentStyle -->
  <Schematic>                                                <!-- §4 the editable project -->
    …
  </Schematic>
</Source>
```

Plug‑in data node: **`/Source/Schematic`**. The embedded `<Library>` uses the CompEdit
dialect (file 30) and nests the pattern library inside it; each symbol gets a unique
`ComponentStyle` that placed parts reference. **Note:** on import DipTrace rebuilds each placed
`<Part>` from its library definition, so per‑instance values that diverge from the library can
be lost — see `02_diptrace_xml_conventions.md` §11.

A nested footprint Pattern may contain its own `<Dimensions><Dimension>` data. Those dimensions
travel with the pattern into Pattern Editor and PCB; they are not a top-level Schematic object
list. In a Schematic plug-in export they follow the `Patterns` setting, while the Schematic
`Dim` setting does not independently filter them.

## `<Schematic>` object catalog (§4)

| Element | § | What it is |
|---|---|---|
| `<SheetSettings>` → `<Sheets>`/`<Sheet>` | 4.1 | Per‑sheet page setup, zones, and 6 title blocks (BottomRight/BottomLeft/TopRight/TopLeft/ExtTopLeft/ExtBottomLeft). A placed object's `Sheet` is a **positional sheet index**; keep the list dense and in order. Stored `<Sheet Id>` is not used for this lookup. |
| `<Settings>` | 4.2 | Global: markings fonts + per‑field show/align, grid, origin, line widths (wire/bus/table/titles, node size), bus‑connection display, pin numbers, hide power/gnd, project dir. |
| `<ProjectLibs>` | 4.3 | Library folders/files. |
| `<DesignCache Count="…"/>` | 4.4 | How many leading components in the embedded library are design‑cache. |
| `<NetClasses>` → `<NetClass>` | 4.5 | Net classes (`Id`, `UpdateId`, `Type`). A net's `NetClass="N"` binds **by position** — the `Id` equals the index and is not used for lookup, so reordering the list silently reassigns classes. |
| `<ERC>` | 4.6 | ERC flags + power/gnd name templates. |
| `<Components>` → `<Part>` | 4.7 | Placed component **parts** (one entry per part/section). |
| `<Nets>` → `<Net>` | 4.8 | Nets, with pins and **wires**. |
| `<DifferentialPairs>` | 4.9 | Diff pairs (positive/negative net Ids). |
| `<Buses>` → `<Bus>` | 4.10 | Buses, their member nets, and bus wires. |
| `<BusConnectors>` → `<BusConnector>` | 4.11 | Bus connectors (ports). |
| `<Shapes>` → `<Shape>` | 4.12 | Free graphics & text (common plug‑in target). |
| `<Tables>` → `<Table>` | 4.13 | Free/BOM tables. |
| `<Simulator>` | 4.14 | SPICE simulation setup (type, signals, analysis params). |
| `<Groups>` → `<Group>` | 4.15 | Group registry (`Id`, `Enabled`, `Selected`). |

> In the Schematic dialect, **`Enabled="Y"/"N"`** is a first‑class attribute meaning
> *exists / removed from the schematic* on **nets, buses, bus connectors, shapes, tables,
> differential pairs, and groups** — **not** on wires. A plug‑in removes such an object by
> setting `Enabled="N"`. **Parts:** a normal export never writes `Enabled` on `<Part>`, but the
> plug‑in importer honors `Enabled="N"` there too — a plug‑in can delete a part this way.
> Wires carry no `Enabled` flag: remove a wire by dropping it from its net's `<Wires>` list
> (the wire list is subtree‑replaced when present — re‑list the survivors); remove a whole net
> (with all its wires) via `Enabled="N"` on the `<Net>`.

## Key objects for plug‑ins

### `<Part>` (§4.7.1) — placed component part/section

```xml
<Part Id="0" UpdateId="2221" BlockId="0" ComponentStyle="CompType229" ComponentPart="0"
      Sheet="4" X="83.82" Y="-43.815" Angle="4.7124" HorzFlip="N" VertFlip="N"
      ShowNumbers="Common" Group="-1" Selected="N" Locked="N">
  <RefDes>C1</RefDes> <PartRefDes>1</PartRefDes> <PartName>Part 1</PartName>
  <Value>(1608)</Value> <Name>CAP_1608(0603)</Name>
  <Pins> <Pin NetId="-1" NotConnected="N"/> … </Pins>
  <RefDesMarking …/> <NameMarking …/> <ValueMarking …/> …
</Part>
```

- One `<Part>` = one **part/section** of a multi‑part component; several parts share a
  `RefDes`. `ComponentStyle` → a symbol in the embedded library; `ComponentPart` = which part
  within it. `Sheet` → positional index in `<Sheets>` (not stored `<Sheet Id>`). `Angle`
  radians CCW.
- **`<Pins>`** lists the part's pins *in symbol pin order*; each `<Pin NetId="…" NotConnected="…"/>`
  says which net (Id) that pin connects to (`-1` = none). Nets reference pins **by this
  positional index** (see below).

### Net ports are library-typed placed parts

A placed net port is **not** a separate top-level XML object, and its placed `<Part>` does not
carry `PartType="Net Port"`. Resolve it through the embedded component library:

```xml
<Library Type="DipTrace-ComponentLibrary">
  <Components>
    <Component ComponentStyle="CompType7" Id="7">
      <Part Id="0" PartType="Net Port"> … </Part>
    </Component>
  </Components>
</Library>

<Schematic>
  <Components>
    <Part Id="42" ComponentStyle="CompType7" ComponentPart="0" …>
      <Name>GND</Name>
      <Pins><Pin NetId="3" NotConnected="N"/></Pins>
    </Part>
  </Components>
  <Nets>
    <Net Id="3" …>
      <Name>Net 3</Name>
      <Pins><Item Part="42" Pin="0"/></Pins>
    </Net>
  </Nets>
</Schematic>
```

Resolution steps:

1. Match placed `Part@ComponentStyle` to
   `/Source/Library/Components/Component@ComponentStyle`.
2. Match placed `Part@ComponentPart` to the library component's `Part@Id`.
3. Treat the placed part as a net port when that library part has
   `PartType="Net Port"`.
4. The **net-port name is the placed part's `<Name>`** — not its `RefDes`, `Value`, or the
   library component's name.
5. Find its connected nets either from placed `<Pins><Pin NetId="…">` or from each net's
   mirror `<Pins><Item Part="…" Pin="…">`. `Pin` is the positional index in the placed part's
   `<Pins>` list.

For a multi-pin net port, DipTrace's connect-by-name region key also includes the corresponding
library pin's `<Name>`; equal placed-port names do not collapse unlike pins of the same
multi-pin port into one region.

### `<Net>` (§4.8.1) with `<Wire>`

```xml
<Net Id="0" NetClass="0" Global="N" CustomColor="Y" WireColor="0" Locked="N" Enabled="Y">
  <Name>AP-WAKE-BT</Name>
  <Pins><Item Part="596" Pin="0"/> … </Pins>          <!-- part Id + pin index in that part -->
  <Wires>
    <Wire Id="0" Sheet="1"
          Connected1="Pin" Bus1="-1" Object1="709" SubObject1="0"
          Connected2="Pin" Bus2="-1" Object2="347" SubObject2="0"
          Arrows="None" Group="-1" Selected="N">
      <Points><Point X="-1.27" Y="-13.97" Dir="-1"/> … </Points>
    </Wire>
  </Wires>
</Net>
```

The **wire connection model** (per endpoint 1 and 2):

| Field | Meaning by `ConnectedN` |
|---|---|
| `ConnectedN` | `Pin` · `Wire` · `Bus` · `Free`. |
| `BusN` | connected bus `Id` when `Connected="Bus"`, else `-1`. |
| `ObjectN` | `Pin`→part `Id` (§4.7); `Wire`→another wire `Id` in the same net; `Bus`→bus‑wire `Id`. |
| `SubObjectN` | `Pin`→pin index in the part; `Wire`/`Bus`→point index in that wire's `<Points>`. |

- `<Point>` `Dir`: `-1` unset, `0` horizontal, `1` vertical — **stored on the segment's second
  point** (first point's `Dir` ignored). Points are listed in connection order.
- Schematic Y is commonly negative downward in stored coordinates — keep values as read; do
  not flip.

#### What "selected net" means

`<Net>` has no `Selected` attribute. For Schematic plug-in export, `Net=Selected` means a net
that contains at least one `<Wire Selected="Y">` (`TNet.line.selected`). A bus is selected by
the same rule over its own wires (`TBus.line.selected`). `Diff=Selected` means a differential
pair whose positive or negative member net contains a selected wire.

These are **parent-scope tests**: once a net or bus qualifies, the exporter writes the whole
parent and all of its wires. If the operation is custom work on individual wires, inspect each
`Wire@Selected` rather than treating every wire in the exported parent as selected.

> **Import warning:** with `ImpMode=Edit` and `Net=Selected`, the importer rebuilds a returned
> net's `<Wires>` list from only the incoming wires marked `Selected="Y"`. This can remove
> unselected wires. For a plug-in that merely offers a "selected nets only" option, use
> `Net=All`, test `Wire@Selected` inside the executable, return only changed `<Net>` records,
> and omit `<Wires>` (and `<Pins>` when not changing connectivity).

### `<Bus>` (§4.10) and `<BusConnector>` (§4.11)

- `<Bus Id Enabled Locked>` holds `<Nets>` (`<Net NetId="…" ConnectionNumber="…"/>`, member
  nets with their position in the bus) and `<Wires>` (`<Wire>` with the same connection model
  but endpoints of type `Bus Wire` / `Bus Connector` / `Free`).
- `<BusConnector Id Sheet X Y Enabled Connected Group Selected Locked>` with a `<Name>` — the
  named port that joins a bus to nets.

### `<Shape>` (§4.12.1) — free graphics & text

```xml
<Shape Enabled="Y" Id="0" Type="Rectangle" Sheet="0" LineWidth="0.3333" Color="9079434"
       NetId="-1" BusId="-1" Angle="0" HorzAlign="Left" VertAlign="Top" TextAlign="Left"
       FontVector="Y" FontSize="10" FontWidth="-2" FontScale="1" FontColor="12632256"
       LineSpacing="1.2" Group="-1" Selected="N" Locked="N">
  <Points><Point X="86.995" Y="21.59"/> … </Points>
  <FontName>Tahoma</FontName>                          <!-- if TrueType -->
  <TextLines><TextLine>Power</TextLine></TextLines>    <!-- if Type="Text" -->
</Shape>
```

- **`Type`**: `Line` · `Arc` · `Rectangle` · `FillRect` · `Obround` · `FillObround` ·
  `Polyline` · `Polygon` · `Text`.
- `Sheet` → positional index in `<Sheets>` (not stored `<Sheet Id>`). `Color` and `FontColor`
  are integer colors. A text shape can be bound
  to a net/bus via `NetId`/`BusId` (net‑name / bus label), else `-1`.
- Remove/replace from a plug‑in: set `Enabled="N"` and append new `<Shape Enabled="Y"
  Selected="Y">`.

### Hierarchical schematics (blocks & sheets)

DipTrace links **block instances** to **child sheets** by a **`BlockId`**, never by the sheet's
positional `<Id>`:

- A **child sheet** is a `<Sheet>` with **`Type="1"`** and a non‑zero, project‑unique **`BlockId`**
  (`BlockId` is written only for `Type<>0` sheets — a `Type="0"` sheet cannot be a block target).
- A **block instance** is a `<Part>` on the *parent* sheet carrying **`BlockId` = the child sheet's
  `BlockId`**. Whether a part is a hierarchy block/connector comes from the **library element** it
  references, **not** from an attribute you add — you cannot turn an ordinary part into a block by
  setting `BlockId`; it must reference a hierarchy‑block library element.
- Each block pin corresponds to a **hierarchy‑connector** part living **on the child sheet**; a pin
  binds to its connector only when that connector is on the block's referenced sheet.
- **Rules:** link block↔sheet **only** through `BlockId` (the `<Sheet Id>` is positional and ignored
  on read; a part's `Sheet="…"` is a positional sheet index — keep sheets dense/in order). **Never
  duplicate a `BlockId`** across sheets, and don't rely on the name fallback: if `BlockId` fails to
  resolve, DipTrace silently rebinds by matching the block‑instance **name** to a sheet name, so a
  name collision can misroute the block.

## Cross‑reference cheat‑sheet

| Attribute | Points to |
|---|---|
| `Sheet` | positional index in `<Sheets>`; stored `<Sheet Id>` is ignored for this lookup |
| net `<Item Part Pin>` | `<Part Id>` + pin **index** in that part's `<Pins>` (§4.7.1.14) |
| wire `ObjectN`/`SubObjectN` | depends on `ConnectedN` (table above) |
| `NetId` / `BusId` | `<Net Id>` (§4.8) / `<Bus Id>` (§4.10), `-1` = none |
| `NetClass` | `<NetClass Id>` (§4.5) |
| `ComponentStyle` + `ComponentPart` | `<Library>/<Components>/<Component ComponentStyle>` + its `<Part Id>` |
| `Group` | `<Groups>`→`<Group Id>` (§4.15), `-1` = none |
| `UpdateId` | link to the PCB component (for update) |

For anything not shown here, consult `DipTraceXML_Schematic_En.pdf`.
