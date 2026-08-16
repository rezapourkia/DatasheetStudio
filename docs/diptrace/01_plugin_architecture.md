# DipTrace Plug‑in Architecture

How a DipTrace plug‑in is packaged, launched, and how it exchanges data with the main
program. This public contract consolidates the shipped documentation and examples, captured
exchange fixtures, and verified host behavior. A plug-in author does not need DipTrace source
code to use it.

## 1. What a plug‑in is

A DipTrace plug‑in is a **standalone executable** (`.exe`) written in **any language and any
toolkit** (the shipped examples are C#/.NET and Delphi). It communicates with DipTrace **only
through a temporary XML file** — there is no in‑process API, no DLL, no callback. The plug‑in
runs as a separate process, edits the file, exits; DipTrace then reads the file back.

Because the contract is "a file in, the same file out," most transformation logic can be tested
offline by running the executable on copied XML fixtures. Prefer a captured **real plug‑in
exchange** for final fixture tests: ordinary `Save As DipTrace XML` can differ from the
exchange-time payload (for example, embedded design-cache styles depend on export scope). The
capture helper under [`templates/python`](templates/python/) copies `argv[1]` without changing it.

## 2. Folder layout & discovery

Each plug‑in lives in its own folder under the program it belongs to, inside the DipTrace
working directory:

```
<DipTrace>\Plugins\Pcb\<PluginName>\
<DipTrace>\Plugins\Schematic\<PluginName>\
<DipTrace>\Plugins\CompEdit\<PluginName>\
<DipTrace>\Plugins\PattEdit\<PluginName>\
```

A folder must contain at least:

- the plug‑in **executable**, and
- **`settings.xml`** — the manifest.

At startup each program scans **two** locations for plug‑in folders: the shared
`…\Plugins\` folder **and** its own `…\Plugins\<Program>\` subfolder. In each candidate
sub‑folder it takes the first `*.exe` it finds and then looks for `settings.xml` beside it.
A plug‑in is **listed under Tools ▸ Plugins only if** its `settings.xml` exists and its
`Type` matches that program (see §3); an exe with no matching manifest is ignored. Discovery
happens **once, at program startup** — add or change a plug‑in, then restart the program.

Keep the plug‑in folder/name and exchange path reasonably short and representable in the Windows
system code page. Current launchers pass executable and argument paths through a legacy
approximately 255-byte ANSI command-line buffer; a very long or non-representable path can fail
before plug‑in code starts. The plug‑in cannot repair a path that it never receives.

One `settings.xml` carries exactly **one** `Type` and therefore lists the plug‑in in exactly
**one** program. To surface the same tool in several programs, reuse the executable but give
**each** program its own plug‑in folder with its own `settings.xml` (each with the matching
`Type`) — a single shared manifest cannot appear in more than one editor.

## 3. `settings.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<Source Type="DipTrace_Pcb_Plugin" Name="My Plugin" ExeFile="MyPlugin.exe">
  <Settings>
    <!-- Export mode: what DipTrace writes for you -->
    <ExpMode>Partial</ExpMode>
    <!-- Import mode: how DipTrace reads your result back -->
    <ImpMode>Edit</ImpMode>
    <!-- Per‑object export/import filter -->
    <Comp>None</Comp>
    <Net>None</Net>
    <Shape>Selected</Shape>
    <Plane>None</Plane>
    <Table>None</Table>
    <Dim>None</Dim>
    <Diff>None</Diff>
    <Board>None</Board>
    <Trace>None</Trace>
    <Stamp>None</Stamp>
  </Settings>
</Source>
```

`<Source>` attributes:

- **`Type`** — which program the plug‑in belongs to. One of:
  `DipTrace_Pcb_Plugin`, `DipTrace_Schematic_Plugin`,
  `DipTrace_CompEdit_Plugin`, `DipTrace_PattEdit_Plugin`.
  If this doesn't match the program doing the scan, the plug‑in is not listed there.
- **`Name`** — the menu caption shown under Tools ▸ Plugins. If omitted, the exe's file name
  (without extension) is used.
- **`ExeFile`** — the executable to launch (relative to the plug‑in folder). It must exist
  and end in `.exe`, otherwise DipTrace falls back to the first `*.exe` it found in the folder.
- **`Hint`** *(optional)* — status‑bar hint text shown when the menu item is highlighted.

> ⚠️ **Two different `Type` namespaces.** In `settings.xml` the `<Source Type>` is a *plugin
> type* with **underscores** (`DipTrace_Pcb_Plugin`). Inside the **data / exchange** XML the
> `<Source Type>` is a *file type* with **hyphens** (`DipTrace-PCB`). Do not confuse them.

### Export mode `<ExpMode>` — what DipTrace hands you

| Program | Values |
|---|---|
| PCB / Schematic | `All` (everything, ignore per‑object filter) · `Partial` (per‑object filter) · `None` (empty file; you only add) |
| CompEdit | `None` · `Library All` · `Library Partial` · `Component All` · `Component Partial` · `Part All` · `Part Partial` |
| PattEdit | `None` · `Library All` · `Library Partial` · `Component All` · `Component Partial` |

### Import mode `<ImpMode>` — how your result is merged back

| Program | Values |
|---|---|
| PCB / Schematic | `All` · `Edit` (per‑object) · `None` (export‑only, nothing read back) |
| CompEdit | `None` · `Library All` · `Library Add` · `Library Insert` · `Component All` · `Part All` · `Edit` |
| PattEdit | `None` · `Library All` · `Library Add` · `Library Insert` · `Component All` · `Edit` |

`Edit` is the usual choice: DipTrace merges your changes, overwriting modified properties and
adding new objects. (In CompEdit/PattEdit `Edit`, patterns of matched components are fully
overwritten if `Patterns=Yes`.)

### Per‑object filter — the `<Object>` tags

Each object tag takes `All` / `Selected` / `None` (or `Yes` / `No` for on/off tags). With
`ExpMode=Partial`, only the object kinds you set to `All` or `Selected` are exported.
For simple top-level objects, `Selected` means "only objects whose XML element carries
`Selected="Y"`." Aggregate objects such as nets, buses, and differential pairs do **not**
necessarily have a top-level `Selected` flag; their selection is derived from selected child
geometry as detailed below. Do not apply the simple-object rule to them.

**In CompEdit** `Selected` only means anything in the `Component Partial` / `Part Partial`
export modes; **in PattEdit** only in `Component Partial` (PattEdit has no Part level). For
import and all other modes it behaves like `All`.

| Program | Object tags |
|---|---|
| **PCB** | `Comp` `Net` `Shape` `Plane` (copper pours) `Table` `Dim` `Diff` `Board` (outline) `Trace` (**ratlines/unrouted connections** — routed copper rides under `Net`) `Stamp`(Yes/No) |
| **Schematic** | `Comp` `Net` `Shape` `Table` `Bus` `BusConnectors` `Diff` `Patterns`(Yes/No) `Stamp`(Yes/No). `Board`, `Trace`, and the top-level meaning of `Dim` are accepted compatibility placeholders because Schematic has no corresponding top-level object list. Footprint dimensions nested inside the embedded pattern library are real data and follow `Patterns`, not `Dim`. |
| **CompEdit** | `Comp` `Shape` `Pin` `Pattern`(Yes/No) `Attributes`(Yes/No) |
| **PattEdit** | `Comp` `Shape` `Pad` `Hole` `Dim` `Attributes`(Yes/No) |

Every applicable `<Settings>` child must be present. Missing children are not a supported way to
select defaults, and an unrecognized token can silently map to a disabled state. Start from the
complete per-program manifests in [`templates`](templates/) and change values explicitly.
PCB/Schematic currently accept `Edit` as a compatibility alias for partial export, but use the
canonical `ExpMode=Partial`; reserve `ImpMode=Edit` for import.

#### Compound-object `Selected` rules (PCB / Schematic)

| Filter | What makes the parent selected for export | Important import behavior |
|---|---|---|
| PCB `Net=Selected` | Any routed `<Trace Selected="Y">` (`TNet.line.selected`) in the net. Point-level `Selected` is not tested directly. | The net itself has no `Selected` attribute. Once the net qualifies, the exporter writes the whole net and all its traces; inspect each `Trace@Selected` / `Point@Selected` for custom trace- or segment-level work. |
| PCB `Diff=Selected` | Any point of any differential-pair segment is selected. | The pair itself has no `Selected` attribute. |
| Schematic `Net=Selected` | Any `<Wire Selected="Y">` (`TNet.line.selected`) in the net. | The exporter writes the whole qualifying net and all its wires. However, in `Edit`, the incoming `<Wires>` list is rebuilt from **only** wires carrying `Selected="Y"`; returning a complete exported net can therefore drop its unselected wires. |
| Schematic `Bus=Selected` | Any bus `<Wire Selected="Y">` (`TBus.line.selected`). | The exporter writes the whole qualifying bus; the same selected-wire-only rebuild applies to its `<Wires>` list in `Edit`. |
| Schematic `Diff=Selected` | Either member net contains a selected wire. | Supported; the differential pair itself has no `Selected` attribute. |

> **Safe runtime "selected nets" switch for Schematic.** Use `Net=All`, determine selected
> scope in your executable by testing for at least one `<Wires><Wire Selected="Y">`, and return
> only the nets you actually edit. If you are changing only a net property such as `<Name>`,
> omit its `<Pins>` and `<Wires>` children from the returned `Edit` record so connectivity and
> geometry stay untouched. See `50_common_operations.md` → *Inspect broadly, edit narrowly*.

Schematic `Patterns=No`/`None` omits the nested pattern library and the component parts'
`<Pattern Style="…">` links from the embedded design-cache library; `Patterns=Yes`/`All`
includes them, including footprint-local `<Dimensions>` stored in those patterns. The
Schematic `Dim` setting does not independently suppress these nested dimensions. They travel
with the footprint when it is saved/opened in Pattern Editor or used in PCB; they are not a
top-level Schematic dimensions list. `Stamp=No`/`None` omits page-border/title-block data in
`Partial` export; `Stamp=Yes`/`All` includes it.

> A minimal "process only the selected shapes" plug‑in sets `ExpMode=Partial`,
> `ImpMode=Edit`, `Shape=Selected`, everything else `None`. That is exactly what the shipped
> `DashDotLine` example does.

The full table of every mode and its meaning is in `DipTrace_Plugins.pdf`.

> **Reading project metadata.** `ExpMode=Partial` still exports PCB board infrastructure such as
> `<Settings>`, layers, via styles, net classes/rules, DRC, and project-library settings. The
> embedded design-cache `<Library>` is different: PCB exports it only for `ExpMode=All` or when
> `Comp` is enabled (`All` or `Selected`). A plug-in that needs `PatternStyle` geometry — pads,
> footprint shapes, holes, mask/paste data, or bound footprint text — must therefore request
> components. Use `Comp=All` when every placed component must be analysed. `ExpMode=None` produces
> an essentially empty document.

For a board-wide component-text analysis, a safe manifest is `ExpMode=Partial`,
`ImpMode=Edit`, `Comp=All`, `Net=All`, `Shape=All`, and `Board=All`, with unrelated editable
families set to `None`. This exposes component footprints, routed/static vias, free mask/cutout
shapes, and the outline without opting into whole-project replacement.

## 4. Runtime lifecycle

```
User clicks Tools ▸ Plugins ▸ <Name>
        │
        ▼
DipTrace writes  plugin_exchange.xml  to a temp folder,
   containing the data selected by <ExpMode> + the per‑object filter.
        │
        ▼
DipTrace launches   <ExeFile>  "<full path to plugin_exchange.xml>"
   (the file path is passed as the first command‑line argument)
        │
        ▼
Your plug‑in:  load the file → modify it → overwrite the SAME file → exit.
        │
        ▼
DipTrace re‑reads plugin_exchange.xml per <ImpMode> and merges the result
   into the live project.
```

Key facts (verified against the DipTrace implementation):

- The exchange file is always named **`plugin_exchange.xml`** in DipTrace's temp directory,
  and its full path is passed to your exe as **`argv[1]`** (quoted). Read it from `argv[1]` —
  don't hard‑code a name or location.
- Your exe is started with `CreateProcess`; its **working directory is your plug‑in's own
  folder**, so relative paths (config, resources) resolve there.
- DipTrace **waits synchronously for your process to exit**, then imports. There are no live
  exchange updates. For a plug-in that imports a result, the current host disables the
  application's main editor window for the export/wait/import transaction while leaving the
  progress/cancel window active. This prevents queued editor commands from mutating the live
  project or the global import mode while the plug-in owns an exported snapshot.
- During a plug-in run the progress/cancel window is an **owned, non-topmost DipTrace window**:
  it stays above DipTrace's own forms, including while the main editor is disabled, but it does
  not cover a foreground window belonging to the external plug-in or another application.
- If the user cancels, DipTrace requests forced termination and waits up to five seconds. A
  process still pending after that bound no longer freezes the editor; the host polls its
  process handle in the background and blocks another plug-in launch until it is really dead.
  The old exchange path is therefore never reused concurrently.
- **You must overwrite `plugin_exchange.xml` in place.** DipTrace notes the file's timestamp
  before launching you and reads back *that same path*; if you never re‑save the file, there
  is nothing to import. (Save even if you only changed part of it.)
- If `ExpMode=None`, DipTrace hands you an essentially empty document — appropriate for
  "generate objects from scratch" plug‑ins; the real project data returns through import.

### How your result is merged back (per `ImpMode`)

- **`All`** — the incoming list *replaces* the project's list of that object kind entirely.
  Anything you dropped from the file is removed from the project.
- **`Edit`** — DipTrace matches each incoming **top‑level** object to an existing one **by its
  `Id`** and overwrites it in place; an object whose `Id` is new/out‑of‑range (or absent) is
  **added**. This is why, to modify or delete an existing object, you keep its `Id`; to add
  one, you can just append it (see §6).
- **Id‑matching applies to top‑level object kinds only.** Nested lists whose members have no
  `Id` of their own — a net's `<Traces>`, a net/bus `<Wires>` list, point/teardrop lists — are
  **subtree‑replaced** when present in your XML: the existing list is discarded and rebuilt
  from exactly the children you supply. Omit the container element entirely to leave that list
  untouched; to add one member, re‑list all current members plus the new one.
- With a **`Selected`** filter in `Edit` mode, simple top-level object kinds are gated by their
  `Selected="Y"` attribute: a marked object with an existing `Id` overwrites it in place, and
  a marked object with a new/absent `Id` is added; an unmarked incoming object is skipped.
  Keep `Id` + `Selected="Y"` on simple objects you edit, and put `Selected="Y"` on every simple
  object you add. **Nets, buses, and differential pairs are exceptions** because their selection
  is derived from child geometry; follow the compound-object table in §3. In particular, avoid
  `Net=Selected` / `Bus=Selected` for a Schematic plug-in that must preserve unselected wires.

## 5. The exchange file *is* DipTrace XML

The `plugin_exchange.xml` uses the same format as a saved DipTrace XML file for that program.
Its **root element and the data node you work under** differ per program:

| Program | Root | Your data lives under | Dialect reference |
|---|---|---|---|
| PCB Layout | `<Source Type="DipTrace-PCB">` | `/Source/Board` | `10_pcb_xml_reference.md` |
| Schematic | `<Source Type="DipTrace-Schematic">` | `/Source/Schematic` | `20_schematic_xml_reference.md` |
| CompEdit | `<Library Type="DipTrace-ComponentLibrary">` | `/Library/Components/Component/Part` | `30_compedit_xml_reference.md` |
| PattEdit | `<Library Type="DipTrace-PatternLibrary">` | `/Library/Patterns/Pattern` | `40_pattedit_xml_reference.md` |

For PCB/Schematic the `<Source>` also contains a `<Library>` section (the design‑cache
component library, which **nests** the pattern library inside it); the editable project data
is under `<Board>` / `<Schematic>`.

## 6. The read → modify → write contract (idioms)

These conventions are **not** in the format spec but are how the shipped examples and the
importer actually behave. Follow them.

1. **Read only what you asked for.** With a `Partial` export the file contains only the object
   kinds your filter enabled; iterate those. Test the `Selected="Y"` and (see below)
   `Enabled` attributes to pick the objects the user actually chose.

2. **To remove or replace an existing object, disable it — don't just delete the node.** Set
   **`Enabled="N"`** on the object and leave it in the file; DipTrace treats an `Enabled="N"`
   object as removed on import. `Enabled` is an actual serialized attribute that the importer
   reads on the editable objects (components, nets, shapes, tables, dimensions, …) even though
   the public XML spec doesn't list it on every one of them — the shipped `DashDotLine`
   example relies on exactly this to replace shapes. A missing `Enabled` attribute means
   *enabled*. (To replace an object: `Enabled="N"` the original **and** append the new
   objects.)

3. **Most objects you add don't need an `Id` you invent.** Just append the new element; in `Edit`
   import an object with no `Id` (or an out‑of‑range one) is added as new, and DipTrace
   assigns its identity. The shipped example appends new `<Shape>`s with no `Id` at all. Keep
   an existing `Id` **only** when you are editing that specific object in place, or when other
   objects reference it by `Id` (nets, components). Mark objects you add with `Selected="Y"`
   so they come back through a `Selected`/`Edit` import and end up selected for the user.
   Exceptions must be explicit and based on a complete visible namespace: `Group`, and the
   verified same-exchange PCB new-net recipe in file 50 where new pads must reference that net.

4. **Group objects you add** by appending a `<Group Id="n" Selected="Y"/>` to the `<Groups>`
   list and setting `Group="n"` on each member. Groups *do* need an `Id` you assign: scan the
   existing `<Group>` `Id`s and use the next free number (this is the Id the shipped example
   manages itself). Create the `<Groups>` node if the file has none.

5. **Analyze broadly; return the proven merge shape.** Load and validate the broad original, but
   do not automatically write that broad tree back for `Edit`. Construct the narrow result the
   dialect's merge contract requires: usually only complete changed top-level records plus
   required infrastructure such as `/Source/Library` for PCB component styles. Preserve unknown
   attributes/children inside every returned record. If no semantic change is planned, do not
   serialize or replace the exchange file at all.

6. **Honor `Units` and number formatting** — see §7.

7. **PCB components are not safe sparse records.** For every placed `<Component>` you return,
   clone the complete exported node and change only the intended leaves. Preserve its
   `PatternStyle`, all attributes, pads, fields, markings, and unknown children. A component
   `PatternStyle` load resets instance data before the remaining fields are read; `<Pads>` and
   `<AddFields>` are rebuilt when their containers are present. Omitting `PatternStyle` is also
   unsafe for a bottom-side component because the side transform is applied after reading.
   Return only the complete component nodes that changed, but preserve the root sibling
   `/Source/Library` unchanged so every `PatternStyle` still resolves.

## 7. Units and number formatting

- The root element carries **`Units="mm" | "inch" | "mil"`**. Coordinates and ordinary
  geometry sizes use those units. Convert them to your internal working unit on read and back
  on write consistently. Font scalars such as `FontSizeFloat` and positive `FontWidth` are an
  exception; do not treat them as project lengths. See file 02 §2/§8.
- **Decimal separator:** **always write a dot** (`0.33`, invariant culture) — it's the
  canonical form and what every other tool reading the file will expect. (DipTrace's own
  reader is lenient: it normalizes **both** `.` and `,` to the running machine's separator
  before parsing, so it reads either — but don't rely on that leniency in files other software
  may consume.) When **parsing** be equally defensive: replace `,`→`.` then parse with the
  invariant/`en-US` culture, exactly as the shipped C# example does.
- Rounding precision the examples use per unit: **inch → 4**, **mil → 2**, **mm → 4** decimal
  places.

## 8. Minimal skeletons

These snippets show traversal and the mandatory `changed` gate. A release build must also use the
atomic-save, logging, packaging, and source/EXE parity rules in §8.1 and
[`05_production_plugin_workflow.md`](05_production_plugin_workflow.md). The reusable Python
starter under [`templates/python`](templates/python/) implements that wrapper.

### C# / .NET (`System.Xml.XmlDocument`)

```csharp
static int Main(string[] args)
{
    if (args.Length < 1) return 1;
    string path = args[0];                       // exchange file path (argv[1])

    var doc = new XmlDocument();
    doc.Load(path);

    // Identify the program from the root <Source Type> / <Library Type>.
    // PCB:  /Source/Board   Schematic: /Source/Schematic
    // CompEdit: /Library/Components   PattEdit: /Library/Patterns
    var shapes = doc.SelectNodes("/Source/Board/Shapes/Shape");
    bool changed = false;
    foreach (XmlNode shape in shapes)
    {
        var sel = shape.Attributes?["Selected"]?.Value;
        var en  = shape.Attributes?["Enabled"]?.Value;   // null => enabled
        if (sel != "Y" || en == "N") continue;
        // ... modify, or set Enabled="N" and append replacement shapes ...
        // changed = true only for a semantic edit that should be imported.
    }

    if (!changed) return 0;                      // leave content and timestamp untouched
    string temp = System.IO.Path.Combine(
        System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(path)),
        System.IO.Path.GetRandomFileName());
    try {
        doc.Save(temp);
        var verify = new XmlDocument(); verify.Load(temp);
        System.IO.File.Replace(temp, path, null); // same-volume atomic replacement
        temp = null;
    }
    finally {
        if (temp != null) try { System.IO.File.Delete(temp); } catch { }
    }
    return 0;
}

