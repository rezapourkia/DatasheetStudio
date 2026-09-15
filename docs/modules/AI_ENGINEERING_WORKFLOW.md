# Datasheet Studio — AI Engineering Workflow

**Status:** Planned architecture

## 1. Purpose

Define a provider-independent and auditable protocol for using AI to convert a
datasheet into engineering inputs and to assist an active design.

## 2. Controller Extraction Pipeline

```text
PDF hash → text/OCR with page markers → coverage check → versioned MD prompt
→ structured response → schema/unit validation → evidence validation
→ contradiction review → user acceptance → reusable component profile
```

“Read complete datasheet” means every page has one of these recorded outcomes:
text extracted, OCR extracted, intentionally skipped with reason, or failed.
Passing only selected pages is permitted for chat but not for a complete
controller-profile claim.

## 3. Required Extracted Sections

The controller schema includes, where published:

- exact part/revision/package and pin functions;
- topology and operating modes;
- switching-frequency min/typ/max and mode-dependent behavior;
- current-limit definition and tolerance;
- duty-cycle, minimum on/off time, leading-edge blanking, and slope behavior;
- internal switch type, voltage/current/thermal limits, and loss-relevant data;
- startup, UVLO, bias, auxiliary-winding, standby, and burst behavior;
- feedback pin transfer behavior, reference/thresholds, source/sink limits, and
  approved optocoupler/PSR arrangements;
- OVP/OCP/OTP/short-circuit behavior and restart/latch conditions;
- manufacturer application equations, recommended operating region, reference
  circuits, and layout warnings;
- every missing or contradictory fact needed by the selected calculation mode.

Each fact must cite its page and conditions. The response schema rejects plain
numbers without units and provenance.

## 4. Versioned Prompt Artifacts

Prompt templates live under a future `prompts/` source directory. A prompt file
contains purpose, permitted context, extraction checklist, response schema
version, uncertainty rules, and examples. Runtime values are inserted into a
copy saved with the AI run; the template itself remains unchanged.

The provider response is retained as Markdown for human review and parsed into
JSON only through a strict validator. Provider name, model, timestamp, source
hashes, prompt version, and schema version are recorded.

## 5. Interactive Design Loop

During design the AI may:

- explain a failed constraint with links to the calculation and datasheet page;
- request a new deterministic scenario run;
- rank engine-produced core candidates using user priorities;
- draft a proposed edit set;
- compare proposed feedback topologies;
- answer contextual questions in the embedded chat.

Any proposed input changes are shown as a diff and require user acceptance.
AI cannot edit verified source facts, hide engine warnings, or label estimates
as verified.

## 6. Offline and Failure Behavior

Saved profiles and deterministic calculations continue to work without AI.
Provider errors, token limits, missing OCR, incomplete page coverage, invalid
JSON, or unresolvable citations produce a resumable failed run, not a partially
accepted profile.

## 7. Acceptance Criteria

- The same source and prompt versions produce a reviewable, archived request.
- Every accepted controller field links to source evidence.
- Complete extraction reports page coverage explicitly.
- Invalid units or out-of-range values cannot enter the calculation engine.
- A design remains openable and calculable with all providers disabled.
