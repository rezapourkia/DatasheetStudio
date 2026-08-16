# PCB Text Geometry: Font Cells, Visible Ink, and Safe Placement

Use this chapter when a PCB plug-in measures, moves, rotates, collides, or contains text. Read
[`02_diptrace_xml_conventions.md`](02_diptrace_xml_conventions.md), especially its font and
transform sections, first.

The central rule is:

> DipTrace XML can describe a text layout cell, but it does not serialize a universal tight
> rectangle around the visible glyph strokes. Keep the layout cell and any calibrated visible-ink
> estimate as separate geometry.

## 1. Keep four text geometries separate

A robust text plug-in normally needs four related, but different, objects:

| Geometry | Meaning | Typical use |
|---|---|---|
| Metric cell | Unrotated width and height resolved for the exact string/font context | Anchor reconstruction and alignment |
| Full placed cell | Metric cell rotated and translated into board coordinates | Broad phase, pads/mask/body checks, outline containment |
| Visible-ink estimate | Calibrated conservative envelope for the strokes that are actually printed | Text/text readability and an explicitly soft via policy |
| Clearance envelope | Full cell or visible estimate expanded by a declared clearance | The final predicate for one obstacle class |

Do not overwrite the full cell with a trimmed box. If trimming happens before anchor reconstruction,
the center moves for left/right/top/bottom anchors and every later transform is wrong.

Do not call the visible-ink estimate “exact” unless it comes from an exact renderer for the same
font face, string, size, width, scale, line spacing, and DipTrace build. A screenshot-derived or
fixture-derived profile is a calibrated policy.

## 2. What PCB XML provides

### Free and footprint text shapes

A PCB `<Shape Type="Text">` has:

- one anchor `<Point X="..." Y="..."/>`;
- `Angle` in radians;
- horizontal and vertical anchor/alignment fields;
- the exact resolved text and font context for that shape;
- `TextWidth` and `TextHeight`.

Treat `TextWidth`/`TextHeight` as the layout-cell extents of that serialized shape. They are not a
tight visible-glyph box and must not be scaled by the font settings a second time.

For a free/footprint Shape, normalize `HorzAlign`/`VertAlign` to the `Horz`/`Vert` names used below.
For a generated marking leaf, use its `Horz`/`Vert` fields directly.

Picture and vector QR objects are not Text. They use `PictureWidth`/`PictureHeight`.

### Generated component markings

`<RefDesMarking>`, `<NameMarking>`, and the other generated marking leaves do not contain their
computed width and height. Resolve:

1. the displayed field value;
2. effective `Show` and `Align` after resolving local `Common` through project globals;
3. global versus component-specific marking font settings;
4. vector versus TrueType mode and the complete font tuple;
5. `CompRotate`, the marking transform, and any Auto-position state;
6. a matching metric method from file 02.

Do not borrow a rectangle merely because another shape has the same `TextShow`. The resolved
string, pattern/component context, and full font tuple must match.

An effective `Auto` marking has no independently usable serialized pose. Reproduce the ordered
host state machine described in file 02 §4.2, including non-Auto-before-Auto processing and shown
empty fields. For `CompRotate=N`, use equivalent angle-aware component bounds and board-axis Auto
offsets; rotating an unrotated `Pattern Width/Height` AABB is not render-equivalent for general
footprints. Keep effective `Position` distinct: local `Common` plus global `Position` still means
the stored anchor is authoritative and should survive a geometric no-op.

For a source-independent resolver, the currently verified host sequence can be expressed as this
pseudocode. The sequence counter is shared by the non-Auto and Auto passes; it is not reset between
them.

```text
sequence = -1
previous = none
for field in (all effective non-Auto fields, then all effective Auto fields):
    # each pass uses RefDes, Name, Value, Pattern, Manufacturer, Datasheet, user fields
    if field is hidden after Show resolution or suppressed by author footprint text:
        continue
    sequence += 1                 # a shown empty string reaches this line
    resolve field alignment; update previous
```

