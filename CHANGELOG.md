
# Change Log
All notable changes to this project will be documented in this file.

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
 