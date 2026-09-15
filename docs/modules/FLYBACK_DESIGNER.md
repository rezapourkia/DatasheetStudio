# Datasheet Studio — Native Flyback Designer

## 1. Purpose

Flyback Designer is a native PySide6 engineering tool for preliminary
constant-frequency discontinuous-conduction-mode (DCM) flyback design. It
replaces the previous browser prototype as a maintained Datasheet Studio tool.

The implementation must not embed, load, translate at runtime, or otherwise
depend on the previous HTML application. The browser project is used only as a
reference for equations, validation cases, and documented limitations.

## 2. User-Facing Behaviour

- Open from **Tools → Power Design → Flyback Designer…**.
- Display a Persian, right-to-left native desktop dialog.
- Edit input-bus, switching, magnetic, winding, clamp, loss, feedback, and
  output parameters.
- Add and remove up to eight outputs.
- Recalculate immediately from explicit user inputs.
- Show primary/secondary turns, magnetising inductance, flux density, peak and
  RMS currents, winding wire recommendations, window fill, estimated air gap,
  reflected voltage, switch stress, RCD estimate, losses, ripple, and warnings.
- Clearly identify all bundled cores/components as illustrative and unverified.
- Save and reopen the design as versioned JSON without requiring CLI commands.

## 3. Calculation Boundary

All numerical work lives in a pure Python engine under:

```text
src/datasheet_studio/tools/flyback_designer/engine.py
```

The engine:

- has no PySide6, file-system, network, settings, or PDF dependency;
- accepts typed project/core/component data;
- returns typed results, validation errors, and engineering warnings;
- rejects missing, non-finite, zero, negative, or out-of-range inputs before
  division;
- preserves unit names in the data model and presentation labels.

The UI may format values but must not reproduce or alter the equations.

## 4. Initial Engineering Model

Version 1 implements the existing reviewed DCM pre-design model:

- energy balance and primary volt-seconds at low-line/full-load;
- integer primary and secondary turns with a 12% target idle interval;
- actual demagnetisation recalculated after integer turns;
- multi-output turns and current estimates;
- copper loss at 20 °C with strand sizing from current density;
- area-based window-fill estimate;
- gap estimate assuming gap reluctance dominates;
- RCD clamp estimate;
- separate BJT and MOSFET conduction-loss estimates;
- simplified switching, bridge, diode, reverse-recovery, core, and first-output
  capacitor losses;
- first-output capacitor ripple and TL431 DC feedback values.

## 5. Safety and Provenance Rules

- The result is a preliminary design aid, not production approval.
- Illustrative seed data is never marked verified.
- Unknown parameters are not invented or represented as measured zero.
- Verification means explicit user review against the exact manufacturer part
  and datasheet revision.
- Warnings remain visible; the UI must not suppress an inconvenient result.
- No AI or network request occurs automatically.

## 6. Non-Goals for Version 1

- Importing or embedding the former HTML/JavaScript interface.
- CCM, QR, valley switching, or transient simulation.
- SPICE generation.
- Detailed bobbin layer packing, fringing, proximity/skin AC resistance, EMI,
  thermal iteration, compensation-loop design, or safety-standard approval.
- Treating sample EE core dimensions or generic parts as purchasing data.

## 7. Persistence

Saved designs use a versioned JSON envelope:

```text
{
  "schema_version": 1,
  "project": { ... },
  "core": { ... },
  "parts": [ ... ]
}
```

Loading validates the complete document before replacing the current form.
Saving uses a normal desktop file dialog and UTF-8 JSON.

## 8. Acceptance Criteria

- Opens from the registry-built Tools menu without an open datasheet.
- Contains no WebView and no dependency on files in the former FLYBACK project.
- All reference numerical tests pass in Python.
- Invalid inputs produce readable Persian validation messages without a crash.
- Multi-output designs conserve requested output power in the engine model.
- Save/open round-trips the typed design data.
- The default 24 W example reproduces the documented reference values within
  numerical tolerance and retains its intentional warnings.
- The main application launches with the tool installed.

## 9. Manual Verification

After automated tests pass:

1. Launch Datasheet Studio.
2. Open **Tools → Power Design → Flyback Designer…**.
3. Confirm Persian RTL layout and readable resizing.
4. Recalculate the default example and inspect results/warnings.
5. Add a second output, recalculate, then remove it.
6. Save a design, change fields, reopen it, and confirm restoration.
7. Close the tool and confirm the PDF workspace remains usable.