For an Auto field at `sequence == 0`, choose Left only when component height is greater than width
and the raw measured text width is greater than component width; otherwise choose Top. At
`sequence == 1`, choose the opposite of the previous effective alignment:

| Previous | Auto successor |
|---|---|
| Center or Top | Bottom |
| Bottom | Top |
| Left | Right |
| Right | Left |
| Corner | Bottom |
| Position | use the stored pose: for `cos(angle) < 0.7`, Left when `X > 0`, otherwise Right; else Top when `Y < 0`, otherwise Bottom |

The strict comparisons matter: a stored Position with `Y == 0` takes the Bottom successor. On a
bottom-side component, Left and Right are swapped before the corresponding pose is built.

For later Auto fields (`sequence > 1`), let `th` be the raw measured text height. The exported-XML
overflow anchor is `(+cw/2 + th/3, +ch/2 - 1.5*th*(sequence-2))` on a top-side component, with
`Horz=Left`, `Vert=Top`, angle 0. On a bottom-side component the X term is
`-cw/2 - th/3` and `Horz=Right`; Y, vertical anchor, and angle are unchanged.

Let `cw/ch` be the host component dimensions selected by `CompRotate`, in the marking frame. The
verified exported-XML anchors for the named alignments are:

| Alignment | Anchor `(X,Y)` | `Horz`, `Vert` | Local angle |
|---|---|---|---|
| Center | `(0,0)` | Center, Center | `π/2` when `ch > cw`, otherwise `0` |
| Top | `(0,+ch/2)` | Center, Bottom | `0` |
| Bottom | `(0,-ch/2)` | Center, Top | `0` |
| Left | `(-cw/2,0)` | Center, Bottom | `+π/2` |
| Right | `(+cw/2,0)` | Center, Bottom | `-π/2` |
| Corner | `(+cw/2,+ch/2)` on top side; mirrored X on bottom | Left, Bottom on top side; Right, Bottom on bottom | `0` |

Reconstruct the visible/full-cell center from these anchors using §3, then apply the marking
transform from file 02. Do not copy Delphi's internal Y-down constants directly into exported XML;
the exporter mirrors Y.

### Bound footprint text is a third mechanism

An author-owned `PatternStyle` text shape bound through `TextShow` is shared footprint geometry.
It may suppress a generated marking, but changing the component marking leaf does not relocate that
shared shape per instance. Classify the text mechanism before measuring or editing it.

## 3. Reconstruct the full cell from the anchor

Let the serialized anchor be `A=(x,y)`, the unrotated metric cell be `w` by `h`, and the local text
angle be `a`. First choose the center offset in the unrotated text frame:

```text
dx =  0       for Horz=Center
dx = -w/2     for Horz=Right
dx = +w/2     for Horz=Left (legacy PCB XML may serialize Left as "-1")

dy =  0       for Vert=Center
dy = +h/2     for Vert=Bottom
dy = -h/2     for Vert=Top
```

Then:

```text
C = A + R(a) * (dx, dy)
```

where `R(a)` is the ordinary two-dimensional rotation. Apply the correct component-marking or
footprint transform only after this local center is known.

For a placed rectangle centered at `C` with board-space angle `a`, an axis-aligned broad-phase box
has half-extents:

```text
ex = |cos(a)| * w/2 + |sin(a)| * h/2
ey = |sin(a)| * w/2 + |cos(a)| * h/2
```

This AABB is conservative for the rotated layout cell. For an exact oriented-rectangle predicate,
keep the four rotated corners too.

## 4. The orange rectangle is not the visible glyph box

Live PCB screenshots and exported geometry show that DipTrace's displayed text rectangle includes
font-cell padding perpendicular to the reading/baseline direction. On the calibrated vector RefDes
samples:

- visible strokes occupied about 94–95% of the cell along the baseline;
- visible strokes occupied about 60–67% across the baseline.

