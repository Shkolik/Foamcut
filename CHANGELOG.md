
# Change Log
All notable changes to this project will be documented in this file.

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
   
### Added

### Fixed 
- route generation with kerf compensation producing incorrect intersections
- postprocessor selecting wrong speed and doesn't use rapid movements
- handling of route parts smaller than step size

## [0.1.8] - 2025-07-15
   
### Added

### Fixed 
- Error compute a route with kerf compensation - Points are equal
- Sorting face edges sometimes produce bad result. Another attempt to mitigate it.

## [0.1.7] - 2025-07-07
   
### Added

### Fixed 
- Postprocessor pause handling.
- join operation fail when edges added not from one side 
- independent pause setting for every part of the route 

## [0.1.6] - 2024-12-15
   
### Added

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

### Fixed
 