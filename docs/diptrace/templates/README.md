# Reusable release templates

These files are starting points, not a prebuilt plug-in.

- Copy exactly one `settings.*.xml` to the target plug-in folder as `settings.xml`.
- Replace `MyPlugin`, its caption/hint, modes, and scopes. Keep every applicable `<Settings>`
  child present and use only canonical values from `01_plugin_architecture.md`.
- Copy `python/plugin_main.py`, implement `transform()`, and keep its no-change and atomic-save
  behavior.
- Build with `python/build_exe.ps1` using a pinned Python and PyInstaller. Match the DipTrace
  edition: x86 for 32-bit DipTrace, x64 for 64-bit DipTrace. The x64 stack is recommended for
  large boards; pass `-ExpectedPythonBits 32` with a 32-bit interpreter for the compatibility
  artifact.
- Use `python/capture_exchange.py` as a separate export-only diagnostic plug-in when you need a
  true runtime exchange fixture. Build it, then clone the **intended production manifest**:
  preserve its `ExpMode` and object scopes, set `ImpMode=None`, and change `ExeFile` to the capture
  executable. It copies `argv[1]` and never changes it. This captures the payload the real plug-in
  would receive.
- After installing, run `verify_installed_artifact.ps1` to compare the built/installed artifact
  tree and verify the exact manifest target. Pass the `.exe` for `onefile`, or the complete output
  directory for `onedir`.

DipTrace scans the plug-in folders at startup. Restart the target editor after install or manifest
changes. Keep only the intended root executable in the folder and set `ExeFile` to its exact name.

See `../05_production_plugin_workflow.md` for fixture, parity, deployment, and release gates.

Example builds:

```powershell
.\python\build_exe.ps1 -PythonExe C:\Python313\python.exe `
  -ExpectedPythonVersion 3.13.7 -ExpectedPyInstallerVersion 6.15.0 `
  -ExpectedPythonBits 64 -Bundle onedir
.\python\build_exe.ps1 -PythonExe C:\Python313\python.exe `
  -ExpectedPythonVersion 3.13.7 -ExpectedPyInstallerVersion 6.15.0 `
  -SourceFile capture_exchange.py -Name CaptureExchange -Bundle onefile
```

`onedir` normally starts faster; `onefile` is easier to copy but has cold extraction/scanning cost.
The version numbers above are examples—set them to the versions deliberately pinned for the
release. The build records them and emits a recursive SHA-256 artifact manifest.
PyInstaller uses the interpreter's architecture, so use a 32-bit Python for x86 and a 64-bit
Python for x64; it does not cross-build the other target.

For `onedir`, copy the **entire contents** of `dist\<Name>\` into an otherwise clean plug-in folder,
then add `settings.xml`; copying only the EXE cannot work. For `onefile`, copy the one EXE plus
`settings.xml`. Keep source/tests outside the installed runtime folder so the strict verifier can
detect every unexpected or stale runtime file. Test and install the same bundle form.