Therefore:

- do **not** trim the leading and trailing ends of a RefDes;
- a controlled amount of cross-axis cell overlap can still leave the strokes readable;
- the same constant must not be applied blindly to another font or string class.

This distinction fixes two opposite failure modes:

- using the full cell for every text/text test moves many labels that are already readable;
- trimming all four edges lets the leading/trailing glyphs collide.

## 5. Verified orthogonal vector-label profile

The following profile was validated for single-line PCB labels whose trimmed text matches
`[A-Z0-9]+`, uses the DipTrace vector font, and is placed at an orthogonal angle. It is suitable for
ordinary uppercase/digit RefDes labels. The v1 profile used a 0.5-degree orthogonal tolerance. It
is **not** a universal DipTrace font law.

Use the full cell if any of these is true:

- TrueType is selected;
- the text is multiline;
- the text contains lowercase, spaces, punctuation, underscore, overline markup, accented text, or
  other Unicode;
- the angle is not within the plug-in's documented orthogonal tolerance;
- the required font context is missing, substituted, or otherwise unverified.

### Parallel text/text collision

For two horizontal labels, use X as the baseline axis and Y as the cross axis. For two vertical
labels, swap those axes.

```text
baseline_overlap = positive overlap along the baseline
cross_overlap    = positive overlap across the baseline
allowance        = 0.26 * min(cross_size_1, cross_size_2)

collision_measure =
    baseline_overlap * max(0, cross_overlap - allowance)
```

A positive `collision_measure` is a conflict. There is no longitudinal/end allowance: any positive
baseline overlap can conflict once the allowed cross-axis padding is consumed. For equal-height
labels, the 26% overlap allowance is equivalent to a 74% effective cross-axis separation.

### Perpendicular text/text collision

Keep the complete baseline length of each label. Reduce only its cross-axis height to 88%:

```text
effective_cross_size = 0.88 * full_cross_size
```

This is a 6% trim at each cross-axis edge. Test the resulting orthogonal rectangles for positive
area overlap.

### Via scoring

When vias are a soft placement preference, keep the complete baseline length and use:

```text
effective_cross_size = 0.74 * full_cross_size
```

This is a 13% trim at each cross-axis edge. Do not shrink the via itself. Add any desired clearance
once, in a documented place.

The 88% perpendicular rule, 74% via envelope, and 26% parallel overlap allowance represent
different acceptance questions. They are intentionally not one generic “text shrink” constant.

## 6. Which box to use for each obstacle

A conservative default policy for a silkscreen placer is:

| Predicate | Recommended text geometry |
|---|---|
| Pad, terminal, solder mask, board cutout | Full placed cell plus hard clearance |
| Component body/courtyard, when enabled by the product contract | Full placed cell |
| Board-outline containment | All four corners of the full placed cell plus inside margin |
| Text/text readability | Calibrated visible profile when eligible; otherwise full cell |
| Via policy | Calibrated visible profile only when vias are explicitly soft; otherwise full cell |
| Broad-phase lookup | Full placed-cell AABB, because a broad phase may return false positives |

Never use a smaller visible box as the broad phase for a later full-cell hard predicate: that can
create false negatives.

Some manufacturing-oriented products intentionally collide a calibrated visible-stroke envelope
with pads/mask/body geometry rather than the orange font cell. That is a separate product contract,
not an optimization of the table above. Keep full-cell board containment and anchor reconstruction,
state the calibration domain and safety inset, and use the same declared envelope in tunnel
construction and the final exact predicate.

## 7. Orientation and ownership are part of geometry

For an auto-placement product, freeze these rules before tuning costs:

- whether 180-degree horizontal text normalizes to 0 degrees;
- whether the dominant existing vertical convention selects +90 or -90 degrees;
- whether a non-orthogonal marking remains at its original angle;
- whether an already readable placement remains locked;
- the hard maximum gap from the owning component;
- whether the package body or courtyard itself blocks the label.

