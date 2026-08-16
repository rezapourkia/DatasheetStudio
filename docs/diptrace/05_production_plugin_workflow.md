# Production Plug-in Workflow

This chapter is the shortest reliable path from a user request to a plug-in that can be
installed and verified without access to DipTrace source code. Read
[`01_plugin_architecture.md`](01_plugin_architecture.md) first for the protocol itself, then use
this workflow as the delivery checklist.

## 1. Freeze the contract before writing code

Turn the request into a one-page contract sheet. Do not start with XML queries or geometry.

```text
Host program:        PCB | Schematic | CompEdit | PattEdit
Input scope:         All | Selected | Partial, per object family
Import mode:         exact <ImpMode> token from file 01
Objects inspected:  ...
Objects changed:    ...
Allowed changes:    exact attributes/subtrees
Forbidden changes: layer, side, font, names, connectivity, ...
No-result policy:   unchanged object | skip | abort whole run
Unknown-data policy: fail closed and leave exchange file untouched
Geometry policy:     hard/full bounds, visual profiles + eligibility/calibration ID
User feedback:      one window or a log path; never a chain of dialogs
Performance target: fixture, cold/warm time, peak memory
Deliverables:       source, settings.xml, executable, README, tests
```

This sheet determines `settings.xml`, the XML families that must be exported, the merge-safe
output shape, and the tests. If a required fact is not exported, broaden the **input** contract;
do not invent the missing value. Broad input and narrow output are compatible.

## 2. Capture real fixtures

Use DipTrace to export representative designs before implementing the transformation:

1. Make a tiny hand-checkable design containing one instance of every relevant object/state.
2. Export a real plug-in exchange or matching DipTrace XML.
3. Add one realistic large design for performance and memory measurements.
4. Keep immutable originals. Copy a fixture before every test.
5. Record the DipTrace build and root `Type`, `Version`, and `Units`.

Include positive, negative, and malformed cases. For geometry this normally means both physical
sides, rotations, flips, custom and common styles, arcs, cutouts, missing references, and a case
where no legal result exists. Never create both the implementation and its expected output with
the same transform or geometry helper.

For PCB text work, capture the layout/font-cell rectangle separately from visible glyph strokes.
Record which predicates use the full cell, which may use a calibrated visual profile, and the exact
font/string/angle classes eligible for that profile.
[`12_pcb_text_geometry.md`](12_pcb_text_geometry.md) provides a verified RefDes profile and the
calibration checklist.

## 3. Design a transactional transformation

Use four explicit phases:

1. **Validate and parse.** Verify root type, units, required containers, enums, references, point
   counts, and numeric values. Reject `NaN`/infinity, require nonnegative dimensions where the
   schema does, and include object identity plus attribute name in every diagnostic.
2. **Analyze.** Resolve styles, text, transforms, connectivity, and geometry into immutable or
   compact working records. Do not alter the XML yet.
3. **Plan.** Compute every intended edit and validate the complete result.
4. **Commit once.** Apply only the approved edits in memory, write a temporary sibling, then
   atomically replace the exact path from `argv[1]`.

An unsupported or malformed object must follow the contract sheet: skip that object only when a
skip is proven safe; otherwise abort the whole run. On abort, the original exchange file remains
byte-for-byte untouched.

If the requested operation produces no **semantic** changes, do not serialize the tree merely to
make its timestamp change. This avoids a needless DipTrace import and prevents serialization-only
noise. Be especially careful with mode attributes: setting a visually unchanged marking to
`Align="Position"` can freeze a formerly `Auto` or `Common` placement and is therefore a real
change, not a no-op.

## 4. Preserve more than you edit

For `ImpMode=Edit`, output only changed top-level records **plus unchanged resolver infrastructure
that the proven merge contract requires**. Return every changed record as the complete exported
record unless its dialect chapter proves a narrower merge contract. PCB component edits, for
example, retain `/Source/Library` so `PatternStyle` references resolve. Preserve unknown attributes
and children. Do not rebuild an object from a hand-written schema.

