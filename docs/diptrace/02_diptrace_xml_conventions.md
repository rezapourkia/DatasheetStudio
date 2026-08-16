# DipTrace XML — Conventions Shared by All Four Dialects

Rules that hold across PCB, Schematic, CompEdit, and PattEdit XML. Read this once; the
per‑program reference files assume it.

## 1. File shell

Always UTF‑8:

```xml
<?xml version="1.0" encoding="UTF-8"?>
```

The root element is one of:

- **`<Source Type="DipTrace-PCB" Version="4.3.0.x" Units="inch">`** … project file (PCB).
- **`<Source Type="DipTrace-Schematic" Version="…" Units="…">`** … project file (Schematic).
- **`<Library Type="DipTrace-ComponentLibrary" Name="…" Hint="…" Version="5.x" UID32="…" Units="…">`** … component library (`.eli`/`.elixml`).
- **`<Library Type="DipTrace-PatternLibrary" Name="…" Hint="…" Version="5.x" UID32="…" Units="…">`** … pattern library (`.lib`).

PCB and Schematic `<Source>` files embed a `<Library>` section — the design‑cache component
library, which **nests the pattern library inside it** — before the editable
`<Board>` / `<Schematic>` node. `UID32` is a stable unique library identifier.

## 2. Units

`Units` on the root = `mm` | `inch` | `mil`. **Coordinates and ordinary geometry lengths are
expressed in these units.** There is no per‑object unit override (a few
`Dimension`/`Table` objects have their own display `Units="Common|inch|mil|mm"`, but that only
affects the text shown, not the stored geometry).

Font scalars are the important exception. `FontSizeFloat` and a positive `FontWidth` are
DipTrace font/internal values, not ordinary project lengths. Do not multiply them by the root
unit conversion. Serialized `TextWidth`/`TextHeight`, however, are coordinate-space extents in
the root units.

When a compatible font engine needs to convert one of those internal font scalars to a project
coordinate length, the scale is:

| Root units | Coordinate length for internal value `v` |
|---|---|
| `mm` | `v / 3` |
| `inch` | `v / 76.2` |
| `mil` | `v * 1000 / 76.2` |

This scale alone does not reproduce glyph metrics; vector glyph data, stroke presets, mono/scale
settings, or the selected TrueType engine still matter.

## 3. Value types & formatting