Never change side/layer or font settings unless the product explicitly asks for it. Distance to
the owning component should be an explicit invariant or a dominant objective rather than a tiny
tie-breaker; otherwise dense interactions can exchange labels between components even when useful
space exists nearby. The actual angle policy, distance limit, and package classification belong to
the plug-in's product specification, not to this SDK.

File 56 provides reusable primitive, clearance, physical-side, indexing, and cache-correctness
geometry without prescribing a placement algorithm.

## 8. Final conflict policy

A weighted global objective is not proof that the final result has no text conflicts. A large via
penalty, movement penalty, or owner-distance term can make a remaining overlap look cheaper.

Whatever placement strategy is used, insert every accepted same-side text into the scene before
later candidates are evaluated. A final validator must use the same declared text envelope and
physical obstacle rules as placement. Re-check every moved text against the complete current
same-side scene, not only the pair or obstacle that triggered its last move.

Keep iterative repair deterministically bounded and propagate every user option (for example via
handling and configured clearances) through every phase. If the declared final invariant is still
false, follow the product's documented policy: abort without writing, leave the affected objects
unchanged, or return a proven safe partial result. Do not serialize an optimizer's last state merely
because its iteration budget expired.

## 9. Determinism requirements

Do not rely on XML order or a stable sort whose semantic key can tie. A canonical marking key should
include at least:

- component identity and field identity;
- resolved text;
- board-space center;
- normalized angle;
- resolved width and height;
- a final stable serialization discriminator for otherwise identical records.

Candidate ties need an equally total key. Run the same board with reversed collection/XML order and
require the same decisions and normalized output.

When subtracting a moving label's original self-hit from a text index, compare against that exact
label's original **visual** box. Comparing a visual candidate against the original full cell can
subtract another label's collision.

## 10. Build a calibration fixture

For a new text class or font profile:

1. create known horizontal and vertical labels beside known board geometry;
2. include narrow and wide glyphs, digits, mixed strings, multiline, spaces, punctuation,
   lowercase, non-ASCII, overline markup, vector mono mode, every stroke code, and required
   TrueType faces;
3. capture the DipTrace cell rectangle and visible strokes at a reproducible zoom/render setting;
4. measure baseline and cross-axis occupancy separately;
5. choose a conservative envelope from the worst validated case plus a stated safety margin;
6. version the calibration by DipTrace build, font mode, and measurement method;
7. keep all unvalidated classes on the full-cell fallback.

Never derive expected test results with the same function being tested. Use hand-measured cases, a
separate reference implementation, or an independent renderer.

## 11. Minimum regression matrix

The permanent suite for text placement should include:

- full-cell anchor reconstruction for every horizontal/vertical alignment;
- local `Common` resolving to global `Position` and global `Auto`;
- Auto field ordering with hidden, author-suppressed, and shown-empty fields;
- `CompRotate=Y` and `CompRotate=N` on orthogonal and non-orthogonal asymmetric footprints;
- 0, +90, 180, -90, and non-orthogonal board-space angles;
- parallel cross-axis overlap just below/at/above the allowance;
- parallel end-to-end overlap just below/at/above zero;
- perpendicular overlap just below/at/above the calibrated trim;
- eligible uppercase/digit vector text and every full-cell fallback class;
- pads, mask, vias, component bodies, straight/curved outlines, and cutouts;
- top/bottom components and marking-versus-footprint transforms;
- same-text/different-font and different-text/same-placeholder cache cases;
- already valid labels, failed/unmoved labels, and dense conflict chains;
- unresolved/fail-closed behavior preserving the input byte-identically when required;
- any bounded-path interval primitive against an independent brute-force oracle;
- physical Top/Bottom SMD separation and the product's declared owner-association invariant;
- collection-order reversal, source/EXE parity, and repeated-run determinism.

See [`70_complex_plugin_review.md`](70_complex_plugin_review.md) for the independent skeptic
protocol that found several of these cases.