`xml.etree.ElementTree` preserves unknown nodes semantically when they remain in the tree, but it
does not promise byte identity: indentation, namespace prefixes, attribute quoting, comments, and
an XML declaration may differ after serialization. Compare normalized XML or object semantics in
tests; require byte identity only for abort/no-op paths where the file is not written.

## 5. Make failures visible without trapping DipTrace

DipTrace waits for the plug-in process. Every code path must terminate.

- Write one diagnostic log with a traceback and stage/object identifiers.
- Prefer `%LOCALAPPDATA%\DipTrace\PluginLogs`; fall back to `%TEMP%` if creating or writing the
  first location fails.
- Do not write beside an executable installed under `Program Files`.
- Do not show a sequence of post-run message boxes. They can appear behind the host, look like a
  hang, and force the user through several modal acknowledgements.
- If interaction is required, use one ordinary plug-in window and close it before the process
  exits. The public protocol does not provide a DipTrace owner-window handle, so do not rely on a
  cross-process owned modal dialog.
- If writing is deferred until a result window closes, define title-bar Close, explicit Close, and
  Cancel semantics. Keep the state visibly pending until the atomic replace succeeds; do not close
  the last progress/result UI or log final success before the exchange file has actually committed.
- A command-line/headless transformation should use exit status plus the log. DipTrace detects
  edits from the exchange file, not from the process exit code.

Log enough to reproduce a run: plug-in version, executable/source identity, input root metadata,
stage timings, processed/changed/skipped counts, and the first unsupported object with its reason.
Do not log the whole board unless the user explicitly enables diagnostic data capture.

## 6. Python project and build

A practical layout is:

```text
MyPlugin/
  settings.xml
  MyPlugin.exe
  README.md
  src/
    main.py
    transform.py
    geometry.py
  tests/
    fixtures/
    test_transform.py
  build.ps1
```

Keep the XML transformation callable as a normal Python function. The executable entry point
should do only argument validation, logging, UI selection if any, and process exit. This makes
fixture tests exercise the same implementation that is packaged.

When Python is a reference implementation for a later Delphi/C# integration, freeze its option
set, target-selection rules, deterministic ordering, changed-object list, and output for every
golden fixture before porting. Run both implementations from immutable copies and require the
declared parity level (ordered decisions, normalized XML, or byte-identical result). Add every
future bug fixture to the reference first, then port the verified behavior. The public SDK need
not contain the product's private search/scoring algorithm to support this oracle workflow.

For a Python plug-in, build a Windows executable with a pinned Python and packager version
(PyInstaller is one suitable option). Match the DipTrace edition: build x86 with a pinned 32-bit
interpreter for 32-bit DipTrace and x64 with a pinned 64-bit interpreter for 64-bit DipTrace.
Use the full x64 stack for large XML/geometry; x86 is the compatibility build. PyInstaller does
not cross-build between x86 and x64. The ready command accepts `ExpectedPythonBits` in
[`templates/python/build_exe.ps1`](templates/python/build_exe.ps1). Choose deliberately:

- **one-folder** starts faster and makes packaged dependencies easier to inspect;
- **one-file** is convenient to distribute but extraction and security scanning can dominate
  cold-start time.

PyInstaller is a packager, not a native compiler for ordinary Python code. It bundles a CPython
runtime, bytecode, and imported native modules. Python geometry loops still execute through the
interpreter; only work delegated to native extensions is native. A later Delphi/C# port may be much
faster in tight numeric loops, but the end-to-end gain depends on XML, process start, allocations,
and data layout. Benchmark stage by stage instead of quoting one language-wide multiplier.

Do not treat a successful package command as proof that the installed executable contains the
reviewed source. Record a build identifier in both the log and executable, remove/replace the old
artifact deliberately, and compare source and packaged behavior as described below.