// Parse a DipTrace real (accepts comma or dot):
static bool ParseReal(string s, out double v)
{
    bool ok = double.TryParse((s ?? "").Replace(',', '.'),
        System.Globalization.NumberStyles.Float,
        System.Globalization.CultureInfo.InvariantCulture, out v);
    return ok && !double.IsNaN(v) && !double.IsInfinity(v);
}
```

See the full example in `…\Plugins\Pcb\DashDotLine\SourceCodeC#` — note `Settings.cs`
(`ConvertUnits`, `ParseDouble`) and `Programs\ProgramPcb.cs` (read/append/disable pattern).
⚠️ Treat the shipped examples as **protocol demos, not production templates**: `Program.cs`
contains a `Console.ReadLine()` right before the save — with no console attached this stalls
the (blocked) DipTrace until the process is killed. Remove any blocking wait before saving.

### Delphi (VCL, e.g. `Xml.XMLDoc` / MSXML)

```pascal
program MyPlugin;
uses Windows, SysUtils, Xml.XMLIntf, Xml.XMLDoc;
var
  Doc: IXMLDocument;
  Fmt: TFormatSettings;
  v: Double;
  Changed: Boolean;
  TempName: string;
begin
  if ParamCount < 1 then Halt(1);
  Fmt := TFormatSettings.Invariant;            // dot decimal for read/write
  Doc := LoadXMLDocument(ParamStr(1));         // exchange file = ParamStr(1)
  Changed := False;
  // ... walk /Source/Board/Shapes, modify, set Enabled='N', append ...
  // Set Changed := True only for a semantic edit.
  // Reals: ALWAYS pass Fmt — the 2-arg overloads use the OS locale and
  // misparse dot-decimals on comma-locale machines:
  //   if TryStrToFloat(StringReplace(s, ',', '.', [rfReplaceAll]), v, Fmt) then ...
  //   attr.NodeValue := FloatToStr(v, Fmt);
  if not Changed then Halt(0);                 // leave content and timestamp untouched
  TempName := ParamStr(1) + '.tmp-' + IntToHex(GetTickCount64, 16);
  try
    Doc.SaveToFile(TempName);
    // Optionally re-open TempName for structural validation before this commit.
    if not MoveFileEx(PChar(TempName), PChar(ParamStr(1)),
                      MOVEFILE_REPLACE_EXISTING or MOVEFILE_WRITE_THROUGH) then
      RaiseLastOSError;
    TempName := '';
  finally
    if TempName <> '' then DeleteFile(TempName);
  end;
end.
```