| Type | Encoding |
|---|---|
| **Bool** | `"Y"` / `"N"` (occasionally `"+"`/`"-"` in the Schematic simulator block). |
| **Int** | plain integer. |
| **Real** | decimal with a **dot** separator. Write dots — the canonical form, and what other tools reading the file expect. (DipTrace's own reader normalizes both `.` and `,` to the machine's separator, so it reads either — don't rely on that leniency.) Parse defensively (older/locale exports can contain commas). |
| **Text** | string attribute or element text. |
| **Color** | 24‑bit integer in Windows/Delphi `TColor` order `0x00BBGGRR`. E.g. `255` = red, `16711680` = blue, `65535` = yellow. |
| **Angle** | radians unless stated otherwise — see §5. |

> **Defaults are omitted.** Every spec states: *"With the default value, some parameters are
> not written to the file."* So a missing attribute means *use the default*, **not** *zero*.
> When editing in place, don't assume an attribute exists; when writing, you may omit
> attributes left at their defaults.

## 4. Coordinate frames

Two frames appear, depending on the object:

- **Project/sheet frame** — PCB board objects and Schematic sheet objects (components, nets,
  traces/wires, shapes, tables, dimensions) use absolute board/sheet coordinates.
- **Object‑center frame** — everything *inside a library symbol or footprint* (pins, pads,
  shapes, holes, dimensions, origin) is stored as an **offset from that object's center
  `(0,0)`**. The spec phrases this as "the X/Y distance from the symbol/pattern center
  coordinate (0;0) to the … coordinate."

Do **not** assume a Y‑axis flip or re‑origin. Whatever frame you read a coordinate in, write
the result back in the same frame. Placed PCB components require the three separate laws below;
do not combine them into one generic `Side`/`Flip` transform.

### 4.1 PCB embedded-footprint geometry

The PCB exchange `<Library>` contains an **exchange-time `PatternStyle` variant**, not
necessarily the untouched source-library footprint. User `Flip`/`HorzFlip` geometry can already
be baked into its pads, shapes, holes, terminals, and offsets. The exporter removes only the
component-side X reflection before serializing that embedded pattern.

For an embedded-pattern point `(px, py)` and placed component `(X, Y, Angle=A)`:

```text
if Component@Side == "Bottom": px = -px
bx = X + px*cos(A) - py*sin(A)
by = Y + px*sin(A) + py*cos(A)
```

Do **not** apply `Component@Flip` or `Component@HorzFlip` again. Doing so double-transforms the
already specialized `PatternStyle`. Fail closed if the referenced `PatternStyle` or `PadStyle`
cannot be resolved.

### 4.2 PCB component-marking fields

`<RefDesMarking>/<Silk>` and the other component marking leaves are placed-instance fields, not
ordinary embedded-pattern geometry. Never mirror their `X/Y/Angle` using `Side`, `Flip`, or
`HorzFlip`.

Read `/Source/Board/Settings/Markings/CompRotate` as a child element containing `Y` or `N`.
For marking offset `(mx,my)` and local angle `ma`:

```text
CompRotate=Y:
  boardPoint = componentOrigin + R(Component@Angle) * (mx,my)
  boardAngle = Component@Angle + ma
  write mx,my = R(-Component@Angle) * (boardPoint-componentOrigin)
  write ma    = boardAngle-Component@Angle

CompRotate=N:
  boardPoint = componentOrigin + (mx,my)
  boardAngle = ma
  write mx,my = boardPoint-componentOrigin
  write ma    = boardAngle
```

Thus a readability rule such as “world angle 0 or π/2” must be enforced in board space and then
converted back with the appropriate inverse.

These formulas describe a stored **effective `Position`** pose. Resolve local `Align="Common"`
through the corresponding global marking setting first: local `Common` plus global `Position` is
still a user-positioned marking, while local `Common` plus global `Auto` is still automatic. Do not
read the serialized `X/Y/Angle` of an effective `Auto` marking as its rendered pose; DipTrace
recomputes that pose.

Exact Auto reconstruction is stateful. For Silk and Assy independently, DipTrace processes all
non-Auto fields first and then all Auto fields, in this order within each pass: RefDes, Name, Value,
Pattern, Manufacturer, Datasheet, then additional fields. A field hidden after `Show=Common`
resolution, or suppressed by a matching author-owned footprint text shape, does not enter the
sequence. A shown field with an empty resolved string **does** enter it and can change every later
Auto position. Preserve this distinction in parsers and fixtures.

The component bounds used by Auto also depend on `CompRotate`:

- with `Y`, the host uses its ordinary component width/height and rotates the marking with the
  component;
- with `N`, the host uses angle-aware `contw/conth` and the rendered marking offset remains aligned
  to board axes.

`contw/conth` are not generally `Pattern Width/Height` rotated as one bounding rectangle. The host
builds them from origin-seeded component geometry, its fiducial-display policy, non-text shapes
(including true arc bounds), and enabled holes. At non-orthogonal angles or for asymmetric/offset
footprints, rotating the already-bounded pattern box can overstate the result. A plug-in requiring
render parity must reconstruct equivalent bounds from the exported geometry and verify them against
the target DipTrace build; a conservative approximation must be documented as such.

### 4.3 PCB layer side versus pad mask/paste side

Pattern shape layers are canonical/local: map `Top` ↔ `Bottom` layer names when a component is
on `Side="Bottom"`. A surface `Pad@Side` is also footprint-local:

| Component side | Footprint `Pad@Side` | Physical copper side |
|---|---|---|
| Top | Top or missing | Top |
| Top | Bottom | Bottom |
| Bottom | Top or missing | Bottom |
| Bottom | Bottom | Top |

A Through pad belongs to both physical surfaces regardless of `Pad@Side`.

Pad `<MaskPaste>` sides are canonical in the pad's own frame, not absolute board sides.
`TopMask`/`TopPaste` and `TopSegments` describe the pad's own (near) face;
`BotMask`/`BotPaste` and `BotSegments` describe its opposite (far) face. Resolve the pad's own
physical side from the table above (`Component@Side` combined with footprint-local `Pad@Side`).
For a queried physical side, use the `Top*` state when it equals that own physical side and the
`Bot*` state otherwise. The exporter normalizes sided pad styles before writing them; treating the
attribute names as physical Top/Bottom swaps asymmetric mask or paste states on bottom components.

## 5. Angles & orientation

- **Rotation angles are in radians, counter‑clockwise** — for placed components/parts
  (`Angle`), pads, shapes, and dimensions. Example: a part at `Angle="4.7124"` is rotated
  270° (≈ 3π/2).
- **`Orientation` and `Side`** are discrete **text enums**, not radians:
  - `Orientation` = `"0"|"90"|"180"|"270"` — used for **schematic‑symbol pin rotation**,
    pattern creation‑template metadata, and tables. A symbol pin has **no** radian `Angle`; it
    rotates only in 90° steps via `Orientation`.
  - `Side` = `"Top"|"Bottom"`.
- The **3D‑model `<Rotate>`** angles are in **degrees**. (The `<Origin>` element carries only
  `X`/`Y` — plus, for patterns, display flags — and has **no** angle attribute.)
- Pattern `Orientation` "does not recompute coordinates" — it's editing metadata for the
  creation template, not an applied transform.

## 6. IDs and cross‑references

DipTrace XML is a **flat set of lists joined by integer IDs**, not a deep tree.

- Most list elements carry an **`Id`** (or `Index`/`Number`) attribute. That value is what
  other objects reference — **not** the element's position, although for many lists the two
  coincide.
- A reference of **`-1`** means "none / not connected / does not belong."
- Typical references (PCB): a `Net` pad is `<Item Comp="…" Pad="…"/>` → component `Id` + that
  component's pad `Id`; a copper layer's `NetId`, a shape's `NetId`/`LayId`, a via's `ViaStyle`
  → `ViaStyle Id`, an object's `Group` → `<Group Id>`.
- Typical references (Schematic): a net `<Item Part="…" Pin="…"/>`, a wire's
  `Connected1/Object1/SubObject1` triple (see the Schematic reference), a part's
  `ComponentStyle` → a component in the embedded library, `NetClass` → net class `Id`.
- Library links: a component `Part` attaches a footprint via `<Pattern Style="PatType0"/>`
  matching a `PatternStyle` in the embedded pattern library; a symbol `Pin`'s `PadNumber`
  must equal a pattern `Pad`'s `Number` to bind pin↔pad.

**Assigning `Id`s — depends on what you are doing:**

| Situation | Rule |
|---|---|
| Editing an existing top‑level object (plug‑in `Edit`) | **Keep its original `Id`.** |
| Adding a new top‑level object (plug‑in `Edit`) | Normally **omit `Id`** — DipTrace appends it and assigns identity. Never compute "max Id + 1" over a partial subset: the value may collide with an unexported object and overwrite it. |
| New object that other new objects must reference in the same exchange | `Group` supports a next-free visible `Id`. A verified PCB exception is creation of a net plus pad `NetId` references when **both** `Net=All` and `Comp=All` expose the complete namespace (file 50). Otherwise prefer a two-step flow (add, re-export, then link). |
| Generating a **full file** from scratch | Every top‑level array must be **dense, ascending from `Id`=0, position == Id** — the full‑file reader binds references positionally (see the dialect files). |
| Nested objects (pads in a component, points in a shape…) | Follow the container's own convention in the dialect file; do not renumber existing members. |

When you **remove** an object, prefer disabling it (`Enabled="N"`) so existing references
stay valid.

## 7. Object state flags (common attributes)

Most editable objects share these:

- **`Selected`** `Y`/`N` — user selection. New objects a plug‑in adds should be `Selected="Y"`.
- **`Locked`** `Y`/`N` — edit lock.
- **`Group`** `Int` — group `Id`, or `-1` for none; groups are listed in a `<Groups>` section.
- **`Enabled`** `Y`/`N` — *exists / removed*. A genuine serialized attribute in the Schematic
  dialect on **nets, buses, bus connectors, shapes, tables, differential pairs, and groups**
  (not on wires; parts don't get it in a normal export, but the plug‑in importer honors
  `Enabled="N"` on `<Part>` too). The plug‑in exchange importer also honors `Enabled="N"` on the
  editable PCB objects (components, nets, shapes, dimensions, tables, …) as the "delete this"
  flag — even where the public PDF spec doesn't list it in the object's attribute table.
  Absent = enabled.
- **`PanelExclude`** `Y`/`N` — "Do Not Panelize" (PCB).

## 8. Text, fonts, and multi‑line strings

- A text object stores its lines as a list: `<TextLines><TextLine>…</TextLine>…</TextLines>`.
- **`FontVector`** `Y`/`N` selects the built‑in **vector (stroke) font** vs a **TrueType**
  font. `FontName` names the TrueType face.
- **Vector line‑width codes** (`FontWidth` / `FontLineWidth`): `-3` = thin, `-2` = normal,
  `-1` = bold, **`>0` = an explicit internal font-width scalar** (convert with §2 only when
  producing coordinate geometry).
- **`FontSize`** is the legacy integer form of DipTrace's font-size scalar; newer formats also
  carry the real `FontSizeFloat`. These are not ordinary project lengths or portable typographic
  point sizes. `FontScale` is a horizontal scale factor; `LineSpacing` multiplies line pitch.
- **Anchoring:** `HorzAlign`/`VertAlign` (`Center|Left|Right` and `Center|Top|Bottom`) set the
  anchor point of the text/picture; `TextAlign` (`Center|Left|Right`) aligns lines within a
  multi‑line block.
- Some text objects have a **`TextShow`** enum selecting a bound field rather than literal
  text (e.g. `Name`, `RefDes`, `Value`, `Manufacturer`, `Datasheet`, `Any Text`, or title‑block
  `Text`/`Sheet`/`File`). In PCB footprint text, values beyond the named table serialize as
  numeric strings: `7` = Pattern and `20+n` = user/additional field index `n`. `Any Text` is
  unbound literal text, not a wildcard suppression token.
- Text and picture-like shapes share anchor/alignment concepts but not necessarily their extent
  attribute names. PCB Text uses `TextWidth`/`TextHeight`; PCB Picture and vector QR
  (`Type="10"`) use `PictureWidth`/`PictureHeight`.
- `TextWidth`/`TextHeight` describe the **specific serialized text shape** after its literal or
  bound value and font were resolved. They may be reused only when the actual displayed text,
  `TextShow`, and the full font tuple (`FontVector`, `FontMono`, `FontName`, size, width, scale,
  line spacing) match. They are not generic metrics for another component marking.
- Generated PCB component markings do not serialize their computed text rectangle in the
  marking leaf. Exact reconstruction requires DipTrace's vector glyph table or equivalent
  TrueType/Win32 measurement. A plug-in without matching metrics must use a proven conservative
  envelope or fail closed; an optimistic estimate can place text on copper.
- For a conservative vector-font height envelope, the renderer's stroke scalar is
  `fsize/12` (thin `-3`), `fsize/8.5` (normal `-2`), `fsize/6` (bold `-1`), or the positive
  `FontWidth` value. In millimetres the single-line full height is approximately
  `(1.3627*fsize + stroke)/3`; retain a safety margin. For multiple lines, add
  `(1.3627*fsize/2.45 + stroke)*(LineSpacing+1)/3` for each additional line. This law does not
  apply to TrueType; exact TrueType bounds remain font/GDI dependent.

### Source-independent marking measurement strategy

Use the first applicable method:

1. **Exact-context serialized metric.** Reuse `TextWidth`/`TextHeight` only from a shape whose
   resolved displayed text, `TextShow`, pattern/component context, and complete font tuple match.
2. **Calibrated vector envelope.** Use the height law above and a width model calibrated against
   exported shapes from the target DipTrace build/font settings. Include wide glyphs (`M`, `W`,
   `@`, digits), spaces, multiline, non-ASCII used by the design, and the actual strings being
   placed. Inflate by a documented error bound established from those fixtures.
3. **Calibrated TrueType/GDI measurement.** Measure the exact installed face with a Unicode Win32
   text API, then calibrate DipTrace's font scalar→GDI size mapping against exported shapes.
   Detect font substitution/missing faces; do not silently measure a fallback font.
4. **Fail closed.** If no measurement has a proven non-optimistic error bound, do not perform an
   obstacle-sensitive placement for that marking.

A character-count multiplier or a convenient safety factor is an engineering heuristic, not a
universal guarantee. Put the measurement method/version and calibration identity in the cache key,
test wide/multiline/missing-font fixtures, and expose the added margin in the plug-in's contract.
For PCB collision work, the serialized/layout metric cell and the visible glyph envelope are
different objects. The verified orthogonal vector-label profile, anchor reconstruction, safe
fallbacks, and final conflict-repair contract are in
[`12_pcb_text_geometry.md`](12_pcb_text_geometry.md).

## 9. Segment parameters live on the *second* point

For a **PCB trace** and a **Schematic wire**, a poly‑line is a `<Points>` list. The attributes
of each *segment* (layer, width, via, arc flag, meander, segment orientation `Dir`, …) are
stored on the segment's **end (second) point**. The very first point's non‑geometry
attributes are ignored (only its `Id`, `X`, `Y` matter). When you split, extend, or rebuild a
trace/wire, put per‑segment data on the correct end point.

## 10. File references (paths)

Anything that points at an external file — libraries, pictures, 3D models — is stored as a
pair:

```xml
<Path>C:\Program Files\DipTrace\Lib\buzzers.lib</Path>
<Var>%standardlibs%\buzzers.lib</Var>
```

`<Path>` is the resolved absolute path; `<Var>` is the same path expressed with a DipTrace
environment variable (e.g. `%maindir%`, `%standardlibs%`, `%pictures%`) when applicable.
Preserve both.

## 11. What the XML leaves out (recomputed or internal)

The XML is not a full dump of DipTrace's in‑memory state. A few things a plug‑in should not
expect to find or be able to set:

- **Via geometry is recomputed, not stored.** A trace/segment point that carries a via
  serializes only its **`ViaStyle`** (the via‑style `Id`); the concrete via diameter/hole/layer
  span is rebuilt from that style on import. To change a via, point it at a different
  `ViaStyle`, don't try to write per‑via dimensions.
- **Footprint geometry is stored once and referenced.** In PCB, Schematic, and `.eli` files a
  footprint's pads/shapes are written a single time in the (nested) pattern library and
  referenced by `PatternStyle`; a component/part stores only that reference (plus
  `<InternalConnections>`). The same `<Pad>`/`<Shape>` footprint markup therefore appears
  identically across all four programs.
- **Placed schematic instances are rebuilt from the library on import.** Structural fields are
  re‑derived correctly, but per‑instance values that *diverge* from the library definition can
  be lost. If a schematic plug‑in must change such a value, be aware the round‑trip may not
  preserve an instance‑level override.
- **Internal editing/undo state is binary‑only.** DipTrace's native binary files double as its
  undo buffer, so transient edit/route state never appears in the XML. Anything not in the XML
  spec simply isn't exchanged.

## 12. Cross‑dialect quick map

| Concept | PCB root/section | Schematic | CompEdit | PattEdit |
|---|---|---|---|---|
| Root | `<Source DipTrace-PCB>` | `<Source DipTrace-Schematic>` | `<Library ComponentLibrary>` | `<Library PatternLibrary>` |
| Editable data node | `<Board>` | `<Schematic>` | `<Components>` | `<Patterns>` |
| Placed device | `<Component>` | `<Part>` | `<Component>`→`<Part>` (definition) | `<Pattern>` (definition) |
| Connectivity | `<Nets>` + traces | `<Nets>` + wires, `<Buses>` | — | — |
| Graphics | `<Shapes>` | `<Shapes>` | part `<Shapes>` | pattern `<Shapes>` |
| Grouping | `<Groups>` | `<Groups>` | part `<Groups>` | pattern `<Groups>` |

See the per‑program files for the full object catalog and the exact attributes.
