# Feature Deprecation Candidates

This document tracks features that are candidates for deprecation or removal.
Each entry lists what the feature does, the evidence behind the proposal, and its
current status. Keep it up to date as decisions are made.

Status legend:

- **Candidate** — proposed, not yet decided
- **Confirmed** — agreed to deprecate; a removal plan (or versioning note) should follow

---

## 1. Dynamic wire power — Confirmed

**Where:**
- `MachineConfig.DynamicWirePower` — `MachineConfig.py:52-54`
- `Postprocess.generateWireCompensatedPower` — `Postprocess.py:100-111`
- `Postprocess.getDynamicWirePowerCommand` — `Postprocess.py:227-234`
- Start-block compensation — `Postprocess.py:175-183`

**What it does:** Varies wire power per move (`Sxx.xx` appended to every cut line)
based on the instantaneous wire length (`point1.distanceToPoint(point2)`), instead of
using a single power value set once via `WireOnCommand`.

**Evidence / reasons:**
- The start-block power path was broken (H3): `generateWireCompensatedPower` was
  called with 2 arguments instead of 3 → `TypeError`. The feature was not being
  exercised and the bug went unnoticed.
- Its own property docs warn that the controller must be in "Laser mode",
  *"otherwise machine will halt for a brif moment after each move"* — fragile and
  hardware-dependent.
- Off by default (`DynamicWirePower = False`). When off, the whole machinery returns
  an empty string and is dead weight on every cut line.
- Emits an extra S-word per move, inflating G-code size.
- Static power (`WireOnCommand M03 S{WirePower}`) covers the common case; dynamic
  power only matters for extreme tapers where per-move wire length changes.

**Status:** Confirmed for deprecation (author).

---

## 2. Legacy Config and cosmetic helper objects — Confirmed

**Where:**
- `MachineConfig.py` — `Config` object and `MachineConfigVP`
- `FoamCut_WorkingPlane.py` — `WPL` / `WPR`
- `FoamBlock.py` — `Block`
- `MachineOrigin.py` — `Origin`
- `RotationAxis.py` — `RotationAxis`

**What it does:** Stores machine/process settings in a separate `Config` child and draws
the CNC volume, foam block, working planes, origin and rotation axis as document objects.

**Replacement:** Settings live on `Job`; the Job view provider (`MachineGui.MachineVP`)
draws the same geometry inline. Working planes are `WorkingPlane` value objects.

**Status:** Confirmed. The classes remain only for restoring old documents before
`Migration.migrate_document()` runs; they are marked `__obsolete__ = True` and pending
removal after the migration-support window.