See the full example in `…\Plugins\Pcb\OpenMaskForSelectedTraceSegments\SourceCodeDelphi`
(reusable geometry helpers and per‑unit precision). ⚠️ Its `ParseDouble` normalizes the string
with the passed `TFormatSettings` but then calls the **2‑arg** `TryStrToFloat`, which uses the
OS locale — the exact anti‑pattern the skeleton comment above warns about; pass `Fmt` in your
own code.

### Python (`xml.etree.ElementTree`)

Any language works, but DipTrace launches a Windows **`.exe`**, not a `.py` file. The transformation
below uses only the Python standard library; package it with a runtime/launcher for release.
Build the plug-in for the matching DipTrace edition: x86 for the supported 32-bit edition and x64
for 64-bit DipTrace. Prefer the complete x64 stack for large XML/geometry; keep x86 as the
compatibility deliverable. PyInstaller does not cross-build the other bitness: run the same
reviewed source and pinned packager once per target architecture. See the ready starter and build
script under [`templates/python`](templates/python/).

```python
import os, sys, tempfile, traceback, xml.etree.ElementTree as ET

def run(path):
    tree = ET.parse(path)
    root = tree.getroot()                       # <Source> (PCB/Schematic) or <Library>
    changed = False
    for shape in root.findall('./Board/Shapes/Shape'):     # adjust path per program
        if shape.get('Selected') != 'Y' or shape.get('Enabled') == 'N':
            continue
        # ... modify in place, or set Enabled='N' and append replacement <Shape>s ...
        # changed = True only for a semantic edit
    if not changed:
        return False                            # no serialization, no import
    # Write beside the exchange file, then atomically replace that SAME path.
    fd, tmp = tempfile.mkstemp(prefix='plugin_exchange.', suffix='.tmp',
                               dir=os.path.dirname(os.path.abspath(path)))
    os.close(fd)
    try:
        tree.write(tmp, encoding='utf-8', xml_declaration=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True

def write_log(message):
    bases = [os.environ.get('LOCALAPPDATA'), tempfile.gettempdir()]
    for base in filter(None, bases):
        try:
            folder = os.path.join(base, 'DipTrace', 'PluginLogs')
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, 'MyPlugin.log'), 'w', encoding='utf-8') as f:
                f.write(message)
            return
        except OSError:
            pass

def main():
    if len(sys.argv) != 2:
        return 1
    try:
        run(sys.argv[1])
        return 0
    except Exception:                             # never crash silently — see §8.1
        try:
            write_log(traceback.format_exc())
        except Exception:
            pass
        return 1                                  # file left untouched → DipTrace imports nothing

sys.exit(main())
```

