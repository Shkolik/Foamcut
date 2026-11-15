
# Change Log

All notable changes to this project will be documented in this file.

## [0.2.2] - 2026-11-29

### Added

- Several setups (Jobs) per document. The active setup, shown in bold in the tree, receives new objects; double-click a Job or use Activate in its context menu to switch to it, and Edit setup opens its settings. With several setups and none active the object commands stay disabled; a document with a single setup keeps working without activating it.
- Kerf direction (Normal / None / Reversed) is now user selectable for Path and Projection objects; it was hidden and read-only before. The setting appears in the property editor and in the movement task panels, and existing documents are migrated on open.
- G-code preamble now discloses the rotation axis position (Origin rotation X) in the MACHINE block for 5-axis machines.
- G-code export shows a confirmation dialog with the estimated run time after the file is saved.

### Changed

- `InitMachine` follows the scripting template: the module is now GUI-free domain code with the script-friendly `createMachine(doc)` factory, and the Init machine command lives in `MachineGui` next to the Job view provider.

### Fixed

- Route visual: break indexes were computed from object point counts instead of the flattened route layout, so the 3D view dropped cut segments (the Enter plunge of a rotation-first route and the Exit lead-out of every sub-route) while the G-code stayed correct. Breaks are now taken from the points actually generated, and existing documents are drawn from their stored point layout without a recompute.
- Route with a trailing Rotation (for example rotation at the start and at the end) failed to build when kerf compensation was Uniform or Dynamic with an IndexError on an empty trailing segment. The trailing rotation no longer produces an empty segment.
- Route postprocessor: Enter ignored its Rapid move flag, so the plunge from safe height to the lead-in start was always G1. It is now G0 when Rapid move is enabled, including an Enter without lead-in that plunges straight to the entry point; the lead-in to the entry point stays a cut.
- Origin rotation X always ignored the machine default parameters and was derived from the horizontal travel. It now comes from the same parameter group as the rest of the machine geometry (falling back to half of the horizontal travel when the parameter does not exist yet).

## [0.2.1] - 2026-11-13

### Added

- Machine/process settings now live directly on `Job`; the separate `Config` object is gone.
- Working planes are lightweight value objects created on demand, with analytic intersections.
- The Job view provider draws the CNC volume, foam block, working planes, origin and rotation axis.
- Old documents are detected on open and migrated automatically; the migration is reported in the console and the document is recomputed
- Route duplicate: parametric clone of an original route with a task panel for Y/Z placement and horizontal (YZ) / vertical (XY) mirroring
- Job task panel: every machine and process setting is editable from one panel that opens on Job creation and on double-click, with a group selector and pages for machine geometry, foam block, travel, axis mapping, feed rates, wire, kerf compensation, homing/parking and G-code. Values are unit-aware, dependent settings appear when their option is enabled, and Cancel restores the previous setup or removes a freshly created Job.
- Movement task panel for Move: live placement preview, feed/power overrides, unit-aware values and route preview
- Task panels for Path, Projection, Enter, Exit, Join, Rotation and Route with unit-aware values, expression overrides and route preview
- Expected program run time in the G-code preamble and in the console message on export. G93 uses the longer wire-end travel, G94 uses the full commanded-axis vector like GRBL does for orthogonal linear axes; G0 moves use the slowest axis.

### Notes

- Only original routes can be duplicated; clones cannot be cloned. Deleting a source leaves its clones inert with an explicit export error.
- XY mirror pivots on the foam block mid-height, keeps plunge moves at safe height and rebuilds Enter/Exit leads from the mirrored anchor.
- Horizontal (YZ) mirror swaps the left/right profiles while keeping every point on its own wire plane, so the viewport and the G-code show the same result.

### Fixed

- Job: the machine graphics no longer turn green when the Job is selected - the Job is unpickable in the 3D view, its selection style is reduced to a bounding box and opening the Job panel clears the selection
- Route postprocessor: shifted points/move types, lost route endpoint and rapid moves into foam on Enter/Exit routes
- Route: duplicate Exit end point when lead-out is enabled
- Route: offset joining created a cusp/loop when adjacent edges had different dynamic kerf compensation
- Route: dynamic kerf compensation failed when the compensation step met a nearly tangential joint. The offset ends are now bridged with a straight segment instead of aborting the route