When verifying a Windows-subsystem/`--noconsole` executable from PowerShell, do not rely on a direct
launch followed by `$LASTEXITCODE`: the shell may return before the GUI process finishes and the
value may be empty or stale. Wait for the real process and read its exit code explicitly:

```powershell
$p = Start-Process -FilePath $exe -ArgumentList ('"{0}"' -f $fixture) -Wait -PassThru
$p.ExitCode
```

Always compare output hashes/normalized XML after the wait; exit zero alone does not prove that the
exchange file was changed or that the packaged code matches the reviewed source.

For C#, publish a `win-x86` or `win-x64` `WinExe` matching the DipTrace edition. Either make it
self-contained (and optionally single-file) or state the exact required .NET runtime. For Delphi,
build the corresponding Win32/Win64 GUI executable; if runtime packages are enabled, ship every
required BPL, otherwise build standalone. The x64 stack avoids address-space failures on large
XML. Test every architecture and packaging form that is installed; do not infer x86 parity from
an x64 test.

## 7. Verification ladder

Run these gates in order:

1. **Static contract check:** `settings.xml`, paths, root types, modes, and object scopes agree
   with the contract sheet.
2. **Unit tests:** units, numeric parsing/formatting, transforms, enum mapping, and individual
   geometry primitives.
3. **Golden fixtures:** normalized output and changed-object lists match independently prepared
   expectations.
4. **Abort/no-op tests:** malformed, unsupported, and no-change inputs leave the file untouched.
5. **Differential tests:** optimized and reference implementations give the same ordered decisions
   and normalized output on randomized small cases.
6. **Source/EXE parity:** run the reviewed source and the exact distributable executable on two
   copies of the same fixture; wait for the GUI process explicitly, then compare normalized XML,
   changed IDs, decisions, summaries, and output hashes.
7. **Termination safety:** force termination during parse/compute and temporary-file write; the
   original exchange must remain untouched. A stale sibling temp is acceptable and must be cleaned
   on a later start because hard termination cannot run `finally`.
8. **Installed-artifact identity:** compare the built and installed executable hashes, embedded/log
   versions, and exact `settings.xml@ExeFile`; ensure no fallback EXE can be selected.
9. **Cold/warm performance:** measure process start, parse, analysis, solve, serialization, total
   time, and peak memory on the large fixture.
10. **DipTrace smoke test:** install under the correct program folder, run on a disposable project,
   inspect the result, undo/reopen, and verify failure feedback. This final GUI check belongs to a
   real DipTrace environment; static review cannot claim it.

Hashing the executable is useful for identifying what was tested, but hash equality alone says
nothing about source equivalence. Parity is a behavioral test plus a recorded artifact identity.

## 8. Release package

Ship:

- a clean per-program runtime folder containing `settings.xml` and the tested artifact: one EXE
  for `onefile`, or the **entire** PyInstaller `onedir` contents (never the EXE alone);
- source and reproducible build instructions;
- the contract sheet and supported/unsupported cases;
- automated tests and sanitized fixtures;
- the log location and a troubleshooting section;
- the DipTrace builds on which the GUI smoke test was performed.

Keep source, tests, fixtures, and build records in the release archive but outside the clean
installed runtime folder. Record a recursive relative-path/size/SHA-256 manifest for `onedir`, not
only the root EXE hash; verify the installed file set and every hash so stale DLL/PYD/ZIP files
cannot survive deployment.

Close the target DipTrace editor before replacing an installed artifact. Writing under
`Program Files` normally requires an elevated installer or an explicitly approved elevated copy;
do not make a development/test script silently elevate or deploy. After copying, verify built and
installed hashes plus `settings.xml@ExeFile`, then restart the editor so it rescans plug-ins.

Do not require users or their coding model to inspect DipTrace implementation files. Every runtime
assumption needed by the plug-in must be stated in this SDK, derived from an actual exported
fixture, or treated as unsupported and failed closed.