Python `str(float)` already uses a dot independently of the process locale. Still use an explicit
finite-number check and controlled format (for example `f'{v:.4f}'`) to stabilize precision,
scientific notation, and negative zero. `ElementTree` retains unknown attributes/elements that
remain in the tree **semantically**, but does not promise byte identity: comments/processing
instructions, namespace prefixes, indentation, quoting, or declarations can change. A true
abort/no-op therefore must not serialize the file.

## 8.1 Robustness — exceptions, saving, and plug‑in windows

DipTrace launches the plug‑in **synchronously**: it starts your process, keeps the launch handler
waiting until you exit, then re‑reads the exchange file (it detects your work by the file having
**changed**, not by your exit code). The VCL message queue is still pumped for responsiveness;
do not mistake the synchronous handler for an immutable-project transaction. Three rules follow:

- **Write the file once, only after you've fully and successfully built the result.** A crash
  *before* you save leaves the original untouched — a safe no‑op. A *partial* or malformed write
  can be imported as garbage or fail to parse. Build everything in memory; `Save`/`SaveToFile`
  **last**. Prefer a temporary sibling file followed by an atomic replace (`os.replace` on
  Python/Windows) so process termination cannot leave a truncated exchange XML. On any exception,
  delete the temporary file and **do not replace the original**. If DipTrace Cancel hard-kills the
  process, `finally`/destructors are not guaranteed; atomic replacement still protects the
  original, but clean stale sibling temp files on a later start.
  Treat the successful atomic replace as the commit point: only after it succeeds may the plug-in
  log final success or close its last progress/result window. If commit fails, retain the already
  computed run diagnostics with the traceback and leave the original exchange untouched.