## [0.2.0] - 2026-08-20

### Notes

- Switching to G93 mode require feed and speed calibration. Usually you should aim for 10-15% lower cut speed than in G94, since in G94 mode real "in-foam" speed usually lower than a set speed. In G93 mode real speed is equal to set speed.

### Added

- G93 feed rate mode: configurable FeedRateMode property (G94/G93), mode-aware feed for travel, rotation and end-block up moves. G94 remains the default for migrated setups.
- Headless test harness for postprocessor and mirror verification
- Example added
- Working area validation: `Label: message` on creation and on recompute

### Fixed

- MirrorGcode: rapid moves without a feed rate are now mirrored correctly
- MirrorGcode: first move command mirrored correctly, input float precision preserved
- Postprocessor: index out of range and points count overrun on route exit
- Migration: missing migrations added, migration text fixed, lead properties hidden when leads disabled
- Route validation, offset, path from faces, face projection and intersectLineAndPlane hardening
- Dynamic wire power and config lookup hardening
- Restrict to one setup per document
- More robust error handling on all objects
- Tooltip and misleading UI fixes
- New default config values
- Major Route performance refactoring (10x faster now)

## [0.1.12] - 2026-03-30

### Fixed

- error message in a projection fixed

## [0.1.11] - 2026-03-07

### Notes

- This release has a breaking change in how wire speed is handled. Before this change user was specifying actual machine speed and kerf compensation was scaled to this speed. now user should specify max speed in a foam, and machine speed will be scaled to keep this speed constant. There's very slight difference if piece has not much taper, but for small tapered objects/pathes there might be significant difference. Please review your legacy files and do ajustments needed.

### Added

- Proper error handling added to all objects

### Fixed 

- Kerf compensation on flipped edges goes wrong direction #19
- Dynamic kerf compensation depends on sequence of adding edges #7

## [0.1.10] - 2025-10-16

### Added

- Add an option to change comment style. #8
- Add ability to rapid move for any move object. #15
- Add preamble to the output gcode #17

### Fixed

- index out of range in the Config.py migration code #10
- LinuxCNC expect to see % as the first character and the last of the program #11
- MirrorGcode.py:43: SyntaxWarning: invalid escape sequence '\-' #13
- After file reopening it's possible to select helper objects #14
- Dynamic kerf compensation gives an error route in near parallel condition #18

## [0.1.9] - 2025-07-28

### Fixed

- route generation with kerf compensation producing incorrect intersections
- postprocessor selecting wrong speed and doesn't use rapid movements
- handling of route parts smaller than step size

## [0.1.8] - 2025-07-15

### Fixed

- Error compute a route with kerf compensation - Points are equal
- Sorting face edges sometimes produce bad result. Another attempt to mitigate it.

## [0.1.7] - 2025-07-07

### Fixed

- Postprocessor pause handling.
- join operation fail when edges added not from one side 
- independent pause setting for every part of the route 

## [0.1.6] - 2024-12-15

### Fixed

- Edge pairs detection when creating set of edges from 2 selected faces and edges on these faces are going in different directions.

## [0.1.5] - 2024-12-15

### Added

- wire stretch verification. For now it provide user a warning if wire stretch exceed maximum and do not prevent gcode to be produced.

### Fixed

- generating Gcode from route without compensation that has strait lines (regression from optimization)

## [0.1.4] - 2024-10-25

### Added

- parameter to suppress warnings

### Fixed

- offset calculation improved. When makeOffset2D fails code fallback to custom calculations
- route points calculations improved by using interpolation instead of approximation

## [0.1.3] - 2024-10-23

### Added

- dynamic kerf compensation

### Fixed

- Edge pairs detection when creating set of edges from 2 selected faces
- route handling when route have multiple Enter-Exit transitions

## [0.1.2] - 2024-10-15
 
### Added

- Base objects implementation
- Helpers visualization (Foam block, working planes, etc.)
- Route visualization
- Kerf kompensation support