- **Wrap the run in try/catch, log, and exit.** A silent unhandled exception looks to the user like
  "the plug‑in did nothing." Always write one durable log with plug-in version, phase, object
  identifier, and full traceback to `%LOCALAPPDATA%\DipTrace\PluginLogs`; if creating or writing
  there fails, try `%TEMP%`. A plug-in is commonly installed under `Program Files`, so its
  executable directory may not be writable. If there is UI, show at most one error inside/owned by
  the plug-in's own main window and point to the log. Never show a chain of unowned message boxes.
  Exit non‑zero by convention; the log/UI, not the exit code, tells the user what happened.
- **Never hang.** For import-capable runs the main editor is unavailable while its message queue
  and status/cancel UI remain responsive until your process exits. An infinite loop, hidden
  dialog, console `input()`/`ReadLine`, or window that never closes blocks completion.

```csharp
static int Main(string[] args)
{
    string temp = null;
    try
    {
        if (args.Length < 1) return 1;
        var doc = new XmlDocument();
        doc.PreserveWhitespace = true;
        doc.Load(args[0]);
        bool changed = Transform(doc);            // validate and build the result in memory
        if (!changed) return 0;                    // leave original content/timestamp untouched
        temp = System.IO.Path.Combine(
            System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(args[0])),
            System.IO.Path.GetRandomFileName());
        doc.Save(temp);
        System.IO.File.Replace(temp, args[0], null); // atomic, same volume
        temp = null;
        return 0;
    }
    catch (Exception ex)
    {
        try { if (temp != null) System.IO.File.Delete(temp); } catch { /* ignore */ }
        try {
            var dir = System.IO.Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "DipTrace", "PluginLogs");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(
                System.IO.Path.Combine(dir, "MyPlugin.log"), ex.ToString());
        }
        catch { /* ignore */ }
        return 1;                    // original file left untouched → DipTrace imports nothing
    }
}
```

**If your plug‑in shows a window** (WinForms/WPF/Avalonia/Qt…): it runs in **your own** process, so
it is a **separate taskbar window**, not a DipTrace dialog. DipTrace passes you **only the
exchange‑file path** (`argv[1]`) — not its window handle — so you cannot make your window a true
child of DipTrace's. Practical rules:
- Use a normal foreground main window or a modal dialog **inside your own process**. System-wide
  `TopMost` is normally unnecessary and may cover unrelated applications; the DipTrace status
  window deliberately is not system-topmost during a plug-in run.
- For an import-capable run, treat the plug-in UI as **effectively modal to the editor**: the user
  acts in your window, you save and exit, and only then does DipTrace import. `ImpMode=None`
  export-only tools do not have the same disabled-editor contract. Give Cancel a path that exits
  without saving.
- Build production headless/UI plug-ins as Windows-subsystem applications (`WinExe`, PyInstaller
  `--noconsole`, Delphi GUI application) and log to a file. Console-subsystem builds can open a
  console because the host starts a new console; keep them for development only.
- In an external PowerShell parity test, launch a GUI/`--noconsole` EXE with
  `Start-Process -Wait -PassThru` and inspect that process's `ExitCode`; a direct launch can return
  before completion and leave `$LASTEXITCODE` empty or stale. Compare the resulting XML as well.

### The exact process contract

These are hard facts of how DipTrace runs your plug‑in — they shape robust plug‑ins and rule some
approaches out:

- **No automatic run timeout.** DipTrace waits for your process until it exits or the user
  cancels. Always make every path exit.
- **Cancel hard‑kills.** If the user cancels while you run, DipTrace **terminates** your process and
  does **not** import whatever file you had written at that moment. The forced-termination wait is
  bounded; if Windows cannot complete it promptly, only subsequent plug-in launches remain
  blocked while the main editor becomes usable again.
- **Your exit code is ignored.** Success/failure is decided **solely** by whether you modified the
  exchange file (its timestamp changed). Rewrite the file to apply changes; **leave it untouched to
  signal "do nothing / I failed"** — a non‑zero exit code alone has no effect.
- **No error channel back to DipTrace.** There is currently **no** way to hand DipTrace a message or
  error to display — no stdout capture, no status/error‑file convention. Surface problems in your
  own window or a log file. (DipTrace shows a dialog only if your exe **fails to launch**.)
- **No host-enforced size limit** is imposed on the exchange XML. DOM/ElementTree memory can be
  several times the file size and packaging/start-up still has practical costs. Prefer a 64-bit
  executable for large geometry workloads; if you also distribute x86, run the same large-fixture
  memory/performance gates against that exact artifact. See file 55.

## 8.2 Heavy geometry — use a library and measure the pipeline

The format stores only *results* — point lists (`<Points><Point/></Points>`), arcs as 3 points,
etc. Any non‑trivial geometry (polygon union/offset/inset, clipping, fillets, arc→polyline
flattening) is **your** job, and hand‑rolling it is where generated plug‑ins go wrong. Use a proven
library and emit its output as DipTrace geometry:
- **Polygon boolean / offset / inset:** Clipper2 (C++, C#, and Delphi ports exist).
- **Arc/curve → polyline:** sample the arc to `<Point>`s at your tolerance (or keep it as a true
  3‑point `Arc` shape when you want the arc itself, not a flattened one).

These are **general‑purpose** libraries — nothing DipTrace‑specific ships them; add them to your own
project.

For prepared outlines, bounded spatial indices, complete cache keys, deterministic equivalence,
XML-memory control, and source/EXE performance measurement, use
[`55_heavy_geometry_optimization.md`](55_heavy_geometry_optimization.md).

## 9. Testing & debugging

- Capture a real exchange with the export-only helper under
  [`templates/python`](templates/python/); use `Save As DipTrace XML` as an additional, not
  equivalent, fixture. Always run on a copy.
- Run source and the freshly packaged, installed executable on separate copies of the same input.
  Compare normalized XML, changed IDs, counters/log summary, exit, artifact version, and hash.
- Verify abort/no-op content **and timestamp**, non-finite numbers, forced termination during
  compute/temp-write, narrow-output goldens, cold/warm start, and peak memory.
- Because DipTrace only imports after your process exits, use a log rather than console
  interaction. If nothing comes back, check `ImpMode`, selection flags, exact `argv[1]` path, and
  that `settings.xml` points to the executable you actually tested.
- Finish with a disposable-project smoke test covering import result, Undo/reopen, Cancel/relaunch,
  and plug-in-window visibility. Static tests cannot claim these host behaviors.

The full evidence ladder and release package are in
[`05_production_plugin_workflow.md`](05_production_plugin_workflow.md).

## 10. Gotchas checklist

- [ ] Read the path from `argv[1]`; write back to the **same** path.
- [ ] Correct `<Source Type>` in `settings.xml` (underscored plugin type).
- [ ] Every applicable manifest child is present; `ExeFile` names the exact tested executable.
- [ ] Right root/data node for the program (`/Source/Board`, `/Source/Schematic`,
      `/Library/Components`, `/Library/Patterns`).
- [ ] Parse reals accepting **both** `.` and `,`; write with `.`.
- [ ] Respect `Units`; convert consistently.
- [ ] Remove by `Enabled="N"`, not by deleting the node.
- [ ] New objects normally **omit `Id`**, carry `Selected="Y"`, and may reference a `Group`.
      Explicit assigned-Id exceptions are `Group` and the complete-namespace PCB new-net recipe
      in file 50.
- [ ] Editing a net? Nested `<Traces>`/`<Wires>` lists are **replaced, not merged** — omit the container or re‑list everything.
- [ ] Preserve unknown attributes/elements.
- [ ] Returning PCB components? Keep only changed components, but each one is a **complete exported
      clone**, and keep `/Source/Library` unchanged.
- [ ] Use the separate footprint, marking, and mask-side transform laws; do not apply
      `Side`/`Flip`/`HorzFlip` uniformly.
- [ ] Reject unsupported arcs, mask/paste modes, missing styles, or unmeasurable text
      **before writing**; leave the original exchange file untouched.
- [ ] Reject `NaN`/infinity and invalid dimensions/point counts with object+attribute diagnostics.
- [ ] A semantic no-op leaves file content and timestamp untouched.
- [ ] Wrap the run in try/catch; **save only on success**, write a traceback log on failure; never hang.
- [ ] If you show a window: use a normal foreground/modal window in the plug-in process, and give
      Cancel a path that exits without saving.
- [ ] Fresh source, packaged EXE, and installed EXE pass parity/hash checks on copied fixtures.
- [ ] Restart DipTrace after adding/renaming a plug‑in folder or editing `settings.xml`.
